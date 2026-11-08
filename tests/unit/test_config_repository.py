import tempfile
import unittest
from pathlib import Path
from winebox.domain.models import Application, Prefix, Runner, SecurityPolicy
from winebox.infrastructure.config_repository import ConfigRepository


class TestConfigRepository(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.repo = ConfigRepository(data_root=base / "data", config_root=base / "config")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_load_app(self):
        app = Application(
            id="test-app",
            name="Test Application",
            prefix_id="default-prefix",
            exe_path="drive_c/Program Files/Test/test.exe",
            policy=SecurityPolicy(display=True, network=False),
        )
        self.repo.save_app(app)

        loaded = self.repo.load_app("test-app")
        self.assertEqual(loaded.id, "test-app")
        self.assertEqual(loaded.name, "Test Application")
        self.assertEqual(loaded.prefix_id, "default-prefix")
        self.assertTrue(loaded.policy.display)
        self.assertFalse(loaded.policy.network)

    def test_save_and_load_prefix(self):
        prefix = Prefix(id="creative", name="Creative Suite")
        self.repo.save_prefix(prefix)

        loaded = self.repo.load_prefix("creative")
        self.assertEqual(loaded.id, "creative")
        self.assertEqual(loaded.name, "Creative Suite")

        all_prefixes = self.repo.list_prefixes()
        self.assertEqual(len(all_prefixes), 1)

    def test_runner_listing_includes_system_wine(self):
        runners = self.repo.list_runners()
        self.assertTrue(any(r.id == "system-wine" for r in runners))


if __name__ == "__main__":
    unittest.main()
