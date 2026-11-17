import tempfile
import unittest
from pathlib import Path
from winebox.common.exceptions import PrefixLockError
from winebox.infrastructure.process_manager import PrefixLock, ProcessManager, prefix_lock


class TestProcessManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.prefix_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_single_lock_success(self):
        with prefix_lock(self.prefix_dir):
            lock_file = self.prefix_dir / "prefix.lock"
            self.assertTrue(lock_file.exists())

    def test_concurrent_lock_fails(self):
        lock1 = PrefixLock(self.prefix_dir)
        lock1.acquire()
        try:
            lock2 = PrefixLock(self.prefix_dir)
            with self.assertRaises(PrefixLockError):
                lock2.acquire()
        finally:
            lock1.release()

    def test_lock_release_allows_reacquire(self):
        lock1 = PrefixLock(self.prefix_dir)
        lock1.acquire()
        lock1.release()

        lock2 = PrefixLock(self.prefix_dir)
        # Should succeed without error
        lock2.acquire()
        lock2.release()

    def test_run_process_streaming_to_log_file(self):
        log_file = self.prefix_dir / "stream_test.log"
        # Run python command that prints to stdout and stderr
        script = "import sys; print('hello from stdout'); sys.stderr.write('hello from stderr\\n')"
        res = ProcessManager.run_process(
            command=["python3", "-c", script],
            stream_log_file=log_file,
            log_header="--- START STREAM TEST ---",
            log_footer="--- END STREAM TEST ---",
            inherit_stdio=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("hello from stdout", res.stdout)
        self.assertIn("hello from stderr", res.stderr)

        self.assertTrue(log_file.exists())
        log_content = log_file.read_text()
        self.assertIn("--- START STREAM TEST ---", log_content)
        self.assertIn("hello from stdout", log_content)
        self.assertIn("hello from stderr", log_content)
        self.assertIn("--- END STREAM TEST ---", log_content)


if __name__ == "__main__":
    unittest.main()

