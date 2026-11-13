import tempfile
import unittest
from pathlib import Path
from winebox.common.exceptions import ResourceNotFoundError, WineboxError
from winebox.domain.models import Application, Prefix, Runner, SecurityProfile
from winebox.infrastructure.sqlite_repository import SqliteRepository


class TestSqliteRepository(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.repo = SqliteRepository(data_root=base / "data", config_root=base / "config")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_profiles_seeded(self):
        profiles = self.repo.list_profiles()
        ids = [p.id for p in profiles]
        self.assertIn("paranoid", ids)
        self.assertIn("zero-trust", ids)
        self.assertIn("balanced", ids)
        self.assertIn("permissive", ids)

    def test_save_and_load_profile(self):
        prof = SecurityProfile(
            id="test-prof",
            name="Test Profile",
            display=True,
            audio=False,
            network=True,
            gpu=False,
            description="Testing custom profile",
        )
        self.repo.save_profile(prof)

        loaded = self.repo.load_profile("test-prof")
        self.assertEqual(loaded.id, "test-prof")
        self.assertEqual(loaded.name, "Test Profile")
        self.assertTrue(loaded.display)
        self.assertFalse(loaded.audio)
        self.assertTrue(loaded.network)
        self.assertFalse(loaded.gpu)

    def test_cannot_delete_builtin_profile(self):
        with self.assertRaises(WineboxError):
            self.repo.delete_profile("permissive")

    def test_save_and_load_prefix(self):
        prefix = Prefix(id="test-p", name="Test Prefix", default_profile_id="balanced")
        self.repo.save_prefix(prefix)

        loaded = self.repo.load_prefix("test-p")
        self.assertEqual(loaded.id, "test-p")
        self.assertEqual(loaded.default_profile_id, "balanced")

        # Snapshot file generated
        snap_file = self.repo.get_prefix_dir("test-p") / "metadata.json"
        self.assertTrue(snap_file.exists())

    def test_save_and_load_app(self):
        prefix = Prefix(id="test-p2", name="Prefix 2")
        self.repo.save_prefix(prefix)

        app = Application(
            id="app-1",
            name="App One",
            prefix_id="test-p2",
            exe_path="drive_c/app.exe",
            profile_id="zero-trust",
        )
        self.repo.save_app(app)

        loaded = self.repo.load_app("app-1")
        self.assertEqual(loaded.id, "app-1")
        self.assertEqual(loaded.profile_id, "zero-trust")
        self.assertTrue(loaded.policy.display)
        self.assertFalse(loaded.policy.network)

    def test_foreign_key_restrict_profile_deletion(self):
        prof = SecurityProfile(id="used-prof", name="Used Profile")
        self.repo.save_profile(prof)

        prefix = Prefix(id="test-p3", name="Prefix 3", default_profile_id="used-prof")
        self.repo.save_prefix(prefix)

        # Attempt to delete used profile should fail
        with self.assertRaises(WineboxError):
            self.repo.delete_profile("used-prof")


if __name__ == "__main__":
    unittest.main()
