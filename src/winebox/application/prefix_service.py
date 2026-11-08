"""Prefix lifecycle application service."""

from pathlib import Path
from typing import List, Optional
from winebox.common.exceptions import PrefixAuditError, WineboxError
from winebox.domain.models import Prefix, PrefixOrigin, PrefixStatus, SecurityPolicy
from winebox.infrastructure.bwrap_adapter import BwrapAdapter
from winebox.infrastructure.config_repository import ConfigRepository
from winebox.infrastructure.process_manager import prefix_lock
from winebox.infrastructure.wine_adapter import WineAdapter
from winebox.security.auditor import PrefixAuditor
from winebox.security.mount_builder import MountBuilder


class PrefixService:
    """Manages creation, auditing, and deletion of Wine prefixes."""

    def __init__(
        self,
        repo: Optional[ConfigRepository] = None,
        bwrap_adapter: Optional[BwrapAdapter] = None,
    ) -> None:
        self.repo = repo or ConfigRepository()
        self.bwrap_adapter = bwrap_adapter or BwrapAdapter()

    def create_prefix(
        self,
        prefix_id: str,
        name: Optional[str] = None,
        runner_id: str = "system-wine",
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

