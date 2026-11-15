"""Prefix lifecycle application service."""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from winebox.common.exceptions import PrefixAuditError, WineboxError
from winebox.domain.models import Prefix, PrefixOrigin, PrefixStatus, SecurityPolicy
from winebox.infrastructure.bwrap_adapter import BwrapAdapter
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.infrastructure.process_manager import PrefixLock, ProcessManager, prefix_lock
from winebox.infrastructure.wine_adapter import WineAdapter
from winebox.security.auditor import PrefixAuditor
from winebox.security.mount_builder import MountBuilder


class PrefixService:
    """Manages creation, auditing, and deletion of Wine prefixes."""

    def __init__(
        self,
        repo: Optional[SqliteRepository] = None,
        bwrap_adapter: Optional[BwrapAdapter] = None,
    ) -> None:
        self.repo = repo or SqliteRepository()
        self.bwrap_adapter = bwrap_adapter or BwrapAdapter()

    def create_prefix(
        self,
        prefix_id: str,
        name: Optional[str] = None,
        runner_id: str = "system-wine",
        default_profile_id: str = "permissive",
        initialize_wineboot: bool = True,
        allow_network: bool = True,
    ) -> Prefix:
        """Creates a new isolated Wine prefix and runs initial wineboot inside sandbox."""
        p_dir = self.repo.get_prefix_dir(prefix_id)
        if p_dir.exists():
            raise WineboxError(f"Prefix '{prefix_id}' already exists at {p_dir}")

        prefix_inner = p_dir / "prefix"
        home_inner = p_dir / "home"
        logs_inner = p_dir / "logs"

        for d in (prefix_inner, home_inner, logs_inner):
            d.mkdir(parents=True, exist_ok=True)

        prefix = Prefix(
            id=prefix_id,
            name=name or prefix_id,
            runner_id=runner_id,
            default_profile_id=default_profile_id,
            origin=PrefixOrigin.CREATED,
            status=PrefixStatus.READY,
        )
        self.repo.save_prefix(prefix)

        if initialize_wineboot:
            with prefix_lock(p_dir):
                runner = self.repo.load_runner(runner_id)
                policy = SecurityPolicy(network=allow_network)
                builder = MountBuilder(
                    prefix_path=prefix_inner,
                    isolated_home_path=home_inner,
                    policy=policy,
                    custom_runner_dir=runner.wine_bin.parent.parent if not runner.is_system else None,
                )
                bwrap_args = builder.build_bwrap_args()
                wineboot_cmd = WineAdapter.build_wineboot_cmd(runner)

                # Run wineboot inside sandbox
                self.bwrap_adapter.execute_in_sandbox(
                    bwrap_args=bwrap_args,
                    command_inside=wineboot_cmd,
                    inherit_stdio=False,
                )

                # Neutralize drive Z: pointing to host root
                PrefixAuditor.sanitize_dosdevices(prefix_inner)

        return prefix

    def list_prefixes(self) -> List[Prefix]:
        return self.repo.list_prefixes()

    def get_prefix(self, prefix_id: str) -> Prefix:
        return self.repo.load_prefix(prefix_id)

    def audit_prefix(self, prefix_id: str) -> List[str]:
        p_dir = self.repo.get_prefix_dir(prefix_id)
        prefix_inner = p_dir / "prefix"
        return PrefixAuditor.audit_prefix(prefix_inner, check_registry=False)

    def remove_prefix(self, prefix_id: str) -> None:
        p_dir = self.repo.get_prefix_dir(prefix_id)
        with prefix_lock(p_dir):
            self.repo.delete_prefix(prefix_id)

    def kill_prefix(self, prefix_id: str, force: bool = False) -> Dict[str, Any]:
        """Terminate all running processes associated with the prefix (ADR-025)."""
        p_dir = self.repo.get_prefix_dir(prefix_id)
        if not p_dir.exists():
            raise WineboxError(f"Prefix '{prefix_id}' does not exist at {p_dir}")

        prefix_inner = p_dir / "prefix"
        killed_pids: List[int] = []

        # 1. Check if prefix.lock is held or has a recorded PID
        recorded_pid = PrefixLock.read_locked_pid(p_dir)
        is_locked = PrefixLock.is_locked(p_dir)

        pids_to_kill: List[int] = []
        if recorded_pid and ProcessManager.is_pid_alive(recorded_pid):
            pids_to_kill.append(recorded_pid)

        # 2. Find any other sibling/child processes matching prefix path
        matched_pids = ProcessManager.find_processes_by_prefix(p_dir)
        for m_pid in matched_pids:
            if m_pid not in pids_to_kill:
                pids_to_kill.append(m_pid)

        if not pids_to_kill and not is_locked:
            # Idle prefix
            PrefixAuditor.sanitize_dosdevices(prefix_inner)
            return {"running": False, "killed_pids": []}

        # 3. Kill all found processes
        for pid in pids_to_kill:
            success = ProcessManager.kill_pid(pid, timeout=1.0, force=force)
            if success:
                killed_pids.append(pid)

        # 4. Wait briefly and ensure lock file is unlocked
        deadline = time.time() + 1.0
        while time.time() < deadline:
            if not PrefixLock.is_locked(p_dir):
                break
            time.sleep(0.05)

        # 5. Sanitize dosdevices
        PrefixAuditor.sanitize_dosdevices(prefix_inner)

        return {"running": True, "killed_pids": killed_pids}

