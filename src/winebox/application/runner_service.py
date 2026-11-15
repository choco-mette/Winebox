"""Wine runner application service."""

from pathlib import Path
from typing import List, Optional
from winebox.domain.models import Runner
from winebox.infrastructure.sqlite_repository import SqliteRepository


class RunnerService:
    """Manages system and custom Wine runners."""

    def __init__(self, repo: Optional[SqliteRepository] = None) -> None:
        self.repo = repo or SqliteRepository()

    def list_runners(self) -> List[Runner]:
        return self.repo.list_runners()

    def get_runner(self, runner_id: str) -> Runner:
        return self.repo.load_runner(runner_id)

    def register_custom_runner(
        self,
        runner_id: str,
        name: str,
        wine_bin: Path,
        wineserver_bin: Optional[Path] = None,
    ) -> Runner:
        resolved_wine = wine_bin.resolve()
        resolved_wineserver = wineserver_bin.resolve() if wineserver_bin else None

        runner = Runner(
            id=runner_id,
            name=name,
            wine_bin=resolved_wine,
            wineserver_bin=resolved_wineserver,
            is_system=False,
        )
        self.repo.save_runner(runner)
        return runner

