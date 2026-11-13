"""Unit tests for ADR-021 unified interactive 'winebox add' wizard helpers."""

import tempfile
import unittest
from pathlib import Path
from typer.testing import CliRunner

from winebox.application.import_service import ImportService
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.interface.cli import app
from winebox.interface.tui import slugify


class TestAddWizard(unittest.TestCase):
    def test_slugify_generates_clean_kebab_case_ids(self) -> None:
        self.assertEqual(slugify("Need for Speed: Most Wanted (2005)"), "need-for-speed-most-wanted-2005")
        self.assertEqual(slugify("  GTA San Andreas  "), "gta-san-andreas")
        self.assertEqual(slugify("!!!"), "app")

    def test_scan_portable_executables_sorts_root_first_and_helpers_last(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_dir = root / "db"
            repo = SqliteRepository(data_root=db_dir, config_root=db_dir / "config")
            svc = ImportService(repo=repo)

            game_dir = root / "MyGame"
            (game_dir / "bin").mkdir(parents=True)
            (game_dir / "redist").mkdir(parents=True)

            (game_dir / "Game.exe").write_text("dummy")
            (game_dir / "unins000.exe").write_text("dummy")
            (game_dir / "bin" / "Launcher.exe").write_text("dummy")
            (game_dir / "redist" / "DXSETUP.exe").write_text("dummy")

            candidates = svc.scan_portable_executables(game_dir)
            self.assertEqual(
                candidates,
                [
                    "Game.exe",
                    "bin/Launcher.exe",
                    "unins000.exe",
                    "redist/DXSETUP.exe",
                ],
            )

    def test_cli_add_help_works_and_install_removed(self) -> None:
        runner = CliRunner()
        res_add = runner.invoke(app, ["add", "--help"])
        self.assertEqual(res_add.exit_code, 0)
        self.assertIn("Interactive TUI Wizard", res_add.stdout)

        res_install = runner.invoke(app, ["install", "--help"])
        self.assertNotEqual(res_install.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
