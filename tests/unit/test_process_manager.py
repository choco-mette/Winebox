import tempfile
import unittest
from pathlib import Path
from winebox.common.exceptions import PrefixLockError
from winebox.infrastructure.process_manager import PrefixLock, prefix_lock


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


if __name__ == "__main__":
    unittest.main()

