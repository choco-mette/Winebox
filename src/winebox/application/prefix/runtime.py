"""Prefix runtime control service (kill switch and sandboxed Wine tools)."""

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from winebox.common.exceptions import WineboxError
from winebox.domain.models import SecurityPolicy
from winebox.infrastructure.bwrap_adapter import BwrapAdapter
from winebox.infrastructure.log_manager import LogManager
from winebox.infrastructure.process_manager import PrefixLock, ProcessManager, prefix_lock
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.infrastructure.wine_adapter import WineAdapter
from winebox.security.auditor import PrefixAuditor
from winebox.security.mount_builder import MountBuilder


class PrefixRuntimeService:
    """Manages active prefix processes and sandboxed Wine utility execution."""

    ALLOWED_WINE_TOOLS = ("winecfg", "regedit", "cmd", "taskmgr", "control", "uninstaller")

    def __init__(
        self,
        repo: Optional[SqliteRepository] = None,
        bwrap_adapter: Optional[BwrapAdapter] = None,
    ) -> None:
        self.repo = repo or SqliteRepository()
        self.bwrap_adapter = bwrap_adapter or BwrapAdapter()
        self.log_manager = LogManager(prefixes_dir=self.repo.prefixes_dir)

    @staticmethod
    def ensure_prefix_idle(p_dir: Path, prefix_id: str) -> None:
        if PrefixLock.is_locked(p_dir) or ProcessManager.find_processes_by_prefix(p_dir):
            raise WineboxError(
                f"Prefix '{prefix_id}' is currently running. Stop it first (e.g. 'winebox prefix kill {prefix_id}')."
            )

    def kill_prefix(self, prefix_id: str, force: bool = False) -> Dict[str, Any]:
        """Terminate all running processes associated with the prefix (ADR-025)."""
        p_dir = self.repo.get_prefix_dir(prefix_id)
        if not p_dir.exists():
            raise WineboxError(f"Prefix '{prefix_id}' does not exist at {p_dir}")

        prefix_inner = p_dir / "prefix"
        killed_pids: List[int] = []

        my_pid = os.getpid()
        recorded_pid = PrefixLock.read_locked_pid(p_dir)
        is_locked = PrefixLock.is_locked(p_dir)

        pids_to_kill: List[int] = []
        if recorded_pid and recorded_pid != my_pid and ProcessManager.is_pid_alive(recorded_pid):
            pids_to_kill.append(recorded_pid)

        matched_pids = ProcessManager.find_processes_by_prefix(p_dir)
        for m_pid in matched_pids:
            if m_pid != my_pid and m_pid not in pids_to_kill:
                pids_to_kill.append(m_pid)

        for desc_pid in ProcessManager.find_descendant_pids(pids_to_kill):
            if desc_pid != my_pid and desc_pid not in pids_to_kill:
                pids_to_kill.append(desc_pid)

        if not pids_to_kill and not is_locked:
            PrefixAuditor.sanitize_dosdevices(prefix_inner)
            self.log_manager.log_event(prefix_id, "Kill switch checked: no active processes running", level="INFO", category="KILL")
            return {"running": False, "killed_pids": []}

        self.log_manager.log_event(
            prefix_id,
            f"Kill switch activated (force={force}, targeted_pids={pids_to_kill})",
            level="WARN",
            category="KILL",
        )

        for pid in pids_to_kill:
            if ProcessManager.kill_pid(pid, timeout=1.0, force=force):
                killed_pids.append(pid)

        deadline = time.time() + 1.0
        while time.time() < deadline:
            if not PrefixLock.is_locked(p_dir):
                break
            time.sleep(0.05)

        PrefixAuditor.sanitize_dosdevices(prefix_inner)
        self.log_manager.log_event(
            prefix_id,
            f"Kill switch finished: terminated {len(killed_pids)} process(es) (killed_pids={killed_pids})",
            level="INFO",
            category="KILL",
        )
        return {"running": True, "killed_pids": killed_pids}

    def run_tool(
        self,
        prefix_id: str,
        tool_name: str,
        args: Optional[List[str]] = None,
        inherit_stdio: bool = True,
        runner_id: Optional[str] = None,
    ) -> int:
        """Executes an allowlisted Wine utility (winecfg, regedit, cmd, etc.) inside the prefix sandbox."""
        cleaned_tool = tool_name.strip().lower()
        if cleaned_tool not in self.ALLOWED_WINE_TOOLS:
            raise WineboxError(
                f"Unsupported Wine tool '{tool_name}'. Allowed: {', '.join(self.ALLOWED_WINE_TOOLS)}"
            )

        prefix = self.repo.load_prefix(prefix_id)
        runner = self.repo.load_runner(runner_id or prefix.runner_id)
        p_dir = self.repo.get_prefix_dir(prefix.id)
        prefix_inner = p_dir / "prefix"
        home_inner = p_dir / "home"

        policy = SecurityPolicy(display=True, audio=True, network=False, gpu=True, gamepad=False)

        log_file = self.log_manager.get_log_file(prefix.id)
        self.log_manager.log_event(
            prefix_id,
            f"Launching Wine tool '{cleaned_tool}' with args={args or []}",
            level="INFO",
            category="TOOL",
        )

        with prefix_lock(p_dir):
            builder = MountBuilder(
                prefix_path=prefix_inner,
                isolated_home_path=home_inner,
                policy=policy,
                custom_runner_dir=runner.wine_bin.parent.parent if not runner.is_system else None,
            )
            bwrap_args = builder.build_bwrap_args()
            if cleaned_tool == "cmd" and not inherit_stdio:
                cmd = WineAdapter.build_run_cmd("wineconsole", args=["cmd", *(args or [])], runner=runner)
            else:
                cmd = WineAdapter.build_run_cmd(cleaned_tool, args=args, runner=runner)
            try:
                res = self.bwrap_adapter.execute_in_sandbox(
                    bwrap_args=bwrap_args,
                    command_inside=cmd,
                    inherit_stdio=inherit_stdio,
                    stream_log_file=log_file,
                    log_header=f"--- [TOOL] Starting Wine tool: {cleaned_tool} ---",
                    log_footer=f"--- [TOOL] Wine tool exited ---",
                )
                if res.returncode in (-15, -9, 143, 137):
                    # Terminated via SIGTERM/SIGKILL (e.g. user clicked Kill)
                    self.log_manager.log_event(
                        prefix_id,
                        f"Wine tool '{cleaned_tool}' terminated by signal {res.returncode}",
                        level="WARN",
                        category="TOOL",
                    )
                    return res.returncode
                if res.returncode != 0:
                    err_detail = res.stderr.strip() if res.stderr else ""
                    suffix = f": {err_detail}" if err_detail else ""
                    self.log_manager.log_event(
                        prefix_id,
                        f"Wine tool '{cleaned_tool}' failed with exit code {res.returncode}{suffix}",
                        level="ERROR",
                        category="TOOL",
                    )
                    raise WineboxError(
                        f"Wine tool '{cleaned_tool}' exited with code {res.returncode}{suffix}"
                    )
                self.log_manager.log_event(
                    prefix_id,
                    f"Wine tool '{cleaned_tool}' finished successfully (exit code 0)",
                    level="INFO",
                    category="TOOL",
                )
                return res.returncode
            except Exception as e:
                if not isinstance(e, WineboxError):
                    self.log_manager.log_event(
                        prefix_id,
                        f"Wine tool '{cleaned_tool}' execution error: {e}",
                        level="ERROR",
                        category="TOOL",
                    )
                raise
            finally:
                PrefixAuditor.sanitize_dosdevices(prefix_inner)
