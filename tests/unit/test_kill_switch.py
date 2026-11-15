"""Unit and integration tests for Emergency Prefix Process Killer (ADR-025)."""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typer.testing import CliRunner

from winebox.application.app_service import AppService
from winebox.application.prefix_service import PrefixService
from winebox.domain.models import Application, Prefix, SecurityPolicy
from winebox.infrastructure.desktop_adapter import DesktopAdapter
from winebox.infrastructure.process_manager import PrefixLock, ProcessManager
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.interface.cli import app as cli_app


class TestKillSwitch(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.prefixes_dir = self.base_path / "prefixes"
        self.repo = SqliteRepository(data_root=self.base_path)

        # Create dummy prefix directory
        self.p1_dir = self.prefixes_dir / "p1"
        (self.p1_dir / "prefix" / "dosdevices").mkdir(parents=True, exist_ok=True)
        (self.p1_dir / "home").mkdir(parents=True, exist_ok=True)

        self.repo.save_prefix(
            Prefix(
                id="p1",
                name="Prefix One",
                default_profile_id="permissive",
            )
        )
        self.repo.save_app(
            Application(
                id="game1",
                name="Game One",
                prefix_id="p1",
                exe_path="drive_c/game.exe",
                runner_id="system-wine",
                profile_id="permissive",
                policy=SecurityPolicy(),
            )
        )
        self.runner = CliRunner()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_prefix_lock_status_and_read_pid(self):
        self.assertFalse(PrefixLock.is_locked(self.p1_dir))
        self.assertIsNone(PrefixLock.read_locked_pid(self.p1_dir))

        lock = PrefixLock(self.p1_dir)
        lock.acquire()
        try:
            self.assertTrue(PrefixLock.is_locked(self.p1_dir))
            recorded_pid = PrefixLock.read_locked_pid(self.p1_dir)
            self.assertEqual(recorded_pid, os.getpid())
        finally:
            lock.release()

        self.assertFalse(PrefixLock.is_locked(self.p1_dir))

    def test_process_manager_kill_pid_graceful_and_force(self):
        # Spawn a dummy long-running python process
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.assertTrue(ProcessManager.is_pid_alive(proc.pid))

        # Graceful kill via SIGTERM
        killed = ProcessManager.kill_pid(proc.pid, timeout=1.0, force=False)
        self.assertTrue(killed)
        self.assertFalse(ProcessManager.is_pid_alive(proc.pid))
        proc.wait(timeout=1)

    def test_prefix_service_kill_idle_prefix(self):
        svc = PrefixService(repo=self.repo)
        res = svc.kill_prefix("p1")
        self.assertFalse(res["running"])
        self.assertEqual(res["killed_pids"], [])

    def test_prefix_service_kill_active_prefix(self):
        # Spawn a subprocess that acquires the prefix.lock and sleeps
        code = f"""
import fcntl, os, time
fd = os.open('{self.p1_dir / "prefix.lock"}', os.O_CREAT | os.O_RDWR, 0o644)
fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
os.write(fd, f'{{os.getpid()}}\\n'.encode())
time.sleep(60)
"""
        proc = subprocess.Popen([sys.executable, "-c", code])
        time.sleep(0.2)  # Give process time to acquire lock

        self.assertTrue(PrefixLock.is_locked(self.p1_dir))
        self.assertEqual(PrefixLock.read_locked_pid(self.p1_dir), proc.pid)

        svc = PrefixService(repo=self.repo)
        res = svc.kill_prefix("p1", force=False)

        self.assertTrue(res["running"])
        self.assertIn(proc.pid, res["killed_pids"])
        self.assertFalse(ProcessManager.is_pid_alive(proc.pid))
        self.assertFalse(PrefixLock.is_locked(self.p1_dir))
        proc.wait(timeout=1)

    def test_app_service_kill_app(self):
        app_svc = AppService(repo=self.repo)
        res = app_svc.kill_app("game1")
        self.assertFalse(res["running"])
        self.assertEqual(res["killed_pids"], [])

    def test_cli_prefix_and_app_kill_idle(self):
        # Test CLI on default repo with non-existent prefix
        res_fail = self.runner.invoke(cli_app, ["prefix", "kill", "non-existent-pfx"])
        self.assertNotEqual(res_fail.exit_code, 0)
        self.assertIn("does not exist", res_fail.output)

        res_app_fail = self.runner.invoke(cli_app, ["app", "kill", "non-existent-app"])
        self.assertNotEqual(res_app_fail.exit_code, 0)

    def test_desktop_action_kill_in_desktop_adapter(self):
        content = DesktopAdapter.generate_content("game1", "Game One", prefix_id="p1")
        self.assertIn("Actions=Configure;Kill;", content)
        self.assertIn("[Desktop Action Kill]", content)
        self.assertIn("Name=Stop / Kill Process", content)
        self.assertIn("Exec=winebox prefix kill p1", content)


if __name__ == "__main__":
    unittest.main()
