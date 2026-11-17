"""Unit tests for the GTK4 + Libadwaita GUI Launcher state, safety helpers, and CLI entrypoint."""

import builtins
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from winebox.common.exceptions import WineboxError
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.interface.cli import app
from winebox.interface.gui import launch_gui
from winebox.interface.gui.state import ServiceContainer, format_size, list_prefix_directory


class TestGuiStateAndFileManager(unittest.TestCase):
    def test_list_prefix_directory_sorting_and_symlink_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "drive_c"
            (root / "Program Files").mkdir(parents=True)
            (root / "app.exe").write_bytes(b"MZ" * 100)
            (root / "readme.txt").write_text("hi")
            (root / "escape_link").symlink_to("/etc/passwd")

            entries = list_prefix_directory(root)
            self.assertEqual([e.name for e in entries], ["Program Files", "app.exe", "escape_link", "readme.txt"])
            self.assertTrue(entries[0].is_dir)
            self.assertFalse(entries[0].is_symlink)
            self.assertTrue(entries[2].is_symlink)
            self.assertFalse(entries[2].is_dir)

            with self.assertRaises(WineboxError):
                list_prefix_directory(root, "../outside")
            with self.assertRaises(WineboxError):
                list_prefix_directory(root, "/etc")

    def test_format_size_and_service_container(self) -> None:
        self.assertEqual(format_size(512), "512 B")
        self.assertEqual(format_size(2048), "2.0 KB")
        with tempfile.TemporaryDirectory() as tmp:
            repo = SqliteRepository(
                data_root=Path(tmp) / "data",
                config_root=Path(tmp) / "cfg",
            )
            container = ServiceContainer(repo=repo)
            self.assertEqual(container.repo, repo)
            self.assertGreaterEqual(len(container.profile_svc.list_profiles()), 4)


class TestGuiCliAndApp(unittest.TestCase):
    def setUp(self) -> None:
        self.cli = CliRunner()

    def test_gui_help(self) -> None:
        res = self.cli.invoke(app, ["gui", "--help"])
        self.assertEqual(res.exit_code, 0)
        self.assertIn("GTK4", res.output)

    def test_launch_gui_raises_clear_error_when_gi_missing(self) -> None:
        real_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "gi":
                raise ImportError("No module named 'gi'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(WineboxError) as ctx:
                launch_gui()
            self.assertIn("PyGObject", str(ctx.exception))

    def test_gtk4_modules_import_and_window_instantiates_when_display_available(self) -> None:
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            self.skipTest("No active X11/Wayland display for GTK4 widget instantiation")
        try:
            import gi

            gi.require_version("Gtk", "4.0")
            gi.require_version("Adw", "1")
        except (ImportError, ValueError):
            self.skipTest("GTK4 / Libadwaita not available")

        from gi.repository import Gio
        from winebox.domain.models import HostMount, MountMode, Prefix, SecurityPolicy
        from winebox.interface.gui.app import WineboxGuiApp
        from winebox.interface.gui.widgets.configure_app_dialog import ConfigureAppDialog

        with tempfile.TemporaryDirectory() as tmp:
            repo = SqliteRepository(data_root=Path(tmp) / "data", config_root=Path(tmp) / "cfg")
            services = ServiceContainer(repo=repo)
            repo.save_prefix(Prefix(id="pfx-gui", name="pfx-gui"))
            app_obj = services.app_svc.register_app(
                app_id="demo-app",
                name="Demo App",
                prefix_id="pfx-gui",
                exe_path="drive_c/demo.exe",
                arguments=["-windowed"],
                policy=SecurityPolicy(
                    hidraw=True,
                    mic=False,
                    env_vars={"DXVK_HUD": "fps"},
                    host_mounts=[HostMount(host_path=Path(tmp), sandbox_path=Path("/mnt/save"), mode=MountMode.RO)],
                ),
            )

            gui_app = WineboxGuiApp(services=services)
            self.assertEqual(gui_app.get_application_id(), "id.winebox.WineBox")
            gui_app.set_flags(Gio.ApplicationFlags.NON_UNIQUE)
            gui_app.register(None)
            gui_app.activate()
            win = gui_app._window
            assert win is not None
            for page in win.pages.values():
                page.refresh()

            dlg = ConfigureAppDialog(
                parent_window=win,
                services=services,
                app_obj=app_obj,
                on_saved=lambda _msg: None,
            )
            dlg.present(win)
            self.assertIsNotNone(dlg._stack.get_child_by_name("app"))
            self.assertIsNotNone(dlg._stack.get_child_by_name("sandbox"))
            self.assertIsNotNone(dlg._stack.get_child_by_name("system"))
            self.assertIsNotNone(dlg._stack.get_child_by_name("shortcut"))

            # Test shortcut tab rename field & bidirectional sync
            self.assertEqual(dlg._sc_name_row.get_text(), app_obj.name)
            dlg._sc_name_row.set_text("GUI Renamed App")
            self.assertEqual(dlg._name_row.get_text(), "GUI Renamed App")

            dlg._name_row.set_text("GUI App Final Name")
            self.assertEqual(dlg._sc_name_row.get_text(), "GUI App Final Name")

            saved_messages = []
            dlg._on_saved = lambda msg: saved_messages.append(msg)
            dlg._on_save_clicked()
            self.assertTrue(any("GUI App Final Name" in m for m in saved_messages))
            reloaded_app = services.app_svc.get_app("demo-app")
            self.assertEqual(reloaded_app.name, "GUI App Final Name")

            # Test library page prompt rename app
            lib_page = win.pages["library"]
            lib_page._prompt_rename_app(reloaded_app)

            win.open_prefix_files("pfx-gui")
            win.close()

    def test_shortcut_settings_sqlite_persistence_and_sync(self) -> None:
        from winebox.application.desktop_service import DesktopService
        from winebox.domain.models import Prefix, ShortcutSettings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = SqliteRepository(data_root=root / "data", config_root=root / "cfg")
            services = ServiceContainer(repo=repo)
            repo.save_prefix(Prefix(id="pfx-sc", name="pfx-sc"))
            services.app_svc.register_app(
                app_id="sc-app",
                name="Shortcut App",
                prefix_id="pfx-sc",
                exe_path="drive_c/sc.exe",
            )

            sc = ShortcutSettings(
                menu_enabled=True,
                desktop_enabled=True,
                icon="steam",
                categories="Game;",
                comment="Launch Shortcut App",
                terminal=True,
                startup_wm_class="sc.exe",
            )
            services.app_svc.update_app("sc-app", shortcut=sc)
            reloaded = repo.load_app("sc-app")
            self.assertEqual(reloaded.shortcut, sc)

            apps_dir = root / "applications"
            desktop_dir = root / "Desktop"
            ds = DesktopService(repo=repo, apps_dir=apps_dir, desktop_dir=desktop_dir)
            paths = ds.sync_shortcuts("sc-app")
            self.assertIsNotNone(paths["menu"])
            self.assertIsNotNone(paths["desktop"])
            assert paths["menu"] is not None and paths["desktop"] is not None
            self.assertTrue(paths["menu"].exists())
            self.assertTrue(paths["desktop"].exists())
            self.assertTrue(os.access(paths["desktop"], os.X_OK))

            content = paths["desktop"].read_text(encoding="utf-8")
            self.assertIn("Icon=steam", content)
            self.assertIn("Terminal=true", content)
            self.assertIn("StartupWMClass=sc.exe", content)
            self.assertIn("Categories=Game;", content)

            services.app_svc.update_app(
                "sc-app",
                shortcut=ShortcutSettings(menu_enabled=False, desktop_enabled=False, icon="steam"),
            )
            ds.sync_shortcuts("sc-app")
            self.assertFalse(paths["menu"].exists())
            self.assertFalse(paths["desktop"].exists())
            self.assertEqual(repo.load_app("sc-app").shortcut.icon, "steam")

    def test_kill_prefix_never_kills_self_gui_process(self) -> None:
        from winebox.domain.models import Prefix
        from winebox.infrastructure.process_manager import prefix_lock

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = SqliteRepository(data_root=root / "data", config_root=root / "cfg")
            services = ServiceContainer(repo=repo)
            repo.save_prefix(Prefix(id="pfx-kill", name="pfx-kill"))
            p_dir = repo.get_prefix_dir("pfx-kill")
            (p_dir / "prefix" / "dosdevices").mkdir(parents=True, exist_ok=True)

            with prefix_lock(p_dir):
                # prefix.lock records os.getpid() (simulating WineBox GUI launching in background thread)
                res = services.prefix_runtime.kill_prefix("pfx-kill")
                self.assertNotIn(os.getpid(), res["killed_pids"])

    def test_run_tool_cmd_uses_wineconsole_when_non_interactive(self) -> None:
        from unittest.mock import MagicMock
        from winebox.application.prefix.runtime import PrefixRuntimeService
        from winebox.domain.models import Prefix

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = SqliteRepository(data_root=root / "data", config_root=root / "cfg")
            repo.save_prefix(Prefix(id="pfx-cmd", name="pfx-cmd"))
            p_dir = repo.get_prefix_dir("pfx-cmd")
            (p_dir / "prefix" / "dosdevices").mkdir(parents=True, exist_ok=True)

            mock_bwrap = MagicMock()
            mock_bwrap.execute_in_sandbox.return_value = MagicMock(returncode=0, stderr="")
            rt = PrefixRuntimeService(repo=repo, bwrap_adapter=mock_bwrap)
            rt.run_tool("pfx-cmd", "cmd", inherit_stdio=False)

            called_cmd = mock_bwrap.execute_in_sandbox.call_args.kwargs["command_inside"]
            self.assertIn("wineconsole", called_cmd)
            self.assertIn("cmd", called_cmd)

    def test_app_service_update_app_and_policy_validation(self) -> None:
        from winebox.common.exceptions import PolicyValidationError
        from winebox.domain.models import HostMount, MountMode, Prefix, SecurityPolicy

        with tempfile.TemporaryDirectory() as tmp:
            repo = SqliteRepository(data_root=Path(tmp) / "data", config_root=Path(tmp) / "cfg")
            services = ServiceContainer(repo=repo)
            repo.save_prefix(Prefix(id="pfx-upd", name="pfx-upd"))
            services.app_svc.register_app(
                app_id="upd-app",
                name="Old Name",
                prefix_id="pfx-upd",
                exe_path="drive_c/old.exe",
            )

            save_dir = Path(tmp) / "saves"
            save_dir.mkdir()
            updated = services.app_svc.update_app(
                "upd-app",
                name="New Name",
                exe_path="drive_c/new.exe",
                arguments=["-dx11", "--fps=60"],
                profile_id="balanced",
                policy=SecurityPolicy(
                    display=True,
                    audio=True,
                    network=False,
                    gpu=True,
                    gamepad=True,
                    hidraw=True,
                    mic=True,
                    env_vars={"DXVK_HUD": "fps"},
                    host_mounts=[HostMount(host_path=save_dir, sandbox_path=Path("/mnt/saves"), mode=MountMode.RW)],
                ),
            )
            self.assertEqual(updated.name, "New Name")
            self.assertEqual(updated.exe_path, "drive_c/new.exe")
            self.assertEqual(updated.arguments, ["-dx11", "--fps=60"])
            self.assertEqual(updated.profile_id, "balanced")
            self.assertTrue(updated.policy.hidraw)
            self.assertTrue(updated.policy.mic)
            self.assertEqual(updated.policy.env_vars, {"DXVK_HUD": "fps"})
            self.assertEqual(len(updated.policy.host_mounts), 1)

            with self.assertRaises(PolicyValidationError):
                services.app_svc.update_app(
                    "upd-app",
                    policy=SecurityPolicy(
                        host_mounts=[HostMount(host_path=Path("/etc"), sandbox_path=Path("/mnt/etc"), mode=MountMode.RO)]
                    ),
                )

    def test_prefixes_page_backup_and_restore_actions(self) -> None:
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            self.skipTest("No active display")
        try:
            import gi

            gi.require_version("Gtk", "4.0")
            gi.require_version("Adw", "1")
        except (ImportError, ValueError):
            self.skipTest("GTK4 / Libadwaita not available")

        from gi.repository import Gio, Gtk
        from winebox.domain.models import Prefix
        from winebox.interface.gui.app import WineboxGuiApp

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = SqliteRepository(data_root=root / "data", config_root=root / "cfg")
            services = ServiceContainer(repo=repo)
            repo.save_prefix(Prefix(id="pfx-bk", name="pfx-bk"))
            p_dir = repo.get_prefix_dir("pfx-bk")
            (p_dir / "prefix" / "drive_c").mkdir(parents=True, exist_ok=True)
            (p_dir / "home").mkdir(parents=True, exist_ok=True)

            gui_app = WineboxGuiApp(services=services)
            gui_app.set_application_id("id.winebox.WineBox.TestBackup")
            gui_app.set_flags(Gio.ApplicationFlags.NON_UNIQUE)
            gui_app.register(None)
            gui_app.activate()
            win = gui_app._window
            assert win is not None

            pfx_page = win.pages["prefixes"]
            pfx_page.refresh()

            # Find action buttons
            action_labels = []
            for child in pfx_page:
                if isinstance(child, Gtk.Box) and child.get_orientation() == Gtk.Orientation.HORIZONTAL:
                    for sub in child:
                        if isinstance(sub, Gtk.Button) and sub.get_label():
                            action_labels.append(sub.get_label())

            self.assertIn("Backup", action_labels)
            self.assertIn("Restore", action_labels)
            self.assertIn("Logs", action_labels)

            # Test custom path backup
            custom_backup = root / "custom_backup.tar.gz"
            saved_path = services.prefix_backup.backup_prefix("pfx-bk", output_path=custom_backup)
            self.assertTrue(saved_path.exists())

            # Test restore dialog prompt instantiation
            pfx_page._confirm_restore("pfx-bk", saved_path)

            # Test LogViewerDialog instantiation and actions
            from winebox.interface.gui.widgets.log_viewer_dialog import LogViewerDialog

            recorded_logs = ["line 1", "line 2"]
            cleared = []

            dlg = LogViewerDialog(
                prefix_id="pfx-bk",
                lines=recorded_logs,
                fetch_logs_fn=lambda _pid, _n: recorded_logs,
                clear_logs_fn=lambda pid: cleared.append(pid),
            )
            self.assertEqual(dlg._prefix_id, "pfx-bk")
            self.assertIn("line 1", dlg._last_content)

            recorded_logs.append("line 3")
            dlg.refresh_logs()
            self.assertIn("line 3", dlg._last_content)

            dlg._confirm_clear_logs()

            # Test GroupAssignmentDialog & Library expanders
            from winebox.interface.gui.widgets.group_assignment_dialog import GroupAssignmentDialog

            # Create sample group
            grp = services.group_svc.create_group("Retro Games", group_id="retro")

            # Register app and open GroupAssignmentDialog
            demo_app = services.app_svc.register_app(
                app_id="bk-app",
                name="Backup App",
                prefix_id="pfx-bk",
                exe_path="drive_c/app.exe",
            )
            grp_dlg = GroupAssignmentDialog(
                parent_window=win,
                services=services,
                app_obj=demo_app,
                on_saved=lambda gids: None,
            )
            grp_dlg.present(win)
            self.assertIn("retro", grp_dlg._check_buttons)
            grp_dlg._check_buttons["retro"].set_active(True)
            grp_dlg._on_save_clicked()

            self.assertIn("retro", services.repo.get_app_group_ids("bk-app"))

            # Refresh library and verify expanders created
            lib_page = win.pages["library"]
            lib_page.refresh()
            expanders = [ch for ch in lib_page._content_box if isinstance(ch, Gtk.Expander)]
            self.assertTrue(len(expanders) >= 1)

            # Test OperationProgressDialog success and error states
            from winebox.interface.gui.widgets.operation_progress_dialog import OperationProgressDialog

            success_results = []
            prog_dlg = OperationProgressDialog(
                title="Test Task",
                task_fn=lambda: "Finished test output",
                parent_window=win,
                on_success=lambda res: success_results.append(res),
            )
            prog_dlg.present(win)
            self.assertFalse(prog_dlg._close_btn.get_sensitive())
            # Directly execute success handler to test state transition
            prog_dlg._handle_task_success("Finished test output")
            self.assertTrue(prog_dlg._is_completed)
            self.assertTrue(prog_dlg._close_btn.get_sensitive())
            self.assertEqual(prog_dlg._icon_stack.get_visible_child_name(), "success")
            prog_dlg._on_close_clicked()
            self.assertEqual(success_results, ["Finished test output"])

            # Test error handler state transition
            error_captured = []
            err_dlg = OperationProgressDialog(
                title="Failing Task",
                task_fn=lambda: None,
                parent_window=win,
                on_error=lambda err: error_captured.append(str(err)),
            )
            err_dlg.present(win)
            err_dlg._handle_task_error(RuntimeError("Task failed hard"))
            self.assertTrue(err_dlg._is_completed)
            self.assertTrue(err_dlg._close_btn.get_sensitive())
            self.assertEqual(err_dlg._icon_stack.get_visible_child_name(), "error")
            err_dlg._on_close_clicked()
            self.assertIn("Task failed hard", error_captured)

            # Test UpdateDialog instantiation
            from winebox.application.update_service import UpdateInfo
            from winebox.interface.gui.widgets.update_dialog import UpdateDialog

            up_info = UpdateInfo(
                current_version="0.1.0",
                latest_version="0.1.1",
                has_update=True,
                release_title="Release v0.1.1",
                release_notes="* New features\n* Bug fixes",
                html_url="https://github.com/example",
                assets=[],
                matching_asset={"name": "winebox_0.1.1_all.deb", "browser_download_url": "http://deb"},
                is_git_install=True,
                distro_family="debian",
            )
            up_dlg = UpdateDialog(parent_window=win, services=services, update_info=up_info)
            up_dlg.present(win)
            self.assertIsNotNone(up_dlg._update_btn)
            up_dlg.close()

            win.close()


if __name__ == "__main__":
    unittest.main()
