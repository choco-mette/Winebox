"""Prefix lifecycle, auditing, and log-reading service."""

from typing import List, Optional
from winebox.common.exceptions import WineboxError
from winebox.domain.models import Prefix, PrefixOrigin, PrefixStatus, SecurityPolicy
from winebox.infrastructure.bwrap_adapter import BwrapAdapter
from winebox.infrastructure.fs_adapter import FilesystemAdapter
from winebox.infrastructure.log_manager import LogManager
from winebox.infrastructure.process_manager import prefix_lock
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.infrastructure.wine_adapter import WineAdapter
from winebox.security.auditor import PrefixAuditor
from winebox.security.mount_builder import MountBuilder


class PrefixLifecycleService:
    """Manages creation, listing, auditing, log reading, and deletion of Wine prefixes."""

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
        log_mgr = LogManager(prefixes_dir=self.repo.prefixes_dir)
        with prefix_lock(p_dir):
            issues = PrefixAuditor.audit_prefix(prefix_inner, check_registry=False)
            if issues:
                log_mgr.log_event(
                    prefix_id,
                    f"Security audit detected {len(issues)} issue(s): {'; '.join(issues)}",
                    level="WARN",
                    category="AUDIT",
                )
            else:
                log_mgr.log_event(
                    prefix_id,
                    "Security audit passed with zero issues",
                    level="INFO",
                    category="AUDIT",
                )
            return issues

    def remove_prefix(self, prefix_id: str) -> None:
        p_dir = self.repo.get_prefix_dir(prefix_id)
        if not p_dir.exists():
            raise WineboxError(f"Prefix '{prefix_id}' does not exist at {p_dir}")
        with prefix_lock(p_dir):
            self.repo.delete_prefix(prefix_id)

    def read_logs(self, prefix_id: str, max_lines: int = 50) -> List[str]:
        log_mgr = LogManager(prefixes_dir=self.repo.prefixes_dir)
        return log_mgr.read_logs(prefix_id=prefix_id, max_lines=max_lines)

    def clear_logs(self, prefix_id: str) -> None:
        log_mgr = LogManager(prefixes_dir=self.repo.prefixes_dir)
        log_mgr.clear_logs(prefix_id=prefix_id)
