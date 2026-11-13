import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from winebox.application.app_service import AppService
from winebox.application.execution_service import ExecutionService
from winebox.application.import_service import ImportService
from winebox.application.prefix_service import PrefixService
from winebox.domain.models import Application, Prefix, SecurityPolicy
from winebox.infrastructure.sqlite_repository import SqliteRepository


class TestServices(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.repo = SqliteRepository(data_root=base / "data", config_root=base / "config")
        self.mock_bwrap = MagicMock()
        self.mock_bwrap.execute_in_sandbox.return_value.returncode = 0

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_prefix_service_create(self):
        svc = PrefixService(repo=self.repo, bwrap_adapter=self.mock_bwrap)
        prefix = svc.create_prefix("my-test-prefix", name="Test Prefix", initialize_wineboot=True)
        self.assertEqual(prefix.id, "my-test-prefix")
        self.assertTrue(self.mock_bwrap.execute_in_sandbox.called)

        # Check prefix folder
        p_dir = self.repo.get_prefix_dir("my-test-prefix")
        self.assertTrue((p_dir / "prefix").exists())
        self.assertTrue((p_dir / "home").exists())

    def test_app_service_crud(self):
        prefix_svc = PrefixService(repo=self.repo, bwrap_adapter=self.mock_bwrap)
        prefix_svc.create_prefix("p1", initialize_wineboot=False)

        svc = AppService(repo=self.repo)
        app = svc.register_app(
            app_id="app1",
            name="Application One",
            prefix_id="p1",
            exe_path="drive_c/app.exe",
        )
        self.assertEqual(app.id, "app1")

        loaded = svc.get_app("app1")
        self.assertEqual(loaded.name, "Application One")

        all_apps = svc.list_apps()
        self.assertEqual(len(all_apps), 1)

        svc.remove_app("app1")
        self.assertEqual(len(svc.list_apps()), 0)

    def test_execution_service_flow(self):
        prefix_svc = PrefixService(repo=self.repo, bwrap_adapter=self.mock_bwrap)
        prefix_svc.create_prefix("p-exec", initialize_wineboot=False)

        app_svc = AppService(repo=self.repo)
        app_svc.register_app(
            app_id="exec-app",
            name="Executable App",
            prefix_id="p-exec",
            exe_path="drive_c/app.exe",
        )

        exec_svc = ExecutionService(repo=self.repo, bwrap_adapter=self.mock_bwrap)
        exec_svc.run_app("exec-app")

        self.assertTrue(self.mock_bwrap.execute_in_sandbox.called)

    def test_import_portable_app(self):
        # Setup prefix
        prefix_svc = PrefixService(repo=self.repo, bwrap_adapter=self.mock_bwrap)
        prefix_svc.create_prefix("p-port", initialize_wineboot=False)

        # Create dummy source portable app
        src_app = Path(self.temp_dir.name) / "src_portable"
        src_app.mkdir()
        (src_app / "editor.exe").write_text("dummy exe")

        import_svc = ImportService(repo=self.repo)
        app = import_svc.import_portable_app(
            source_dir=src_app,
            prefix_id="p-port",
            app_id="portable-editor",
            name="Portable Editor",
            exe_rel_path="editor.exe",
        )

        self.assertEqual(app.id, "portable-editor")
        target_exe = (
            self.repo.get_prefix_dir("p-port")
            / "prefix"
            / "drive_c"
            / "Program Files"
            / "portable-editor"
            / "editor.exe"
        )
        self.assertTrue(target_exe.exists())


if __name__ == "__main__":
    unittest.main()

