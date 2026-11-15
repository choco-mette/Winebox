"""Lutris integration service for exporting WineBox apps to Lutris GUI."""

from pathlib import Path
from typing import Optional
from winebox.infrastructure.lutris_adapter import LutrisAdapter
from winebox.infrastructure.sqlite_repository import SqliteRepository


class LutrisService:
    """Manages exporting registered WineBox applications into Lutris."""

    def __init__(
        self,
        repo: Optional[SqliteRepository] = None,
        adapter: Optional[LutrisAdapter] = None,
    ) -> None:
        self.repo = repo or SqliteRepository()
        self.adapter = adapter or LutrisAdapter()
        self.lutris_dir = self.repo.data_root / "lutris"
        self.lutris_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def is_available() -> bool:
        """Returns True if the Lutris binary is installed on the host."""
        return LutrisAdapter.find_lutris_binary() is not None

    def export_app_to_lutris(self, app_id: str, launch_lutris: bool = True) -> Path:
        """Generates the Lutris YAML script for an app and optionally invokes lutris --install."""
        app = self.repo.load_app(app_id)
        yaml_path = self.adapter.generate_installer_yaml(app, self.lutris_dir)
        if launch_lutris:
            self.adapter.launch_installer(yaml_path)
        return yaml_path

