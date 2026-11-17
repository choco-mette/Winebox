"""Winetricks service for executing package installations in Bubblewrap with shared cache."""

import os
from pathlib import Path
from typing import List, Optional
from winebox.common.exceptions import WineboxError
from winebox.domain.models import HostMount, MountMode, SecurityPolicy
from winebox.infrastructure.bwrap_adapter import BwrapAdapter
from winebox.infrastructure.log_manager import LogManager
from winebox.infrastructure.process_manager import prefix_lock
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.infrastructure.winetricks_adapter import WinetricksAdapter
from winebox.security.auditor import PrefixAuditor
from winebox.security.mount_builder import MountBuilder


class WinetricksService:
    """Orchestrates sandboxed Winetricks execution with shared cache across prefixes."""

    def __init__(
        self,
        repo: Optional[SqliteRepository] = None,
        bwrap_adapter: Optional[BwrapAdapter] = None,
        adapter: Optional[WinetricksAdapter] = None,
        log_manager: Optional[LogManager] = None,
    ) -> None:
        self.repo = repo or SqliteRepository()
        self.bwrap_adapter = bwrap_adapter or BwrapAdapter()
        self.adapter = adapter or WinetricksAdapter()
        self.log_manager = log_manager or LogManager(prefixes_dir=self.repo.prefixes_dir)

        self.shared_cache_dir = self.repo.data_root / "cache" / "winetricks"
        self.shared_cache_dir.mkdir(parents=True, exist_ok=True)

    def run_winetricks(
        self,
        prefix_id: str,
        verbs: Optional[List[str]] = None,
        unattended: bool = True,
        inherit_stdio: bool = True,
    ) -> None:
        """Executes Winetricks inside the sandbox targeting the specified prefix."""
        prefix = self.repo.load_prefix(prefix_id)
        runner = self.repo.load_runner(prefix.runner_id)

        p_dir = self.repo.get_prefix_dir(prefix.id)
        prefix_inner = p_dir / "prefix"
        home_inner = p_dir / "home"

        user_name = os.environ.get("USER", "winebox")
        sandbox_cache_dir = Path(f"/home/{user_name}/.cache/winetricks")

        cache_mount = HostMount(
            host_path=self.shared_cache_dir,
            sandbox_path=sandbox_cache_dir,
            mode=MountMode.RW,
        )

        # Winetricks needs network for downloading and display for dialogs
        policy = SecurityPolicy(
            network=True,
            display=True,
            host_mounts=[cache_mount],
        )

        verbs_str = ", ".join(verbs) if verbs else "(GUI menu)"
        self.log_manager.log_event(
            prefix_id,
            f"Starting Winetricks with verbs: {verbs_str}",
            level="INFO",
            category="WINETRICKS",
        )
        log_file = self.log_manager.get_log_file(prefix.id)

        with prefix_lock(p_dir):
            with prefix_lock(self.shared_cache_dir):
                builder = MountBuilder(
                    prefix_path=prefix_inner,
                    isolated_home_path=home_inner,
                    policy=policy,
                    custom_runner_dir=runner.wine_bin.parent.parent if not runner.is_system else None,
                    sandbox_workdir=f"/home/{user_name}/.wine/drive_c",
                )
                bwrap_args = builder.build_bwrap_args()
                winetricks_cmd = self.adapter.build_winetricks_cmd(
                    verbs=verbs or [],
                    runner=runner,
                    unattended=unattended,
                )

                try:
                    res = self.bwrap_adapter.execute_in_sandbox(
                        bwrap_args=bwrap_args,
                        command_inside=winetricks_cmd,
                        inherit_stdio=inherit_stdio,
                        stream_log_file=log_file,
                        log_header=f"--- [WINETRICKS] Starting Winetricks: {verbs_str} ---",
                        log_footer=f"--- [WINETRICKS] Winetricks exited ---",
                    )

                    if res.returncode != 0:
                        self.log_manager.log_event(
                            prefix_id,
                            f"Winetricks failed with exit code {res.returncode}",
                            level="ERROR",
                            category="WINETRICKS",
                        )
                        raise WineboxError(f"Winetricks execution failed with exit code {res.returncode}")

                    self.log_manager.log_event(
                        prefix_id,
                        f"Winetricks completed successfully: {verbs_str}",
                        level="INFO",
                        category="WINETRICKS",
                    )
                except Exception as e:
                    if not isinstance(e, WineboxError):
                        self.log_manager.log_event(
                            prefix_id,
                            f"Winetricks exception: {e}",
                            level="ERROR",
                            category="WINETRICKS",
                        )
                    raise
                finally:
                    # Auto-sanitize prefix after winetricks finishes
                    PrefixAuditor.sanitize_dosdevices(prefix_inner)
