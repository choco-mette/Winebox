"""Application service for XDG Desktop Entry creation and lifecycle management (ADR-024)."""

from pathlib import Path
from typing import Dict, Optional
from winebox.common.exceptions import WineboxError
from winebox.domain.models import Application
from winebox.infrastructure.desktop_adapter import DesktopAdapter
from winebox.infrastructure.sqlite_repository import SqliteRepository


class DesktopService:
    """Orchestrates creation, inspection, and deletion of XDG .desktop entries."""

    def __init__(
        self,
        repo: Optional[SqliteRepository] = None,
        apps_dir: Optional[Path] = None,
        desktop_dir: Optional[Path] = None,
    ) -> None:
        self.repo = repo or SqliteRepository()
        self.apps_dir = apps_dir
        self.desktop_dir = desktop_dir

    def get_desktop_entry_path(self, app_id: str) -> Path:
        """Return the .desktop file path in the applications menu directory."""
        return DesktopAdapter.desktop_entry_path(app_id, apps_dir=self.apps_dir)

    def get_desktop_icon_path(self, app_id: str) -> Path:
        """Return the .desktop file path in the user's Desktop directory."""
        return DesktopAdapter.desktop_icon_path(app_id, desktop_dir=self.desktop_dir)

    def desktop_entry_exists(self, app_id: str) -> bool:
        """Check if an application menu .desktop entry exists for the given app ID."""
        return self.get_desktop_entry_path(app_id).exists()

    def desktop_icon_exists(self, app_id: str) -> bool:
        """Check if a Desktop folder .desktop icon exists for the given app ID."""
        return self.get_desktop_icon_path(app_id).exists()

    def _resolve_icon(self, app: Application, icon_override: Optional[str] = None) -> str:
        chosen_icon = (icon_override or app.shortcut.icon or "").strip()
        if chosen_icon:
            return chosen_icon
        try:
            prefix_root = (
                getattr(self.repo, "prefixes_dir", Path.home() / ".local/share/winebox/prefixes")
                / app.prefix_id
                / "prefix"
            )
            exe_dir = (prefix_root / app.exe_path).parent
            for candidate_name in ("icon.png", f"{app.id}.png", f"{Path(app.exe_path).stem}.png"):
                candidate_path = exe_dir / candidate_name
                if candidate_path.exists():
                    return str(candidate_path.resolve())
        except (OSError, WineboxError):
            pass
        return "wine"

    def sync_shortcuts(self, app_id: str) -> Dict[str, Optional[Path]]:
        """Synchronize XDG Menu and Desktop folder .desktop files from SQLite ShortcutSettings."""
        app = self.repo.load_app(app_id)
        sc = app.shortcut
        icon = self._resolve_icon(app)
        categories = sc.categories.strip() or "Game;Utility;"
        comment = sc.comment.strip() or None
        wm_class = sc.startup_wm_class.strip() or None

        menu_path: Optional[Path] = None
        if sc.menu_enabled:
            menu_path = DesktopAdapter.write_desktop_entry(
                app_id=app.id,
                name=app.name,
                icon=icon,
                categories=categories,
                comment=comment,
                prefix_id=app.prefix_id,
                apps_dir=self.apps_dir,
                terminal=sc.terminal,
                startup_wm_class=wm_class,
            )
        else:
            DesktopAdapter.remove_desktop_entry(app.id, apps_dir=self.apps_dir)

        desktop_path: Optional[Path] = None
        if sc.desktop_enabled:
            desktop_path = DesktopAdapter.write_desktop_entry(
                app_id=app.id,
                name=app.name,
                icon=icon,
                categories=categories,
                comment=comment,
                prefix_id=app.prefix_id,
                terminal=sc.terminal,
                startup_wm_class=wm_class,
                target_path=self.get_desktop_icon_path(app.id),
                mark_trusted=True,
            )
        else:
            DesktopAdapter.remove_desktop_icon(app.id, desktop_dir=self.desktop_dir)

        return {"menu": menu_path, "desktop": desktop_path}

    def create_desktop_entry(
        self,
        app_id: str,
        icon: Optional[str] = None,
        categories: Optional[str] = None,
    ) -> Path:
        """Create or update a Freedesktop .desktop entry for a registered application."""
        app = self.repo.load_app(app_id)
        if icon is not None:
            app.shortcut.icon = icon
        if categories is not None:
            app.shortcut.categories = categories
        app.shortcut.menu_enabled = True
        self.repo.save_app(app)

        chosen_icon = self._resolve_icon(app, icon_override=icon)
        chosen_categories = (categories or app.shortcut.categories or "Game;Utility;").strip()
        return DesktopAdapter.write_desktop_entry(
            app_id=app.id,
            name=app.name,
            icon=chosen_icon,
            categories=chosen_categories,
            comment=app.shortcut.comment.strip() or None,
            prefix_id=app.prefix_id,
            apps_dir=self.apps_dir,
            terminal=app.shortcut.terminal,
            startup_wm_class=app.shortcut.startup_wm_class.strip() or None,
        )

    def remove_desktop_entry(self, app_id: str) -> bool:
        """Remove the menu .desktop entry for the given app ID and update SQLite flag."""
        try:
            app = self.repo.load_app(app_id)
            if app.shortcut.menu_enabled:
                app.shortcut.menu_enabled = False
                self.repo.save_app(app)
        except (OSError, WineboxError):
            pass
        return DesktopAdapter.remove_desktop_entry(app_id, apps_dir=self.apps_dir)

    def remove_desktop_icon(self, app_id: str) -> bool:
        """Remove the Desktop folder .desktop icon if it exists."""
        return DesktopAdapter.remove_desktop_icon(app_id, desktop_dir=self.desktop_dir)
