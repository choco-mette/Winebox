"""XDG Desktop Entry adapter for managing Freedesktop .desktop files (ADR-024 & ADR-025)."""

import os
import subprocess
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

    @staticmethod
    def get_desktop_dir() -> Path:
        """Return the user's XDG Desktop directory (KDE/XFCE/MATE/Cinnamon/GNOME DING)."""
        env_desktop = os.environ.get("XDG_DESKTOP_DIR")
        if env_desktop:
            return Path(os.path.expandvars(env_desktop)).expanduser()
        user_dirs = Path.home() / ".config" / "user-dirs.dirs"
        if user_dirs.is_file():
            try:
                for line in user_dirs.read_text(encoding="utf-8", errors="ignore").splitlines():
                    stripped = line.strip()
                    if stripped.startswith("XDG_DESKTOP_DIR="):
                        val = stripped.split("=", 1)[1].strip().strip('"').strip("'")
                        val = val.replace("$HOME", str(Path.home()))
                        if val:
                            return Path(val).expanduser()
            except OSError:
                pass
        return Path.home() / "Desktop"

    @classmethod
    def desktop_entry_path(cls, app_id: str, apps_dir: Optional[Path] = None) -> Path:
        """Return the target Path for a given app ID's .desktop file."""
        target_dir = apps_dir or cls.get_applications_dir()
        return target_dir / f"winebox-{app_id}.desktop"

    @classmethod
    def desktop_icon_path(cls, app_id: str, desktop_dir: Optional[Path] = None) -> Path:
        """Return the target Path for a given app ID's Desktop folder .desktop icon."""
        target_dir = desktop_dir or cls.get_desktop_dir()
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
        terminal: bool = False,
        startup_wm_class: Optional[str] = None,
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
            f"Terminal={'true' if terminal else 'false'}",
            f"Categories={categories}",
            "StartupNotify=true",
            f"Comment={desc}",
        ]
        if startup_wm_class and startup_wm_class.strip():
            lines.append(f"StartupWMClass={startup_wm_class.strip()}")
        lines.extend(
            [
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
        )
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
        terminal: bool = False,
        startup_wm_class: Optional[str] = None,
        target_path: Optional[Path] = None,
        mark_trusted: bool = False,
    ) -> Path:
        """Write the .desktop entry file into the target directory."""
        dest_path = target_path or cls.desktop_entry_path(app_id, apps_dir=apps_dir)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        content = cls.generate_content(
            app_id=app_id,
            name=name,
            icon=icon,
            categories=categories,
            comment=comment,
            prefix_id=prefix_id,
            terminal=terminal,
            startup_wm_class=startup_wm_class,
        )
        dest_path.write_text(content, encoding="utf-8")
        dest_path.chmod(0o755)
        if mark_trusted:
            try:
                subprocess.run(
                    ["gio", "set", str(dest_path), "metadata::trusted", "true"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError:
                pass
        return dest_path

    @classmethod
    def remove_desktop_entry(cls, app_id: str, apps_dir: Optional[Path] = None) -> bool:
        """Remove the .desktop entry file if it exists. Returns True if removed."""
        dest_path = cls.desktop_entry_path(app_id, apps_dir=apps_dir)
        if dest_path.exists():
            dest_path.unlink()
            return True
        return False

    @classmethod
    def remove_desktop_icon(cls, app_id: str, desktop_dir: Optional[Path] = None) -> bool:
        """Remove the Desktop folder .desktop icon if it exists. Returns True if removed."""
        dest_path = cls.desktop_icon_path(app_id, desktop_dir=desktop_dir)
        if dest_path.exists():
            dest_path.unlink()
            return True
        return False
