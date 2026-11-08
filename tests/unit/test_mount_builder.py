import os
import tempfile
import unittest
from pathlib import Path
from winebox.domain.models import HostMount, MountMode, SecurityPolicy
from winebox.security.mount_builder import MountBuilder


class TestMountBuilder(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.prefix_dir = self.base_dir / "prefix"
        self.home_dir = self.base_dir / "home"
        self.prefix_dir.mkdir()
        self.home_dir.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_mount_builder_args(self):
        policy = SecurityPolicy(display=True, audio=True, network=True, gpu=True)
        builder = MountBuilder(self.prefix_dir, self.home_dir, policy)
        args = builder.build_bwrap_args()

        self.assertEqual(args[0], "bwrap")
        self.assertIn("--unshare-user", args)
        self.assertIn("--unshare-pid", args)
        self.assertIn("--share-net", args)
        self.assertIn("--proc", args)
        self.assertIn(str(self.prefix_dir), args)
        self.assertIn(str(self.home_dir), args)

    def test_network_disabled_mount_builder(self):
        policy = SecurityPolicy(network=False)
        builder = MountBuilder(self.prefix_dir, self.home_dir, policy)
        args = builder.build_bwrap_args()

        self.assertIn("--unshare-net", args)
        self.assertNotIn("--share-net", args)

    def test_custom_mount_addition(self):
        test_dir = self.base_dir / "custom"
        test_dir.mkdir()
        mount = HostMount(host_path=test_dir, sandbox_path=Path("/custom"), mode=MountMode.RO)
        policy = SecurityPolicy(host_mounts=[mount])

        builder = MountBuilder(self.prefix_dir, self.home_dir, policy)
        args = builder.build_bwrap_args()

        self.assertIn("--ro-bind", args)
        self.assertIn(str(test_dir), args)
        self.assertIn("/custom", args)


if __name__ == "__main__":
    unittest.main()
