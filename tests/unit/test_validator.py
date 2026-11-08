import tempfile
import unittest
from pathlib import Path
from winebox.common.exceptions import PolicyValidationError
from winebox.domain.models import HostMount, MountMode, SecurityPolicy
from winebox.security.validator import PolicyValidator


class TestPolicyValidator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.fake_home = Path(self.temp_dir.name)
        self.validator = PolicyValidator(host_home=self.fake_home)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_reject_root_mount(self):
        mount = HostMount(host_path=Path("/"), sandbox_path=Path("/host_root"))
        with self.assertRaises(PolicyValidationError):
            self.validator.validate_mount(mount)

    def test_reject_entire_home_mount(self):
        mount = HostMount(host_path=self.fake_home, sandbox_path=Path("/my_home"))
        with self.assertRaises(PolicyValidationError):
            self.validator.validate_mount(mount)

    def test_reject_sensitive_home_subpaths(self):
        ssh_dir = self.fake_home / ".ssh"
        ssh_dir.mkdir(parents=True, exist_ok=True)
        mount = HostMount(host_path=ssh_dir, sandbox_path=Path("/ssh"))
        with self.assertRaises(PolicyValidationError):
            self.validator.validate_mount(mount)

    def test_allow_safe_subfolder(self):
        docs_dir = self.fake_home / "Documents"
        docs_dir.mkdir(parents=True, exist_ok=True)
        mount = HostMount(host_path=docs_dir, sandbox_path=Path("/docs"), mode=MountMode.RO)
        # Should not raise
        self.validator.validate_mount(mount)


if __name__ == "__main__":
    unittest.main()
