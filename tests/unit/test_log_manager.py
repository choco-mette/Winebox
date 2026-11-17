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

    def test_log_event_and_clear_logs(self):
        self.log_manager.log_event("p1", "Backup created successfully", level="INFO", category="BACKUP")
        self.log_manager.log_event("p1", "Process kill triggered", level="WARN", category="KILL")

        lines = self.log_manager.read_logs("p1", max_lines=10)
        self.assertEqual(len(lines), 2)
        self.assertIn("[INFO]", lines[0])
        self.assertIn("[BACKUP]", lines[0])
        self.assertIn("Backup created successfully", lines[0])
        self.assertIn("[WARN]", lines[1])
        self.assertIn("[KILL]", lines[1])

        # Test clear logs
        self.log_manager.clear_logs("p1")
        lines_after_clear = self.log_manager.read_logs("p1")
        self.assertEqual(lines_after_clear, [])
        self.assertFalse(self.log_manager.get_log_file("p1").exists())

    def test_rotation_policy_constants_and_rotation(self):
        self.assertEqual(LogManager.MAX_BYTES, 100 * 1024 * 1024)
        self.assertEqual(LogManager.BACKUP_COUNT, 3)

        # Temporarily adjust threshold to test rotation logic directly
        log_file = self.log_manager.get_log_file("p_rotate")
        log_file.write_text("x" * 50)
        self.log_manager._rotate_if_needed(log_file, max_bytes=40, backup_count=2)

        self.assertFalse(log_file.exists())
        self.assertTrue(log_file.with_name(f"{log_file.name}.1").exists())
        self.assertEqual(log_file.with_name(f"{log_file.name}.1").read_text(), "x" * 50)


if __name__ == "__main__":
    unittest.main()

