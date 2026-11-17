"""Unit tests for master application groups and multi-tag assignments (ADR-020)."""

import tempfile
import unittest
from pathlib import Path
from typer.testing import CliRunner

from winebox.application.app_service import AppService
from winebox.application.group_service import GroupService
from winebox.common.exceptions import WineboxError
from winebox.domain.models import Application, Prefix, SecurityPolicy
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.interface.cli import app as cli_app


class TestGroupService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.repo = SqliteRepository(data_root=self.root / "data", config_root=self.root / "cfg")
        self.group_svc = GroupService(repo=self.repo)
        self.app_svc = AppService(repo=self.repo)

        # Setup sample prefix & app
        self.repo.save_prefix(Prefix(id="p1", name="Prefix 1"))
        self.app_svc.register_app(
            app_id="app1",
            name="Game One",
            prefix_id="p1",
            exe_path="drive_c/game1.exe",
        )
        self.app_svc.register_app(
            app_id="app2",
            name="Game Two",
            prefix_id="p1",
            exe_path="drive_c/game2.exe",
        )
        self.runner = CliRunner()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_group_crud_lifecycle(self):
        # Create groups
        rpg = self.group_svc.create_group("RPG & Adventure")
        self.assertEqual(rpg.id, "rpg-adventure")
        self.assertEqual(rpg.name, "RPG & Adventure")

        fav = self.group_svc.create_group("Favorites", group_id="favs", icon="starred")
        self.assertEqual(fav.id, "favs")
        self.assertEqual(fav.icon, "starred")

        # Duplicate ID should raise WineboxError
        with self.assertRaises(WineboxError):
            self.group_svc.create_group("Duplicates", group_id="favs")

        # List groups
        all_groups = self.group_svc.list_groups()
        self.assertEqual(len(all_groups), 2)
        self.assertEqual([g.id for g in all_groups], ["favs", "rpg-adventure"])

        # Rename group
        renamed = self.group_svc.rename_group("favs", "Top Favorites")
        self.assertEqual(renamed.name, "Top Favorites")

        # Delete group
        self.group_svc.delete_group("rpg-adventure")
        self.assertEqual(len(self.group_svc.list_groups()), 1)

    def test_multi_group_assignment(self):
        g1 = self.group_svc.create_group("Action")
        g2 = self.group_svc.create_group("Favorites")

        # Assign app1 to both groups
        self.group_svc.assign_groups("app1", [g1.id, g2.id])
        assigned_grps = self.group_svc.get_app_groups("app1")
        self.assertEqual(len(assigned_grps), 2)
        self.assertEqual({g.id for g in assigned_grps}, {g1.id, g2.id})

        # Reload app from repo directly
        app1 = self.repo.load_app("app1")
        self.assertEqual(set(app1.groups), {g1.id, g2.id})

        # App2 has no groups (uncategorized)
        app2 = self.repo.load_app("app2")
        self.assertEqual(app2.groups, [])

        # Deleting a group removes association without removing app
        self.group_svc.delete_group(g1.id)
        reloaded_app1 = self.repo.load_app("app1")
        self.assertEqual(reloaded_app1.groups, [g2.id])

    def test_cli_group_and_app_set_groups(self):
        # Test CLI group list when empty
        res_empty = self.runner.invoke(cli_app, ["group", "list"])
        self.assertEqual(res_empty.exit_code, 0)

        # Test CLI group create
        res_create = self.runner.invoke(cli_app, ["group", "create", "Indie Games", "--id", "indie"])
        self.assertEqual(res_create.exit_code, 0)
        self.assertIn("Created group", res_create.output)

        # Test CLI group rename
        res_rename = self.runner.invoke(cli_app, ["group", "rename", "indie", "Cool Indie"])
        self.assertEqual(res_rename.exit_code, 0)

        # Test CLI group list
        res_list = self.runner.invoke(cli_app, ["group", "list"])
        self.assertEqual(res_list.exit_code, 0)
        self.assertIn("Cool Indie", res_list.output)

        # Test CLI group delete
        res_del = self.runner.invoke(cli_app, ["group", "delete", "indie"])
        self.assertEqual(res_del.exit_code, 0)
        self.assertIn("Deleted group", res_del.output)


if __name__ == "__main__":
    unittest.main()
