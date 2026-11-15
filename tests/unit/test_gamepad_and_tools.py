"""Unit tests for Gamepad passthrough policy and sandboxed Wine tools."""

import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from winebox.application.prefix_service import PrefixService
from winebox.application.profile_service import ProfileService
from winebox.common.exceptions import WineboxError
from winebox.domain.models import Prefix, SecurityPolicy
from winebox.infrastructure.db_schema import init_database_schema
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.interface.cli import app
from winebox.security.mount_builder import MountBuilder


class TestGamepadPolicy(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.repo = SqliteRepository(
            data_root=self.tmp_path / "data",
            config_root=self.tmp_path / "config",
        )

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_builtin_profiles_gamepad_defaults(self) -> None:
        svc = ProfileService(repo=self.repo)
        permissive = svc.get_profile("permissive")
        balanced = svc.get_profile("balanced")
        zero_trust = svc.get_profile("zero-trust")
        paranoid = svc.get_profile("paranoid")

        self.assertTrue(permissive.gamepad)
        self.assertFalse(balanced.gamepad)
        self.assertFalse(zero_trust.gamepad)
        self.assertFalse(paranoid.gamepad)
        self.assertTrue(permissive.to_policy().gamepad)

    def test_profile_service_create_and_update_gamepad(self) -> None:
        svc = ProfileService(repo=self.repo)
        prof = svc.create_profile("arcade", "Arcade", gamepad=True)
        self.assertTrue(prof.gamepad)
        self.assertTrue(svc.get_profile("arcade").gamepad)

        updated = svc.update_profile("arcade", gamepad=False)
        self.assertFalse(updated.gamepad)
        self.assertFalse(svc.get_profile("arcade").gamepad)

    def test_sqlite_migration_adds_gamepad_column(self) -> None:
        db_file = self.tmp_path / "legacy.db"
        conn = sqlite3.connect(db_file)
        conn.execute(
            """
            CREATE TABLE security_profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                is_builtin INTEGER NOT NULL DEFAULT 0,
                display INTEGER NOT NULL DEFAULT 1,
                audio INTEGER NOT NULL DEFAULT 1,
                network INTEGER NOT NULL DEFAULT 1,
                gpu INTEGER NOT NULL DEFAULT 1,
                description TEXT DEFAULT ''
            );
            """
        )
        conn.execute(
            "INSERT INTO security_profiles VALUES ('permissive', 'Permissive', 1, 1, 1, 1, 1, 'old');"
        )
        conn.execute(
            "INSERT INTO security_profiles VALUES ('balanced', 'Balanced', 1, 1, 1, 0, 0, 'old');"
        )
        conn.commit()

        init_database_schema(conn)
        conn.row_factory = sqlite3.Row
        perm_row = conn.execute("SELECT gamepad FROM security_profiles WHERE id = 'permissive'").fetchone()
        bal_row = conn.execute("SELECT gamepad FROM security_profiles WHERE id = 'balanced'").fetchone()
        conn.close()

        self.assertEqual(perm_row["gamepad"], 1)
        self.assertEqual(bal_row["gamepad"], 0)

    def test_mount_builder_binds_dev_input_when_gamepad_enabled(self) -> None:
        pfx = self.tmp_path / "pfx"
        home = self.tmp_path / "home"
        pfx.mkdir()
        home.mkdir()

        with patch("winebox.security.mount_builder.Path.exists", return_value=True):
            args_on = MountBuilder(pfx, home, SecurityPolicy(display=False, audio=False, gpu=False, gamepad=True)).build_bwrap_args()
            args_off = MountBuilder(pfx, home, SecurityPolicy(display=False, audio=False, gpu=False, gamepad=False)).build_bwrap_args()

        self.assertIn("/dev/input", args_on)
        self.assertNotIn("/dev/input", args_off)


class TestPrefixWineTools(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.repo = SqliteRepository(
            data_root=self.tmp_path / "data",
            config_root=self.tmp_path / "config",
        )
        self.bwrap = MagicMock()
        self.bwrap.execute_in_sandbox.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        self.svc = PrefixService(repo=self.repo, bwrap_adapter=self.bwrap)

        p_dir = self.repo.get_prefix_dir("game-pfx")
        (p_dir / "prefix" / "dosdevices").mkdir(parents=True)
        (p_dir / "home").mkdir(parents=True)
        self.repo.save_prefix(Prefix(id="game-pfx", name="Game Prefix"))

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_run_tool_rejects_disallowed_tool(self) -> None:
        with self.assertRaises(WineboxError):
            self.svc.run_tool("game-pfx", "bash")

    def test_run_tool_executes_winecfg_in_sandbox(self) -> None:
        rc = self.svc.run_tool("game-pfx", "winecfg", inherit_stdio=False)
        self.assertEqual(rc, 0)
        self.bwrap.execute_in_sandbox.assert_called_once()
        call_kwargs = self.bwrap.execute_in_sandbox.call_args.kwargs
        self.assertIn("winecfg", call_kwargs["command_inside"])


class TestGamepadAndToolCLI(unittest.TestCase):
    def setUp(self) -> None:
        self.cli = CliRunner()

    def test_cli_help_and_profile_list(self) -> None:
        res_tool = self.cli.invoke(app, ["prefix", "tool", "--help"])
        self.assertEqual(res_tool.exit_code, 0)
        self.assertIn("winecfg", res_tool.output)

        with tempfile.TemporaryDirectory() as tmp:
            env = {"XDG_DATA_HOME": str(Path(tmp) / "data"), "XDG_CONFIG_HOME": str(Path(tmp) / "cfg"), "PATH": "/usr/bin:/bin"}
            res_prof = self.cli.invoke(app, ["profile", "list"], env=env)
            self.assertEqual(res_prof.exit_code, 0)
            self.assertIn("Gamepad", res_prof.output)


if __name__ == "__main__":
    unittest.main()
