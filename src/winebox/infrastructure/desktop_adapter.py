"""XDG Desktop Entry adapter for managing Freedesktop .desktop files (ADR-024 & ADR-025)."""

import os
from pathlib import Path
from typing import Optional


class DesktopAdapter:
    """Handles Freedesktop .desktop file generation, placement, and removal."""

    @staticmethod
    def get_applications_dir() -> Path:
        """Return the user's XDG applications directory."""
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            base = Path(xdg_data)
        else:
            base = Path.home() / ".local" / "share"
        return base / "applications"

    @classmethod
    def desktop_entry_path(cls, app_id: str, apps_dir: Optional[Path] = None) -> Path:
        """Return the target Path for a given app ID's .desktop file."""
        target_dir = apps_dir or cls.get_applications_dir()
        return target_dir / f"winebox-{app_id}.desktop"

    @classmethod
    def generate_content(
        cls,
        app_id: str,
        name: str,
        icon: str = "wine",
        categories: str = "Game;Utility;",
        comment: Optional[str] = None,
        prefix_id: Optional[str] = None,
    ) -> str:
        """Generate valid INI content for the .desktop entry."""
        desc = comment or f"Run {name} in Winebox sandbox"
        kill_cmd = f"winebox prefix kill {prefix_id}" if prefix_id else f"winebox app kill {app_id}"
        lines = [
            "[Desktop Entry]",
            "Type=Application",
            f"Name={name}",
            f"Exec=winebox app run {app_id}",
            f"Icon={icon}",
            "Terminal=false",
            f"Categories={categories}",
            "StartupNotify=true",
            f"Comment={desc}",
            "Actions=Configure;Kill;",
            "",
            "[Desktop Action Configure]",
            "Name=WineBox App Info",
            f"Exec=winebox app info {app_id}",
            "",
            "[Desktop Action Kill]",
            "Name=Stop / Kill Process",
            f"Exec={kill_cmd}",
            "",
        ]
        return "\n".join(lines)

    @classmethod
    def write_desktop_entry(
        cls,
        app_id: str,
        name: str,
        icon: str = "wine",
        categories: str = "Game;Utility;",
        comment: Optional[str] = None,
        prefix_id: Optional[str] = None,
        apps_dir: Optional[Path] = None,
    ) -> Path:
        """Write the .desktop entry file into the applications directory."""
        dest_path = cls.desktop_entry_path(app_id, apps_dir=apps_dir)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        content = cls.generate_content(
            app_id=app_id,
            name=name,
            icon=icon,
            categories=categories,
            comment=comment,
            prefix_id=prefix_id,
        )
        dest_path.write_text(content, encoding="utf-8")
        dest_path.chmod(0o755)
        return dest_path

    @classmethod
    def remove_desktop_entry(cls, app_id: str, apps_dir: Optional[Path] = None) -> bool:
        """Remove the .desktop entry file if it exists. Returns True if removed."""
        dest_path = cls.desktop_entry_path(app_id, apps_dir=apps_dir)
        if dest_path.exists():
            dest_path.unlink()
            return True
        return False
