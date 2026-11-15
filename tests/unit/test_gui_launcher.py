"""Unit tests for the GTK4 + Libadwaita GUI Launcher state, safety helpers, and CLI entrypoint."""

import builtins
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from winebox.common.exceptions import WineboxError
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.interface.cli import app
from winebox.interface.gui import launch_gui
from winebox.interface.gui.state import ServiceContainer, format_size, list_prefix_directory


class TestGuiStateAndFileManager(unittest.TestCase):
    def test_list_prefix_directory_sorting_and_symlink_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "drive_c"
            (root / "Program Files").mkdir(parents=True)
            (root / "app.exe").write_bytes(b"MZ" * 100)
            (root / "readme.txt").write_text("hi")
            (root / "escape_link").symlink_to("/etc/passwd")

            entries = list_prefix_directory(root)
            self.assertEqual([e.name for e in entries], ["Program Files", "app.exe", "escape_link", "readme.txt"])
            self.assertTrue(entries[0].is_dir)
            self.assertFalse(entries[0].is_symlink)
            self.assertTrue(entries[2].is_symlink)
            self.assertFalse(entries[2].is_dir)

            with self.assertRaises(WineboxError):
                list_prefix_directory(root, "../outside")
            with self.assertRaises(WineboxError):
                list_prefix_directory(root, "/etc")

    def test_format_size_and_service_container(self) -> None:
        self.assertEqual(format_size(512), "512 B")
        self.assertEqual(format_size(2048), "2.0 KB")
        with tempfile.TemporaryDirectory() as tmp:
            repo = SqliteRepository(
                data_root=Path(tmp) / "data",
                config_root=Path(tmp) / "cfg",
            )
            container = ServiceContainer(repo=repo)
            self.assertEqual(container.repo, repo)
            self.assertGreaterEqual(len(container.profile_svc.list_profiles()), 4)


class TestGuiCliAndApp(unittest.TestCase):
    def setUp(self) -> None:
        self.cli = CliRunner()

    def test_gui_help(self) -> None:
        res = self.cli.invoke(app, ["gui", "--help"])
        self.assertEqual(res.exit_code, 0)
        self.assertIn("GTK4", res.output)

    def test_launch_gui_raises_clear_error_when_gi_missing(self) -> None:
        real_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "gi":
                raise ImportError("No module named 'gi'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(WineboxError) as ctx:
                launch_gui()
            self.assertIn("PyGObject", str(ctx.exception))

    def test_gtk4_modules_import_and_window_instantiates_when_display_available(self) -> None:
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            self.skipTest("No active X11/Wayland display for GTK4 widget instantiation")
        try:
            import gi

            gi.require_version("Gtk", "4.0")
            gi.require_version("Adw", "1")
        except (ImportError, ValueError):
            self.skipTest("GTK4 / Libadwaita not available")

        from gi.repository import Gio
        from winebox.interface.gui.app import WineboxGuiApp

        with tempfile.TemporaryDirectory() as tmp:
            repo = SqliteRepository(data_root=Path(tmp) / "data", config_root=Path(tmp) / "cfg")
            gui_app = WineboxGuiApp(services=ServiceContainer(repo=repo))
            gui_app.set_flags(Gio.ApplicationFlags.NON_UNIQUE)
            self.assertEqual(gui_app.get_application_id(), "id.winebox.WineBox")
            gui_app.register(None)
            gui_app.activate()
            win = gui_app._window
            assert win is not None
            for page in win.pages.values():
                page.refresh()
            win.close()


if __name__ == "__main__":
    unittest.main()
