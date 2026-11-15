"""Unit tests for ADR-023 Sandboxed Winetricks integration and shared cache."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from typer.testing import CliRunner

from winebox.application.prefix_service import PrefixService
from winebox.application.winetricks_service import WinetricksService
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.infrastructure.winetricks_adapter import WinetricksAdapter
from winebox.interface.cli import app
from winebox.interface.tui.select import tui_multiselect


class TestWinetricksIntegration(unittest.TestCase):
    def test_find_winetricks_binary(self) -> None:
        bin_path = WinetricksAdapter.find_winetricks_binary()
        self.assertIsNotNone(bin_path)
        self.assertTrue(bin_path.exists())

    def test_build_winetricks_cmd(self) -> None:
        cmd = WinetricksAdapter.build_winetricks_cmd(["vcrun2022", "dxvk"], unattended=True)
        self.assertIn("-q", cmd)
        self.assertIn("vcrun2022", cmd)
        self.assertIn("dxvk", cmd)

        gui_cmd = WinetricksAdapter.build_winetricks_cmd(["gui"], unattended=True)
        self.assertNotIn("-q", gui_cmd)

    def test_winetricks_service_configures_sandbox_and_shared_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = SqliteRepository(data_root=root / "data", config_root=root / "config")
            mock_bwrap = MagicMock()
            mock_bwrap.execute_in_sandbox.return_value.returncode = 0

            prefix_svc = PrefixService(repo=repo, bwrap_adapter=mock_bwrap)
            prefix_svc.create_prefix("test-pref", initialize_wineboot=False)

            mock_adapter = MagicMock(wraps=WinetricksAdapter)
            mock_adapter.find_winetricks_binary.return_value = Path("/usr/local/bin/winetricks")
            mock_adapter.build_winetricks_cmd.return_value = ["/usr/local/bin/winetricks", "-q", "dxvk"]

            svc = WinetricksService(repo=repo, bwrap_adapter=mock_bwrap, adapter=mock_adapter)
            self.assertTrue(svc.shared_cache_dir.exists())

            svc.run_winetricks("test-pref", verbs=["dxvk"], inherit_stdio=False)

            self.assertTrue(mock_bwrap.execute_in_sandbox.called)
            call_kwargs = mock_bwrap.execute_in_sandbox.call_args[1]
            bwrap_args = call_kwargs["bwrap_args"]
            self.assertIn("--share-net", bwrap_args)
            self.assertIn(str(svc.shared_cache_dir), bwrap_args)

    def test_tui_multiselect_non_interactive_fallback(self) -> None:
        options = [("a", "Option A"), ("b", "Option B"), ("c", "Option C")]
        chosen = tui_multiselect("Test Title", options, force_non_interactive=True)
        self.assertEqual(chosen, ["a"])

    def test_cli_prefix_winetricks_help(self) -> None:
        runner = CliRunner()
        res = runner.invoke(app, ["prefix", "winetricks", "--help"])
        self.assertEqual(res.exit_code, 0)
        self.assertIn("Run Winetricks inside the Bubblewrap sandbox", res.stdout)


if __name__ == "__main__":
    unittest.main()
