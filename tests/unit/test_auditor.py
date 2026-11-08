import os
import tempfile
import unittest
from pathlib import Path
from winebox.common.exceptions import PrefixAuditError
from winebox.security.auditor import PrefixAuditor


class TestPrefixAuditor(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.prefix_dir = Path(self.temp_dir.name)
        (self.prefix_dir / "drive_c").mkdir()
        (self.prefix_dir / "dosdevices").mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sanitize_dosdevices_removes_root_z(self):
        z_link = self.prefix_dir / "dosdevices" / "z:"
        z_link.symlink_to("/")

        actions = PrefixAuditor.sanitize_dosdevices(self.prefix_dir)
        self.assertEqual(len(actions), 1)
        self.assertFalse(z_link.exists())

    def test_audit_detects_escaping_symlink(self):
        secret_file = self.prefix_dir.parent / "secret.txt"
        secret_file.write_text("sensitivedata")

        bad_link = self.prefix_dir / "drive_c" / "escape_link"
        bad_link.symlink_to(secret_file)

        with self.assertRaises(PrefixAuditError):
            PrefixAuditor.audit_prefix(self.prefix_dir)


if __name__ == "__main__":
    unittest.main()

