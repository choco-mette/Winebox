import tempfile
import unittest
from pathlib import Path
from winebox.infrastructure.log_manager import LogManager


class TestLogManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.prefixes_dir = Path(self.temp_dir.name)
        self.log_manager = LogManager(prefixes_dir=self.prefixes_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_log_execution_and_read(self):
        self.log_manager.log_execution(
            prefix_id="p1",
            app_id="app1",
            stdout="sample standard output",
            stderr="sample warning message",
            exit_code=0,
        )

        log_file = self.log_manager.get_log_file("p1")
        self.assertTrue(log_file.exists())

        lines = self.log_manager.read_logs("p1", max_lines=10)
        self.assertTrue(any("sample standard output" in l for l in lines))
        self.assertTrue(any("sample warning message" in l for l in lines))
        self.assertTrue(any("Exit Code 0" in l for l in lines))

    def test_read_logs_nonexistent(self):
        lines = self.log_manager.read_logs("nonexistent")
        self.assertEqual(lines, [])


if __name__ == "__main__":
    unittest.main()

