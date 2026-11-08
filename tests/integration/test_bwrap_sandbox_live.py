import subprocess
import tempfile
import unittest
from pathlib import Path
from winebox.infrastructure.bwrap_adapter import BwrapAdapter


class TestBwrapSandboxLive(unittest.TestCase):
    """Integration test verifying real Bubblewrap execution on the host kernel."""

    def setUp(self):
        self.adapter = BwrapAdapter()

    def test_verify_ready_succeeds_on_host(self):
        # Should not raise SystemDependencyError
        self.adapter.verify_ready()

    def test_read_only_root_enforcement(self):
        """Verifies that an attempt to write to a read-only mount inside bwrap is denied."""
        bwrap_args = [
            "bwrap",
            "--unshare-user",
            "--unshare-pid",
            "--ro-bind", "/", "/",
            "--proc", "/proc",
            "--dev", "/dev",
        ]
        # Attempt to touch a file in root
        res = self.adapter.execute_in_sandbox(
            bwrap_args=bwrap_args,
            command_inside=["sh", "-c", "touch /test_file_should_fail"],
            inherit_stdio=False,
        )
        self.assertNotEqual(res.returncode, 0)

    def test_sandbox_isolated_tmpfs(self):
        """Verifies that files written in tmpfs exist inside but do not leak to host."""
        bwrap_args = [
            "bwrap",
            "--unshare-user",
            "--unshare-pid",
            "--ro-bind", "/usr", "/usr",
            "--ro-bind-try", "/lib", "/lib",
            "--ro-bind-try", "/lib64", "/lib64",
            "--ro-bind-try", "/bin", "/bin",
            "--tmpfs", "/tmp",
            "--proc", "/proc",
            "--dev", "/dev",
        ]
        res = self.adapter.execute_in_sandbox(
            bwrap_args=bwrap_args,
            command_inside=["sh", "-c", "echo 'hello' > /tmp/sandboxed_test.txt && cat /tmp/sandboxed_test.txt"],
            inherit_stdio=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), "hello")
        self.assertFalse(Path("/tmp/sandboxed_test.txt").exists())


if __name__ == "__main__":
    unittest.main()

