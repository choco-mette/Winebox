"""Application service for XDG Desktop Entry creation and lifecycle management (ADR-024)."""

from pathlib import Path
from typing import Any, Optional
from winebox.infrastructure.desktop_adapter import DesktopAdapter
from winebox.infrastructure.sqlite_repository import SqliteRepository


class DesktopService:
    """Orchestrates creation, inspection, and deletion of XDG .desktop entries."""

    def __init__(self, repo: Optional[Any] = None, apps_dir: Optional[Path] = None) -> None:
        self.repo = repo or SqliteRepository()
        self.apps_dir = apps_dir

    def get_desktop_entry_path(self, app_id: str) -> Path:
        """Return the .desktop file path for the given app ID."""
        return DesktopAdapter.desktop_entry_path(app_id, apps_dir=self.apps_dir)

    def desktop_entry_exists(self, app_id: str) -> bool:
        """Check if a .desktop entry exists for the given app ID."""
        return self.get_desktop_entry_path(app_id).exists()

    def create_desktop_entry(
        self,
        app_id: str,
        icon: Optional[str] = None,
        categories: Optional[str] = None,
    ) -> Path:
        """Create or update a Freedesktop .desktop entry for a registered application."""
        app = self.repo.load_app(app_id)

        # Resolve icon
        chosen_icon = icon
        if not chosen_icon:
            # Check if there is an icon file alongside the executable in the prefix
            try:
                prefix_root = getattr(self.repo, "prefixes_dir", Path.home() / ".local/share/winebox/prefixes") / app.prefix_id / "prefix"
                exe_full = prefix_root / app.exe_path
                exe_dir = exe_full.parent
                for candidate_name in ("icon.png", f"{app.id}.png", f"{Path(app.exe_path).stem}.png"):
                    candidate_path = exe_dir / candidate_name
                    if candidate_path.exists():
                        chosen_icon = str(candidate_path.resolve())
                        break
            except Exception:
                pass

        if not chosen_icon:
            chosen_icon = "wine"

        chosen_categories = categories or "Game;Utility;"

        return DesktopAdapter.write_desktop_entry(
            app_id=app.id,
            name=app.name,
            icon=chosen_icon,
            categories=chosen_categories,
            apps_dir=self.apps_dir,
        )

    def remove_desktop_entry(self, app_id: str) -> bool:
        """Remove the .desktop entry for the given app ID if it exists."""
        return DesktopAdapter.remove_desktop_entry(app_id, apps_dir=self.apps_dir)
