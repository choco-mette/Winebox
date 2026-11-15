"""Unit tests verifying audit backlog hardening fixes (concurrency, resource cleanup, security, layering)."""

import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from winebox.application.import_service import ImportService
from winebox.application.lutris_service import LutrisService
from winebox.application.prefix_service import PrefixService
from winebox.common.exceptions import PolicyValidationError, PrefixAuditError, WineboxError
from winebox.domain.models import HostMount, MountMode, SecurityPolicy
from winebox.infrastructure.db_sync import write_prefix_snapshot
from winebox.infrastructure.log_manager import LogManager
from winebox.infrastructure.process_manager import ProcessManager
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.security.auditor import PrefixAuditor
from winebox.security.validator import PolicyValidator


class TestAuditBacklogHardening(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.repo = SqliteRepository(data_root=self.root / "data", config_root=self.root / "config")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_validator_rejects_system_subpaths_and_restricted_env_vars(self) -> None:
        validator = PolicyValidator(host_home=self.root / "home")
        # /etc/hosts exists on standard Linux
        if Path("/etc/hosts").exists():
            with self.assertRaises(PolicyValidationError):
                validator.validate_mount(
                    HostMount(host_path=Path("/etc/hosts"), sandbox_path=Path("/tmp/hosts"), mode=MountMode.RO)
                )

        policy = SecurityPolicy(env_vars={"LD_PRELOAD": "/tmp/evil.so"})
        with self.assertRaises(PolicyValidationError):
            validator.validate_policy(policy)

        policy_wp = SecurityPolicy(env_vars={"WINEPREFIX": "/tmp/other"})
        with self.assertRaises(PolicyValidationError):
            validator.validate_policy(policy_wp)

    def test_auditor_case_insensitive_and_traversal_dosdevices(self) -> None:
        prefix_dir = self.root / "pfx" / "prefix"
        dosdevices = prefix_dir / "dosdevices"
        dosdevices.mkdir(parents=True)
        (prefix_dir / "drive_c").mkdir()

        # Uppercase Z: -> / and y: -> ../../../../..
        (dosdevices / "Z:").symlink_to("/")
        (dosdevices / "y:").symlink_to("../../../../..")
        (dosdevices / "c:").symlink_to("../drive_c")

        with self.assertRaises(PrefixAuditError):
            PrefixAuditor.audit_prefix(prefix_dir, check_registry=False)

        actions = PrefixAuditor.sanitize_dosdevices(prefix_dir)
        self.assertGreaterEqual(len(actions), 2)
        self.assertFalse((dosdevices / "Z:").exists())
        self.assertFalse((dosdevices / "y:").exists())
        self.assertTrue((dosdevices / "c:").is_symlink())

    def test_process_manager_kill_pid_separates_eperm_and_esrch(self) -> None:
        with patch.object(ProcessManager, "is_pid_alive", return_value=True):
            with patch("os.kill", side_effect=PermissionError("Operation not permitted")):
                self.assertFalse(ProcessManager.kill_pid(99999, force=True))

            with patch("os.kill", side_effect=ProcessLookupError("No such process")):
                self.assertTrue(ProcessManager.kill_pid(99999, force=True))

    def test_log_manager_closes_handlers_and_read_logs_no_mkdir(self) -> None:
        prefixes_dir = self.root / "data" / "prefixes"
        mgr = LogManager(prefixes_dir=prefixes_dir)

        # Unknown prefix should not create empty logs directory
        self.assertEqual(mgr.read_logs("nonexistent"), [])
        self.assertFalse((prefixes_dir / "nonexistent").exists())

        mgr.log_execution("pfx1", "app1", "hello", "", 0)
        logger_name = f"winebox.prefix.{prefixes_dir.resolve()}.pfx1"
        self.assertEqual(len(logging.getLogger(logger_name).handlers), 0)
        lines = mgr.read_logs("pfx1", max_lines=10)
        self.assertTrue(any("hello" in line for line in lines))

    def test_prefix_service_missing_prefix_and_atomic_create(self) -> None:
        svc = PrefixService(repo=self.repo)
        with self.assertRaises(WineboxError):
            svc.audit_prefix("missing")
        with self.assertRaises(WineboxError):
            svc.remove_prefix("missing")
        self.assertFalse(self.repo.get_prefix_dir("missing").exists())

        svc.create_prefix("p1", initialize_wineboot=False)
        with self.assertRaises(WineboxError):
            svc.create_prefix("p1", initialize_wineboot=False)

    def test_import_prefix_rejects_duplicate_and_atomic_snapshot(self) -> None:
        ext = self.root / "external_pfx"
        (ext / "drive_c").mkdir(parents=True)
        imp = ImportService(repo=self.repo)
        imp.import_prefix(ext, prefix_id="imp1")

        # Duplicate import rejected without overwriting
        with self.assertRaises(WineboxError):
            imp.import_prefix(ext, prefix_id="imp1")

        # Snapshot exists and no .tmp leftover
        p_dir = self.repo.get_prefix_dir("imp1")
        write_prefix_snapshot(self.repo, "imp1")
        self.assertTrue((p_dir / "metadata.json").exists())
        self.assertFalse((p_dir / "metadata.json.tmp").exists())

    def test_lutris_service_is_available_returns_bool(self) -> None:
        self.assertIsInstance(LutrisService.is_available(), bool)


if __name__ == "__main__":
    unittest.main()
