"""Execution service for launching sandboxed applications."""

import os
import subprocess
from pathlib import Path
from typing import List, Optional
from winebox.common.exceptions import ResourceNotFoundError
from winebox.domain.models import Application
from winebox.infrastructure.bwrap_adapter import BwrapAdapter
from winebox.infrastructure.log_manager import LogManager
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.infrastructure.process_manager import prefix_lock
from winebox.infrastructure.wine_adapter import WineAdapter
from winebox.security.auditor import PrefixAuditor
from winebox.security.mount_builder import MountBuilder
from winebox.security.validator import PolicyValidator


class ExecutionService:
    """Orchestrates security validation, log rotation, and sandboxed process execution."""

    def __init__(
        self,
        repo: Optional[SqliteRepository] = None,
        bwrap_adapter: Optional[BwrapAdapter] = None,
        validator: Optional[PolicyValidator] = None,
    ) -> None:
        self.repo = repo or SqliteRepository()
        self.bwrap_adapter = bwrap_adapter or BwrapAdapter()
        self.validator = validator or PolicyValidator()
        self.log_manager = LogManager(prefixes_dir=self.repo.prefixes_dir)

    def run_app(
        self,
        app_id: str,
        extra_args: Optional[List[str]] = None,
        inherit_stdio: bool = True,
    ) -> subprocess.CompletedProcess:
        """Executes an application inside Bubblewrap sandbox with prefix locking and log rotation."""
        app = self.repo.load_app(app_id)
        prefix = self.repo.load_prefix(app.prefix_id)
        runner = self.repo.load_runner(app.runner_id)

        p_dir = self.repo.get_prefix_dir(prefix.id)
        prefix_inner = p_dir / "prefix"
        home_inner = p_dir / "home"

        # Validate security policy (ADR-017)
        self.validator.validate_policy(app.policy)

        with prefix_lock(p_dir):
            # Audit prefix before execution (ADR-010)
            PrefixAuditor.audit_prefix(prefix_inner, check_registry=False)

            # Compute executable working directory inside sandbox
            user_name = os.environ.get("USER", "winebox")
            sandbox_workdir: Optional[str] = None
            norm_rel = app.exe_path.replace("\\", "/")
            if norm_rel.lower().startswith("c:/"):
                norm_rel = "drive_c/" + norm_rel[3:]
            rel_parent = Path(norm_rel).parent
            if str(rel_parent) != "." and (prefix_inner / rel_parent).is_dir():
                sandbox_workdir = f"/home/{user_name}/.wine/{rel_parent.as_posix()}"

            # Build sandbox mounts (ADR-012, ADR-013, ADR-014)
            builder = MountBuilder(
                prefix_path=prefix_inner,
                isolated_home_path=home_inner,
                policy=app.policy,
                custom_runner_dir=runner.wine_bin.parent.parent if not runner.is_system else None,
                sandbox_workdir=sandbox_workdir,
            )
            bwrap_args = builder.build_bwrap_args()

            combined_args = list(app.arguments)
            if extra_args:
                combined_args.extend(extra_args)

            cmd_inside = WineAdapter.build_run_cmd(
                exe_path=app.exe_path,
                args=combined_args,
                runner=runner,
            )

            try:
                res = self.bwrap_adapter.execute_in_sandbox(
                    bwrap_args=bwrap_args,
                    command_inside=cmd_inside,
                    inherit_stdio=inherit_stdio,
                )

                # Update telemetry in database
                if hasattr(self.repo, "update_app_last_run"):
                    self.repo.update_app_last_run(app_id=app.id, exit_code=res.returncode)

                # Log execution details to rotating log file
                stdout_str = res.stdout if hasattr(res, "stdout") and res.stdout else ""
                stderr_str = res.stderr if hasattr(res, "stderr") and res.stderr else ""
                self.log_manager.log_execution(
                    prefix_id=prefix.id,
                    app_id=app.id,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    exit_code=res.returncode,
                )

                return res
            finally:
                PrefixAuditor.sanitize_dosdevices(prefix_inner)

