"""Application registration and metadata management service."""

from typing import List, Optional
from winebox.domain.models import Application, SecurityPolicy
from winebox.infrastructure.config_repository import ConfigRepository


class AppService:
    """Manages application registration, inspection, and removal."""

    def __init__(self, repo: Optional[ConfigRepository] = None) -> None:
        self.repo = repo or ConfigRepository()

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
        policy: Optional[SecurityPolicy] = None,
        arguments: Optional[List[str]] = None,
    ) -> Application:
        app = Application(
            id=app_id,
            name=name,
            prefix_id=prefix_id,
            exe_path=exe_path,
            runner_id=runner_id,
            arguments=arguments or [],
            policy=policy or SecurityPolicy(),
        )
        self.repo.save_app(app)
        return app

    def remove_app(self, app_id: str) -> None:
        self.repo.delete_app(app_id)
