import tempfile
import unittest
from pathlib import Path
from winebox.application.profile_service import ProfileService
from winebox.common.exceptions import WineboxError
from winebox.infrastructure.sqlite_repository import SqliteRepository


class TestProfileService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.repo = SqliteRepository(data_root=base / "data", config_root=base / "config")
        self.service = ProfileService(repo=self.repo)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_and_list_profile(self):
        prof = self.service.create_profile(
            profile_id="dev-profile",
            name="Developer Profile",
            display=True,
            audio=True,
            network=False,
            gpu=True,
            description="Profile for development tools",
        )
        self.assertEqual(prof.id, "dev-profile")

        all_profiles = self.service.list_profiles()
        self.assertTrue(any(p.id == "dev-profile" for p in all_profiles))

    def test_update_profile(self):
        self.service.create_profile(
            profile_id="up-profile",
            name="Original",
            network=False,
        )
        updated = self.service.update_profile("up-profile", name="Modified", network=True)
        self.assertEqual(updated.name, "Modified")
        self.assertTrue(updated.network)

    def test_delete_profile(self):
        self.service.create_profile(
            profile_id="del-profile",
            name="To Delete",
        )
        self.service.delete_profile("del-profile")
        with self.assertRaises(WineboxError):
            self.service.get_profile("del-profile")


if __name__ == "__main__":
    unittest.main()

