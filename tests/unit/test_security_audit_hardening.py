"""Unit tests verifying security audit hardening across validation, sandboxing, locking, and profiles."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from winebox.application.app_service import AppService
from winebox.application.execution_service import ExecutionService
from winebox.application.import_service import ImportService
from winebox.application.install_service import InstallService
from winebox.application.prefix_service import PrefixService
from winebox.application.profile_service import ProfileService
from winebox.application.winetricks_service import WinetricksService
from winebox.common.exceptions import (
    ExecutionError,
    PolicyValidationError,
    PrefixLockError,
    ResourceNotFoundError,
    WineboxError,
)
from winebox.domain.models import HostMount, MountMode, SecurityPolicy
from winebox.infrastructure.process_manager import PrefixLock, prefix_lock
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.security.auditor import PrefixAuditor
from winebox.security.mount_builder import MountBuilder
from winebox.security.validator import PolicyValidator


class TestPolicyValidatorSandboxPathHardening(unittest.TestCase):
    """Tests that PolicyValidator blocks host mounts targeting restricted sandbox paths."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.fake_home = Path(self.temp_dir.name)
        self.safe_host_dir = self.fake_home / "safe_host_data"
        self.safe_host_dir.mkdir(parents=True, exist_ok=True)
        self.validator = PolicyValidator(host_home=self.fake_home)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_allow_safe_host_and_sandbox_mount(self) -> None:
        mount = HostMount(
            host_path=self.safe_host_dir,
            sandbox_path=Path("/mnt/safe_data"),
            mode=MountMode.RO,
        )
        self.validator.validate_mount(mount)

    def test_reject_restricted_sandbox_paths_exact(self) -> None:
        restricted_targets = [
            Path("/proc"),
            Path("/dev"),
            Path("/app/runner"),
            Path("/usr"),
        ]
        for target in restricted_targets:
            with self.subTest(sandbox_path=str(target)):
                mount = HostMount(
                    host_path=self.safe_host_dir,
                    sandbox_path=target,
                    mode=MountMode.RO,
                )
                with self.assertRaises(PolicyValidationError):
                    self.validator.validate_mount(mount)

    def test_reject_restricted_sandbox_subpaths(self) -> None:
        restricted_subpaths = [
            Path("/proc/1"),
            Path("/proc/sys/kernel"),
            Path("/dev/shm"),
            Path("/dev/nvidia0"),
            Path("/app/runner/bin"),
            Path("/usr/bin"),
            Path("/usr/local/lib"),
        ]
        for target in restricted_subpaths:
            with self.subTest(sandbox_path=str(target)):
                mount = HostMount(
                    host_path=self.safe_host_dir,
                    sandbox_path=target,
                    mode=MountMode.RW,
                )
                with self.assertRaises(PolicyValidationError):
                    self.validator.validate_mount(mount)

    def test_reject_unnormalized_traversal_sandbox_paths(self) -> None:
        traversal_targets = [
            Path("/mnt/../proc"),
            Path("/mnt/sub/../../proc/self"),
            Path("/mnt/../dev"),
            Path("/mnt/sub/../../dev/null"),
            Path("/app/other/../runner"),
            Path("/app/other/../runner/lib"),
            Path("/mnt/../usr"),
            Path("/mnt/sub/../../usr/bin"),
        ]
        for target in traversal_targets:
            with self.subTest(sandbox_path=str(target)):
                mount = HostMount(
                    host_path=self.safe_host_dir,
                    sandbox_path=target,
                    mode=MountMode.RO,
                )
                with self.assertRaises(PolicyValidationError):
                    self.validator.validate_mount(mount)

    def test_validate_policy_rejects_restricted_sandbox_mount(self) -> None:
        policy = SecurityPolicy(
            host_mounts=[
                HostMount(
                    host_path=self.safe_host_dir,
                    sandbox_path=Path("/proc/meminfo"),
                    mode=MountMode.RO,
                )
            ]
        )
        with self.assertRaises(PolicyValidationError):
            self.validator.validate_policy(policy)


class TestMountBuilderNvidiaUvmHardening(unittest.TestCase):
    """Tests that MountBuilder includes /dev/nvidia-uvm when present and GPU is enabled."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.prefix_dir = base / "prefix"
        self.home_dir = base / "home"
        self.prefix_dir.mkdir(parents=True, exist_ok=True)
        self.home_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @staticmethod
    def _build_with_nvidia_uvm_state(
        prefix_dir: Path,
        home_dir: Path,
        gpu_enabled: bool,
        uvm_exists: bool,
    ) -> list[str]:
        orig_path_exists = Path.exists
        orig_os_exists = os.path.exists

        def fake_path_exists(path_obj: Path) -> bool:
            if str(path_obj) == "/dev/nvidia-uvm":
                return uvm_exists
            return orig_path_exists(path_obj)

        def fake_os_exists(path_arg: object) -> bool:
            if str(path_arg) == "/dev/nvidia-uvm":
                return uvm_exists
            return orig_os_exists(path_arg)  # type: ignore[arg-type]

        policy = SecurityPolicy(display=False, audio=False, network=False, gpu=gpu_enabled)
        builder = MountBuilder(prefix_dir, home_dir, policy)
        with (
            patch.object(Path, "exists", autospec=True, side_effect=fake_path_exists),
            patch("os.path.exists", side_effect=fake_os_exists),
        ):
            return builder.build_bwrap_args()

    def test_nvidia_uvm_included_when_device_exists(self) -> None:
        args = self._build_with_nvidia_uvm_state(
            self.prefix_dir,
            self.home_dir,
            gpu_enabled=True,
            uvm_exists=True,
        )
        self.assertIn("/dev/nvidia-uvm", args)
        idx = args.index("/dev/nvidia-uvm")
        self.assertGreater(idx, 0)
        self.assertIn(args[idx - 1], ("--dev-bind-try", "--dev-bind"))
        self.assertEqual(args[idx + 1], "/dev/nvidia-uvm")

    def test_nvidia_uvm_omitted_when_device_missing(self) -> None:
        args = self._build_with_nvidia_uvm_state(
            self.prefix_dir,
            self.home_dir,
            gpu_enabled=True,
            uvm_exists=False,
        )
        self.assertNotIn("/dev/nvidia-uvm", args)

    def test_nvidia_uvm_omitted_when_gpu_disabled(self) -> None:
        args = self._build_with_nvidia_uvm_state(
            self.prefix_dir,
            self.home_dir,
            gpu_enabled=False,
            uvm_exists=True,
        )
        self.assertNotIn("/dev/nvidia-uvm", args)


class TestServiceSanitizeOnExecutionErrorHardening(unittest.TestCase):
    """Tests that services still sanitize dosdevices when sandbox execution raises ExecutionError."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.repo = SqliteRepository(data_root=base / "data", config_root=base / "config")
        self.mock_bwrap = MagicMock()

        prefix_svc = PrefixService(repo=self.repo, bwrap_adapter=self.mock_bwrap)
        prefix_svc.create_prefix("p-err", initialize_wineboot=False)

        self.p_dir = self.repo.get_prefix_dir("p-err")
        self.prefix_inner = self.p_dir / "prefix"
        self.dosdevices = self.prefix_inner / "dosdevices"
        self.dosdevices.mkdir(parents=True, exist_ok=True)
        self.z_link = self.dosdevices / "z:"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _failing_sandbox_side_effect(self):
        def _fail(*_args, **_kwargs):
            if self.z_link.exists() or self.z_link.is_symlink():
                self.z_link.unlink()
            self.z_link.symlink_to("/")
            raise ExecutionError("Simulated sandbox failure")

        return _fail

    def test_execution_service_sanitizes_dosdevices_on_execution_error(self) -> None:
        app_svc = AppService(repo=self.repo)
        app_svc.register_app(
            app_id="err-app",
            name="Error App",
            prefix_id="p-err",
            exe_path="drive_c/app.exe",
        )
        self.mock_bwrap.execute_in_sandbox.side_effect = self._failing_sandbox_side_effect()
        exec_svc = ExecutionService(repo=self.repo, bwrap_adapter=self.mock_bwrap)

        with patch.object(
            PrefixAuditor,
            "sanitize_dosdevices",
            wraps=PrefixAuditor.sanitize_dosdevices,
        ) as spy_sanitize:
            with self.assertRaises(ExecutionError):
                exec_svc.run_app("err-app", inherit_stdio=False)

        spy_sanitize.assert_any_call(self.prefix_inner)
        self.assertFalse(self.z_link.is_symlink())
        self.assertFalse(self.z_link.exists())

    def test_install_service_sanitizes_dosdevices_on_execution_error(self) -> None:
        installer = Path(self.temp_dir.name) / "setup.exe"
        installer.write_text("dummy installer", encoding="utf-8")

        self.mock_bwrap.execute_in_sandbox.side_effect = self._failing_sandbox_side_effect()
        install_svc = InstallService(repo=self.repo, bwrap_adapter=self.mock_bwrap)

        with patch.object(
            PrefixAuditor,
            "sanitize_dosdevices",
            wraps=PrefixAuditor.sanitize_dosdevices,
        ) as spy_sanitize:
            with self.assertRaises(ExecutionError):
                install_svc.run_installer(installer_path=installer, prefix_id="p-err")

        spy_sanitize.assert_any_call(self.prefix_inner)
        self.assertFalse(self.z_link.is_symlink())
        self.assertFalse(self.z_link.exists())

    def test_winetricks_service_sanitizes_dosdevices_on_execution_error(self) -> None:
        self.mock_bwrap.execute_in_sandbox.side_effect = self._failing_sandbox_side_effect()
        mock_adapter = MagicMock()
        mock_adapter.build_winetricks_cmd.return_value = ["/usr/local/bin/winetricks", "-q", "dxvk"]

        wt_svc = WinetricksService(
            repo=self.repo,
            bwrap_adapter=self.mock_bwrap,
            adapter=mock_adapter,
        )

        with patch.object(
            PrefixAuditor,
            "sanitize_dosdevices",
            wraps=PrefixAuditor.sanitize_dosdevices,
        ) as spy_sanitize:
            with self.assertRaises(ExecutionError):
                wt_svc.run_winetricks("p-err", verbs=["dxvk"], inherit_stdio=False)

        spy_sanitize.assert_any_call(self.prefix_inner)
        self.assertFalse(self.z_link.is_symlink())
        self.assertFalse(self.z_link.exists())


class TestImportServicePrefixLockHardening(unittest.TestCase):
    """Tests that ImportService.import_portable_app enforces PrefixLock concurrency control."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.repo = SqliteRepository(data_root=base / "data", config_root=base / "config")
        mock_bwrap = MagicMock()
        PrefixService(repo=self.repo, bwrap_adapter=mock_bwrap).create_prefix(
            "p-locked",
            initialize_wineboot=False,
        )
        self.p_dir = self.repo.get_prefix_dir("p-locked")

        self.src_app = base / "src_portable"
        self.src_app.mkdir(parents=True, exist_ok=True)
        (self.src_app / "app.exe").write_text("dummy exe", encoding="utf-8")

        self.import_svc = ImportService(repo=self.repo)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_import_portable_app_raises_prefix_lock_error_when_held_by_subprocess(self) -> None:
        lock_file = self.p_dir / "prefix.lock"
        holder_script = (
            "import fcntl, os, sys; "
            "fd = os.open(sys.argv[1], os.O_CREAT | os.O_RDWR, 0o644); "
            "fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); "
            "os.ftruncate(fd, 0); "
            "os.write(fd, f'{os.getpid()}\\n'.encode()); "
            "sys.stdout.write('LOCKED\\n'); "
            "sys.stdout.flush(); "
            "sys.stdin.read()"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", holder_script, str(lock_file)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert proc.stdout is not None
            ready = proc.stdout.readline().strip()
            self.assertEqual(ready, "LOCKED")
            self.assertTrue(PrefixLock.is_locked(self.p_dir))

            with self.assertRaises(PrefixLockError):
                self.import_svc.import_portable_app(
                    source_dir=self.src_app,
                    prefix_id="p-locked",
                    app_id="locked-app",
                    name="Locked App",
                    exe_rel_path="app.exe",
                )

            target_dir = self.p_dir / "prefix" / "drive_c" / "Program Files" / "locked-app"
            self.assertFalse(target_dir.exists())
            with self.assertRaises(ResourceNotFoundError):
                self.repo.load_app("locked-app")
        finally:
            if proc.stdin is not None:
                proc.stdin.close()
            proc.terminate()
            proc.wait(timeout=5)
            if proc.stdout is not None:
                proc.stdout.close()
            if proc.stderr is not None:
                proc.stderr.close()

        self.assertFalse(PrefixLock.is_locked(self.p_dir))
        app = self.import_svc.import_portable_app(
            source_dir=self.src_app,
            prefix_id="p-locked",
            app_id="locked-app",
            name="Locked App",
            exe_rel_path="app.exe",
        )
        self.assertEqual(app.id, "locked-app")

    def test_import_portable_app_raises_prefix_lock_error_when_held_by_prefix_lock(self) -> None:
        with prefix_lock(self.p_dir):
            with self.assertRaises(PrefixLockError):
                self.import_svc.import_portable_app(
                    source_dir=self.src_app,
                    prefix_id="p-locked",
                    app_id="locked-app-2",
                    name="Locked App 2",
                    exe_rel_path="app.exe",
                )


class TestProfileServiceDuplicateHardening(unittest.TestCase):
    """Tests that ProfileService.create_profile rejects duplicate profile IDs."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.repo = SqliteRepository(data_root=base / "data", config_root=base / "config")
        self.service = ProfileService(repo=self.repo)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_create_duplicate_custom_profile_raises_winebox_error(self) -> None:
        created = self.service.create_profile(
            profile_id="dup-profile",
            name="Original Profile",
            network=False,
        )
        self.assertEqual(created.id, "dup-profile")

        with self.assertRaises(WineboxError):
            self.service.create_profile(
                profile_id="dup-profile",
                name="Duplicate Profile",
                network=True,
            )

        stored = self.service.get_profile("dup-profile")
        self.assertEqual(stored.name, "Original Profile")
        self.assertFalse(stored.network)

    def test_create_duplicate_normalized_profile_id_raises_winebox_error(self) -> None:
        self.service.create_profile(profile_id="dup-profile", name="Original Profile")

        with self.assertRaises(WineboxError):
            self.service.create_profile(
                profile_id="  Dup Profile  ",
                name="Normalized Duplicate",
            )

    def test_create_duplicate_builtin_profile_raises_winebox_error(self) -> None:
        with self.assertRaises(WineboxError):
            self.service.create_profile(
                profile_id="permissive",
                name="Shadow Builtin",
            )


if __name__ == "__main__":
    unittest.main()
