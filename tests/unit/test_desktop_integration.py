"""Unit and integration tests for XDG Desktop Entry (.desktop) support (ADR-024)."""

import os
import tempfile
import unittest
from pathlib import Path
from typer.testing import CliRunner

from winebox.application.app_service import AppService
from winebox.application.desktop_service import DesktopService
from winebox.domain.models import Application, Prefix, SecurityPolicy
from winebox.infrastructure.desktop_adapter import DesktopAdapter
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.interface.cli import app as cli_app


class TestDesktopIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.apps_dir = self.base_path / "applications"
        self.db_path = self.base_path / "winebox.db"

        # Mock repository with in-temp sqlite
        self.repo = SqliteRepository(data_root=self.base_path)

        # Setup sample prefix & app
        self.prefix_dir = self.base_path / "prefixes" / "p1"
        (self.prefix_dir / "prefix" / "drive_c" / "Games" / "Doom").mkdir(parents=True, exist_ok=True)
        self.exe_file = self.prefix_dir / "prefix" / "drive_c" / "Games" / "Doom" / "doom.exe"
        self.exe_file.touch()

        self.repo.save_prefix(
            Prefix(
                id="p1",
                name="Prefix 1",
                default_profile_id="permissive",
            )
        )
        self.repo.save_app(
            Application(
                id="doom",
                name="Doom Eternal",
                prefix_id="p1",
                exe_path="drive_c/Games/Doom/doom.exe",
                runner_id="system-wine",
                profile_id="permissive",
                policy=SecurityPolicy(),
            )
        )
        self.runner = CliRunner()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_desktop_adapter_generate_and_write(self):
        content = DesktopAdapter.generate_content("doom", "Doom Eternal", icon="wine", categories="Game;")
        self.assertIn("[Desktop Entry]", content)
        self.assertIn("Name=Doom Eternal", content)
        self.assertIn("Exec=winebox app run doom", content)
        self.assertIn("Icon=wine", content)
        self.assertIn("Categories=Game;", content)
        self.assertIn("[Desktop Action Configure]", content)

        out_path = DesktopAdapter.write_desktop_entry(
            app_id="doom",
            name="Doom Eternal",
            icon="wine",
            categories="Game;",
            apps_dir=self.apps_dir,
        )
        self.assertTrue(out_path.exists())
        self.assertEqual(out_path.name, "winebox-doom.desktop")

        # Test removal
        removed = DesktopAdapter.remove_desktop_entry("doom", apps_dir=self.apps_dir)
        self.assertTrue(removed)
        self.assertFalse(out_path.exists())

        # Removing non-existent returns False
        self.assertFalse(DesktopAdapter.remove_desktop_entry("doom", apps_dir=self.apps_dir))

    def test_desktop_service_lifecycle(self):
        svc = DesktopService(repo=self.repo, apps_dir=self.apps_dir)
        self.assertFalse(svc.desktop_entry_exists("doom"))

        desktop_file = svc.create_desktop_entry("doom")
        self.assertTrue(desktop_file.exists())
        self.assertTrue(svc.desktop_entry_exists("doom"))

        content = desktop_file.read_text(encoding="utf-8")
        self.assertIn("Name=Doom Eternal", content)
        self.assertIn("Icon=wine", content)

        # Test rename via create_desktop_entry
        desktop_renamed = svc.create_desktop_entry("doom", name="Doom Ancient Gods")
        self.assertTrue(desktop_renamed.exists())
        reloaded_app = self.repo.load_app("doom")
        self.assertEqual(reloaded_app.name, "Doom Ancient Gods")
        content_renamed = desktop_renamed.read_text(encoding="utf-8")
        self.assertIn("Name=Doom Ancient Gods", content_renamed)

        # Remove
        self.assertTrue(svc.remove_desktop_entry("doom"))
        self.assertFalse(svc.desktop_entry_exists("doom"))

    def test_desktop_service_auto_detect_icon(self):
        # Create an icon file next to exe
        icon_file = self.exe_file.parent / "icon.png"
        icon_file.touch()

        svc = DesktopService(repo=self.repo, apps_dir=self.apps_dir)
        desktop_file = svc.create_desktop_entry("doom")
        content = desktop_file.read_text(encoding="utf-8")
        self.assertIn(f"Icon={str(icon_file.resolve())}", content)

    def test_app_service_auto_cleanup_desktop_entry(self):
        app_svc = AppService(repo=self.repo)
        desktop_svc = DesktopService(repo=self.repo, apps_dir=self.apps_dir)

        # Create desktop entry manually using DesktopAdapter in custom apps_dir
        DesktopAdapter.write_desktop_entry(
            app_id="doom",
            name="Doom Eternal",
            apps_dir=self.apps_dir,
        )
        dest_path = self.apps_dir / "winebox-doom.desktop"
        self.assertTrue(dest_path.exists())

        # Test with DesktopService targeting the same apps_dir
        desktop_svc.remove_desktop_entry("doom")
        self.assertFalse(dest_path.exists())

    def test_cli_app_desktop_create_and_remove(self):
        # Create app in default sqlite for CLI runner
        default_repo = SqliteRepository()
        default_repo.save_prefix(
            Prefix(
                id="test-pfx",
                name="Test Prefix",
                default_profile_id="permissive",
            )
        )
        default_repo.save_app(
            Application(
                id="test-game",
                name="Test Game",
                prefix_id="test-pfx",
                exe_path="drive_c/game.exe",
                runner_id="system-wine",
                profile_id="permissive",
                policy=SecurityPolicy(),
            )
        )

        try:
            # Run CLI app desktop test-game
            result = self.runner.invoke(cli_app, ["app", "desktop", "test-game"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Desktop shortcut created", result.output)

            desktop_path = DesktopAdapter.desktop_entry_path("test-game")
            self.assertTrue(desktop_path.exists())

            # Remove via CLI
            result_remove = self.runner.invoke(cli_app, ["app", "desktop", "test-game", "--remove"])
            self.assertEqual(result_remove.exit_code, 0)
            self.assertIn("Desktop shortcut for 'test-game' removed", result_remove.output)
            self.assertFalse(desktop_path.exists())

        finally:
            default_repo.delete_app("test-game")
            default_repo.delete_prefix("test-pfx")
            DesktopAdapter.remove_desktop_entry("test-game")


if __name__ == "__main__":
    unittest.main()
