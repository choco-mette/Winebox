"""Application registration and metadata management service."""

from typing import Any, Dict, List, Optional
from winebox.application.desktop_service import DesktopService
from winebox.common.exceptions import WineboxError
from winebox.domain.models import Application, SecurityPolicy, ShortcutSettings
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.security.validator import PolicyValidator


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

    def update_app(
        self,
        app_id: str,
        name: Optional[str] = None,
        exe_path: Optional[str] = None,
        runner_id: Optional[str] = None,
        profile_id: Optional[str] = None,
        arguments: Optional[List[str]] = None,
        policy: Optional[SecurityPolicy] = None,
        shortcut: Optional[ShortcutSettings] = None,
    ) -> Application:
        """Update registered application metadata, runner, launch arguments, policy, or shortcut."""
        app = self.repo.load_app(app_id)
        if name is not None:
            cleaned = name.strip()
            if not cleaned:
                raise WineboxError("Application name cannot be empty.")
            app.name = cleaned
        if exe_path is not None:
            cleaned_exe = exe_path.strip()
            if not cleaned_exe:
                raise WineboxError("Executable path cannot be empty.")
            app.exe_path = cleaned_exe
        if runner_id is not None:
            self.repo.load_runner(runner_id)
            app.runner_id = runner_id
        if profile_id is not None:
            self.repo.load_profile(profile_id)
            app.profile_id = profile_id
        if arguments is not None:
            app.arguments = list(arguments)
        if policy is not None:
            PolicyValidator().validate_policy(policy)
            app.policy = policy
        if shortcut is not None:
            app.shortcut = shortcut
        self.repo.save_app(app)
        return app

    def remove_app(self, app_id: str) -> None:
        try:
            ds = DesktopService(self.repo)
            ds.remove_desktop_entry(app_id)
            ds.remove_desktop_icon(app_id)
        except (OSError, WineboxError):
            pass
        self.repo.delete_app(app_id)

    def kill_app(self, app_id: str, force: bool = False) -> Dict[str, Any]:
        """Terminate all running processes in the application's prefix (ADR-025)."""
        app = self.get_app(app_id)
        from winebox.application.prefix_service import PrefixService
        return PrefixService(self.repo).kill_prefix(app.prefix_id, force=force)

