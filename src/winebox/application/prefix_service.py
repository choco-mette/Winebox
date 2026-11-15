"""Prefix lifecycle application service."""

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from winebox.common.exceptions import ResourceNotFoundError, WineboxError
from winebox.domain.models import Prefix, PrefixOrigin, PrefixStatus, SecurityPolicy
from winebox.infrastructure.backup_adapter import BackupAdapter
from winebox.infrastructure.bwrap_adapter import BwrapAdapter
from winebox.infrastructure.fs_adapter import FilesystemAdapter
from winebox.infrastructure.log_manager import LogManager
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.infrastructure.process_manager import PrefixLock, ProcessManager, prefix_lock
from winebox.infrastructure.wine_adapter import WineAdapter
from winebox.security.auditor import PrefixAuditor
from winebox.security.mount_builder import MountBuilder


class PrefixService:
    """Manages creation, auditing, and deletion of Wine prefixes."""

    ALLOWED_WINE_TOOLS = ("winecfg", "regedit", "cmd", "taskmgr", "control", "uninstaller")

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
        try:
            p_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError as e:
            raise WineboxError(f"Prefix '{prefix_id}' already exists at {p_dir}") from e

        prefix_inner = p_dir / "prefix"
        home_inner = p_dir / "home"
        logs_inner = p_dir / "logs"

        try:
            with prefix_lock(p_dir):
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

                    try:
                        self.bwrap_adapter.execute_in_sandbox(
                            bwrap_args=bwrap_args,
                            command_inside=wineboot_cmd,
                            inherit_stdio=False,
                        )
                    finally:
                        PrefixAuditor.sanitize_dosdevices(prefix_inner)

                return prefix
        except Exception:
            FilesystemAdapter.remove_tree(p_dir)
            raise

    def list_prefixes(self) -> List[Prefix]:
        return self.repo.list_prefixes()

    def get_prefix(self, prefix_id: str) -> Prefix:
        return self.repo.load_prefix(prefix_id)

    def audit_prefix(self, prefix_id: str) -> List[str]:
        p_dir = self.repo.get_prefix_dir(prefix_id)
        if not p_dir.exists():
            raise WineboxError(f"Prefix '{prefix_id}' does not exist at {p_dir}")
        prefix_inner = p_dir / "prefix"
        with prefix_lock(p_dir):
            return PrefixAuditor.audit_prefix(prefix_inner, check_registry=False)

    def remove_prefix(self, prefix_id: str) -> None:
        p_dir = self.repo.get_prefix_dir(prefix_id)
        if not p_dir.exists():
            raise WineboxError(f"Prefix '{prefix_id}' does not exist at {p_dir}")
        with prefix_lock(p_dir):
            self.repo.delete_prefix(prefix_id)

    def read_logs(self, prefix_id: str, max_lines: int = 50) -> List[str]:
        log_mgr = LogManager(prefixes_dir=self.repo.prefixes_dir)
        return log_mgr.read_logs(prefix_id=prefix_id, max_lines=max_lines)

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

    def run_tool(
        self,
        prefix_id: str,
        tool_name: str,
        args: Optional[List[str]] = None,
        inherit_stdio: bool = True,
    ) -> int:
        """Executes an allowlisted Wine utility (winecfg, regedit, cmd, etc.) inside the prefix sandbox."""
        cleaned_tool = tool_name.strip().lower()
        if cleaned_tool not in self.ALLOWED_WINE_TOOLS:
            raise WineboxError(
                f"Unsupported Wine tool '{tool_name}'. Allowed: {', '.join(self.ALLOWED_WINE_TOOLS)}"
            )

        prefix = self.repo.load_prefix(prefix_id)
        runner = self.repo.load_runner(prefix.runner_id)
        p_dir = self.repo.get_prefix_dir(prefix.id)
        prefix_inner = p_dir / "prefix"
        home_inner = p_dir / "home"

        policy = SecurityPolicy(display=True, audio=False, network=False, gpu=False, gamepad=False)

        with prefix_lock(p_dir):
            builder = MountBuilder(
                prefix_path=prefix_inner,
                isolated_home_path=home_inner,
                policy=policy,
                custom_runner_dir=runner.wine_bin.parent.parent if not runner.is_system else None,
            )
            bwrap_args = builder.build_bwrap_args()
            cmd = WineAdapter.build_run_cmd(cleaned_tool, args=args, runner=runner)
            try:
                res = self.bwrap_adapter.execute_in_sandbox(
                    bwrap_args=bwrap_args,
                    command_inside=cmd,
                    inherit_stdio=inherit_stdio,
                )
                if res.returncode != 0:
                    raise WineboxError(f"Wine tool '{cleaned_tool}' exited with code {res.returncode}")
                return res.returncode
            finally:
                PrefixAuditor.sanitize_dosdevices(prefix_inner)

    @staticmethod
    def _ensure_prefix_idle(p_dir: Path, prefix_id: str) -> None:
        if PrefixLock.is_locked(p_dir) or ProcessManager.find_processes_by_prefix(p_dir):
            raise WineboxError(
                f"Prefix '{prefix_id}' is currently running. Stop it first (e.g. 'winebox prefix kill {prefix_id}')."
            )

    def list_backups(self) -> List[Dict[str, Any]]:
        return BackupAdapter.list_backups(self.repo.data_root / "backups")

    def backup_prefix(self, prefix_id: str, output_path: Optional[Path] = None) -> Path:
        """Creates a compressed snapshot archive of a prefix and its isolated home."""
        prefix = self.repo.load_prefix(prefix_id)
        p_dir = self.repo.get_prefix_dir(prefix.id)
        self._ensure_prefix_idle(p_dir, prefix.id)

        if output_path is None:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            output_path = self.repo.data_root / "backups" / f"{prefix.id}_{ts}{BackupAdapter.default_extension()}"

        manifest = {
            "format_version": 1,
            "prefix_id": prefix.id,
            "name": prefix.name,
            "runner_id": prefix.runner_id,
            "default_profile_id": prefix.default_profile_id,
            "origin": prefix.origin.value,
            "created_at": prefix.created_at.isoformat(),
            "backed_up_at": datetime.now(timezone.utc).isoformat(),
        }

        with prefix_lock(p_dir):
            return BackupAdapter.create_archive(p_dir, output_path, manifest)

    def restore_prefix(
        self,
        archive_path: Path,
        target_prefix_id: Optional[str] = None,
        force: bool = False,
    ) -> Prefix:
        """Safely validates, extracts, sanitizes, and registers a prefix from a backup archive."""
        staged_dir = self.repo.staging_dir / f"restore-{uuid.uuid4().hex[:8]}"
        try:
            manifest = BackupAdapter.extract_archive_safely(archive_path, staged_dir)
            if not (staged_dir / "prefix").is_dir():
                raise WineboxError(f"Invalid backup archive '{archive_path.name}': missing 'prefix/' directory.")

            (staged_dir / "home").mkdir(parents=True, exist_ok=True)
            PrefixAuditor.sanitize_dosdevices(staged_dir / "prefix")

            raw_id = target_prefix_id or (manifest or {}).get("prefix_id") or archive_path.name.split("_")[0].split(".")[0]
            final_id = raw_id.strip().lower().replace(" ", "-")
            dest_dir = self.repo.get_prefix_dir(final_id)

            if dest_dir.exists():
                if not force:
                    raise WineboxError(
                        f"Prefix '{final_id}' already exists. Use --force to overwrite or --id to restore under a new ID."
                    )
                self._ensure_prefix_idle(dest_dir, final_id)
                backup_old = self.repo.staging_dir / f"old-{final_id}-{uuid.uuid4().hex[:6]}"
                FilesystemAdapter.atomic_move(dest_dir, backup_old)
                try:
                    FilesystemAdapter.atomic_move(staged_dir, dest_dir)
                except Exception:
                    if not dest_dir.exists() and backup_old.exists():
                        FilesystemAdapter.atomic_move(backup_old, dest_dir)
                    raise
                FilesystemAdapter.remove_tree(backup_old)
            else:
                FilesystemAdapter.atomic_move(staged_dir, dest_dir)
        except Exception:
            FilesystemAdapter.remove_tree(staged_dir)
            raise

        runner_id = (manifest or {}).get("runner_id", "system-wine")
        try:
            self.repo.load_runner(runner_id)
        except ResourceNotFoundError:
            runner_id = "system-wine"

        profile_id = (manifest or {}).get("default_profile_id", "permissive")
        try:
            self.repo.load_profile(profile_id)
        except ResourceNotFoundError:
            profile_id = "permissive"

        name = (manifest or {}).get("name") or final_id
        restored = Prefix(
            id=final_id,
            name=name if not target_prefix_id else final_id,
            runner_id=runner_id,
            default_profile_id=profile_id,
            origin=PrefixOrigin.IMPORTED if target_prefix_id else PrefixOrigin.CREATED,
            status=PrefixStatus.READY,
        )
        self.repo.save_prefix(restored)
        return restored

