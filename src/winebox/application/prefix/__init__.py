"""Modular prefix application services package with backward-compatible PrefixService facade."""

from pathlib import Path
from typing import Any, Dict, List, Optional
from winebox.application.prefix.backup import PrefixBackupService
from winebox.application.prefix.lifecycle import PrefixLifecycleService
from winebox.application.prefix.runtime import PrefixRuntimeService
from winebox.domain.models import Prefix
from winebox.infrastructure.bwrap_adapter import BwrapAdapter
from winebox.infrastructure.sqlite_repository import SqliteRepository


class PrefixService:
    """Thin facade delegating prefix lifecycle, runtime control, and backup operations."""

    ALLOWED_WINE_TOOLS = PrefixRuntimeService.ALLOWED_WINE_TOOLS

    def __init__(
        self,
        repo: Optional[SqliteRepository] = None,
        bwrap_adapter: Optional[BwrapAdapter] = None,
    ) -> None:
        self.repo = repo or SqliteRepository()
        self.bwrap_adapter = bwrap_adapter or BwrapAdapter()
        self.lifecycle = PrefixLifecycleService(repo=self.repo, bwrap_adapter=self.bwrap_adapter)
        self.runtime = PrefixRuntimeService(repo=self.repo, bwrap_adapter=self.bwrap_adapter)
        self.backup = PrefixBackupService(repo=self.repo)

    def create_prefix(
        self,
        prefix_id: str,
        name: Optional[str] = None,
        runner_id: str = "system-wine",
        default_profile_id: str = "permissive",
        initialize_wineboot: bool = True,
        allow_network: bool = True,
    ) -> Prefix:
        return self.lifecycle.create_prefix(
            prefix_id=prefix_id,
            name=name,
            runner_id=runner_id,
            default_profile_id=default_profile_id,
            initialize_wineboot=initialize_wineboot,
            allow_network=allow_network,
        )

    def list_prefixes(self) -> List[Prefix]:
        return self.lifecycle.list_prefixes()

    def get_prefix(self, prefix_id: str) -> Prefix:
        return self.lifecycle.get_prefix(prefix_id)

    def audit_prefix(self, prefix_id: str) -> List[str]:
        return self.lifecycle.audit_prefix(prefix_id)

    def remove_prefix(self, prefix_id: str) -> None:
        self.lifecycle.remove_prefix(prefix_id)

    def read_logs(self, prefix_id: str, max_lines: int = 50) -> List[str]:
        return self.lifecycle.read_logs(prefix_id, max_lines=max_lines)

    def kill_prefix(self, prefix_id: str, force: bool = False) -> Dict[str, Any]:
        return self.runtime.kill_prefix(prefix_id, force=force)

    def run_tool(
        self,
        prefix_id: str,
        tool_name: str,
        args: Optional[List[str]] = None,
        inherit_stdio: bool = True,
    ) -> int:
        return self.runtime.run_tool(prefix_id, tool_name, args=args, inherit_stdio=inherit_stdio)

    def list_backups(self) -> List[Dict[str, Any]]:
        return self.backup.list_backups()

    def backup_prefix(self, prefix_id: str, output_path: Optional[Path] = None) -> Path:
        return self.backup.backup_prefix(prefix_id, output_path=output_path)

    def restore_prefix(
        self,
        archive_path: Path,
        target_prefix_id: Optional[str] = None,
        force: bool = False,
    ) -> Prefix:
        return self.backup.restore_prefix(archive_path, target_prefix_id=target_prefix_id, force=force)


__all__ = [
    "PrefixBackupService",
    "PrefixLifecycleService",
    "PrefixRuntimeService",
    "PrefixService",
]
