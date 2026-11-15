"""Application registration and metadata management service."""

from typing import Any, Dict, List, Optional
from winebox.application.desktop_service import DesktopService
from winebox.common.exceptions import WineboxError
from winebox.domain.models import Application, SecurityPolicy
from winebox.infrastructure.sqlite_repository import SqliteRepository


class AppService:
    """Manages application registration, inspection, and removal."""

    def __init__(self, repo: Optional[SqliteRepository] = None) -> None:
        self.repo = repo or SqliteRepository()

    def list_apps(self) -> List[Application]:
        return self.repo.list_apps()

    def get_app(self, app_id: str) -> Application:
        return self.repo.load_app(app_id)

    def register_app(
        self,
        app_id: str,
        name: str,
        prefix_id: str,
        exe_path: str,
        runner_id: str = "system-wine",
        profile_id: str = "permissive",
        policy: Optional[SecurityPolicy] = None,
        arguments: Optional[List[str]] = None,
    ) -> Application:
        app = Application(
            id=app_id,
            name=name,
            prefix_id=prefix_id,
            exe_path=exe_path,
            runner_id=runner_id,
            profile_id=profile_id,
            arguments=arguments or [],
            policy=policy or SecurityPolicy(),
        )
        self.repo.save_app(app)
        return app

    def remove_app(self, app_id: str) -> None:
        try:
            DesktopService(self.repo).remove_desktop_entry(app_id)
        except (OSError, WineboxError):
            pass
        self.repo.delete_app(app_id)

    def kill_app(self, app_id: str, force: bool = False) -> Dict[str, Any]:
        """Terminate all running processes in the application's prefix (ADR-025)."""
        app = self.get_app(app_id)
        from winebox.application.prefix_service import PrefixService
        return PrefixService(self.repo).kill_prefix(app.prefix_id, force=force)

