import os
import unittest
from unittest.mock import patch
from winebox.common.doctor import SystemDoctor


class TestDoctor(unittest.TestCase):
    def test_doctor_bwrap_found(self):
        with patch("shutil.which", return_value="/usr/bin/bwrap"):
            res = SystemDoctor.check_bwrap()
            self.assertTrue(res.passed)
            self.assertIn("/usr/bin/bwrap", res.details)

    def test_doctor_bwrap_missing(self):
        with patch("shutil.which", return_value=None):
            res = SystemDoctor.check_bwrap()
            self.assertFalse(res.passed)
            self.assertIn("not found", res.details)

    def test_doctor_wine_found(self):
        with patch("shutil.which", return_value="/usr/bin/wine"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "wine-9.0\n"
            res = SystemDoctor.check_wine()
            self.assertTrue(res.passed)
            self.assertIn("wine-9.0", res.details)

    def test_doctor_display_detection(self):
        with patch.dict(os.environ, {"DISPLAY": ":1"}, clear=True):
            res = SystemDoctor.check_display()
            self.assertTrue(res.passed)
            self.assertIn(":1", res.details)

        with patch.dict(os.environ, {}, clear=True):
            res = SystemDoctor.check_display()
            self.assertFalse(res.passed)


if __name__ == "__main__":
    unittest.main()

