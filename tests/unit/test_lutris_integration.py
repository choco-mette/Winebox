"""Unit tests for ADR-022 Lutris integration via official installer YAML scripts."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from typer.testing import CliRunner

from winebox.application.app_service import AppService
from winebox.application.lutris_service import LutrisService
from winebox.application.prefix_service import PrefixService
from winebox.domain.models import Application
from winebox.infrastructure.lutris_adapter import LutrisAdapter
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.interface.cli import app


class TestLutrisIntegration(unittest.TestCase):
    def test_generate_installer_yaml_creates_valid_lutris_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            dummy_app = Application(
                id="my-game",
                name="My Awesome Game",
                prefix_id="gaming",
                exe_path="drive_c/Program Files/my-game/Game.exe",
            )
            yaml_path = LutrisAdapter.generate_installer_yaml(dummy_app, dest)
            self.assertTrue(yaml_path.exists())
            content = yaml_path.read_text(encoding="utf-8")
            self.assertIn('name: "My Awesome Game"', content)
            self.assertIn('game_slug: "my-game"', content)
            self.assertIn('slug: "my-game-winebox"', content)
            self.assertIn("runner: linux", content)
            self.assertIn('args: "app run my-game"', content)
            self.assertIn("disable_runtime: true", content)

    def test_lutris_service_exports_and_calls_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = SqliteRepository(data_root=root / "data", config_root=root / "config")
            mock_bwrap = MagicMock()
            mock_bwrap.execute_in_sandbox.return_value.returncode = 0

            prefix_svc = PrefixService(repo=repo, bwrap_adapter=mock_bwrap)
            prefix_svc.create_prefix("gaming", initialize_wineboot=False)

            app_svc = AppService(repo=repo)
            app_svc.register_app(
                app_id="test-game",
                name="Test Game",
                prefix_id="gaming",
                exe_path="drive_c/Game.exe",
            )

            mock_adapter = MagicMock(wraps=LutrisAdapter)
            mock_adapter.launch_installer = MagicMock()

            svc = LutrisService(repo=repo, adapter=mock_adapter)
            yaml_path = svc.export_app_to_lutris("test-game", launch_lutris=True)

            self.assertTrue(yaml_path.exists())
            mock_adapter.launch_installer.assert_called_once_with(yaml_path)

    def test_cli_lutris_help(self) -> None:
        runner = CliRunner()
        res = runner.invoke(app, ["lutris", "add", "--help"])
        self.assertEqual(res.exit_code, 0)
        self.assertIn("Generate an official Lutris installer YAML", res.stdout)


if __name__ == "__main__":
    unittest.main()
