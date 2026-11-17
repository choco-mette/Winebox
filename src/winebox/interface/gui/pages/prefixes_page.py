"""Prefixes management page with Quick Wine Tools, Backup/Restore, and File Manager."""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from gi.repository import Adw, Gio, Gtk
from winebox.infrastructure.backup_adapter import BackupAdapter
from winebox.infrastructure.process_manager import PrefixLock
from winebox.interface.gui.state import run_async
from winebox.interface.gui.widgets.prefix_file_manager import PrefixFileManager


class PrefixesPage(Gtk.Box):
    """Manages Wine prefixes, sandboxed tools, snapshots, and embedded file browsing."""

    def __init__(self, window: Adw.ApplicationWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._window = window
        self._prefix_ids: List[str] = []
        self.set_margin_top(16)
        self.set_margin_bottom(16)
        self.set_margin_start(16)
        self.set_margin_end(16)

        # Prefix selector + create button
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._prefix_dropdown = Gtk.DropDown.new_from_strings([])
        self._prefix_dropdown.set_hexpand(True)
        self._prefix_dropdown.connect("notify::selected", self._on_prefix_changed)
        header_box.append(self._prefix_dropdown)

        self._status_label = Gtk.Label(label="Idle")
        self._status_label.add_css_class("dim-label")
        header_box.append(self._status_label)

        new_btn = Gtk.Button(label="+ New Prefix")
        new_btn.add_css_class("suggested-action")
        new_btn.connect("clicked", self._on_new_prefix)
        header_box.append(new_btn)
        self.append(header_box)

        # Action toolbar: Winecfg, Regedit, CMD, Audit, Backup, Restore, Kill
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for label, fn in (
            ("Winecfg", lambda: self._run_tool("winecfg")),
            ("Regedit", lambda: self._run_tool("regedit")),
            ("CMD", lambda: self._run_tool("cmd")),
            ("Audit", self._audit_prefix),
            ("Backup", self._backup_prefix),
            ("Restore", self._restore_prefix),
            ("Kill", self._kill_prefix),
        ):
            btn = Gtk.Button(label=label)
            if label == "Kill":
                btn.add_css_class("destructive-action")
            btn.connect("clicked", lambda _b, cb=fn: cb())
            actions.append(btn)
        self.append(actions)

        # Embedded Prefix File Manager
        self._file_manager = PrefixFileManager(
            window=window,
            services=window.services,
            on_refresh_apps=lambda: window.pages["library"].refresh(),
        )
        self.append(self._file_manager)

    def _selected_prefix_id(self) -> Optional[str]:
        idx = self._prefix_dropdown.get_selected()
        if idx == Gtk.INVALID_LIST_POSITION or idx >= len(self._prefix_ids):
            return None
        return self._prefix_ids[idx]

    def refresh(self) -> None:
        current = self._selected_prefix_id()
        prefixes = self._window.services.prefix_lifecycle.list_prefixes()
        self._prefix_ids = [p.id for p in prefixes]
        self._prefix_dropdown.set_model(Gtk.StringList.new(self._prefix_ids or ["(no prefixes)"]))
        if current and current in self._prefix_ids:
            self._prefix_dropdown.set_selected(self._prefix_ids.index(current))
        elif self._prefix_ids:
            self._prefix_dropdown.set_selected(0)
        self._update_selected_view()

    def select_prefix(self, prefix_id: str) -> None:
        """Select the given prefix in the dropdown and load its file manager view."""
        if prefix_id not in self._prefix_ids:
            self.refresh()
        if prefix_id in self._prefix_ids:
            self._prefix_dropdown.set_selected(self._prefix_ids.index(prefix_id))
            self._update_selected_view()

    def _on_prefix_changed(self, *_args: object) -> None:
        self._update_selected_view()

    def _update_selected_view(self) -> None:
        pid = self._selected_prefix_id()
        if not pid:
            self._status_label.set_text("No prefix")
            self._file_manager.set_prefix(None)
            return
        p_dir = self._window.services.repo.get_prefix_dir(pid)
        self._status_label.set_text("Running" if PrefixLock.is_locked(p_dir) else "Idle")
        self._file_manager.set_prefix(pid)

    def _on_new_prefix(self, *_args: object) -> None:
        dlg = Adw.AlertDialog.new("Create New Prefix", "Enter a lowercase ID (e.g. gaming-pfx):")
        entry = Gtk.Entry(placeholder_text="my-prefix")
        dlg.set_extra_child(entry)
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("create", "Create")
        dlg.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)

        def _on_resp(_d: Adw.AlertDialog, resp: str) -> None:
            pid = entry.get_text().strip().lower().replace(" ", "-")
            if resp != "create" or not pid:
                return
            self._window.show_toast(f"Creating prefix '{pid}'...")
            run_async(
                lambda: self._window.services.prefix_lifecycle.create_prefix(pid),
                on_success=lambda _: (self._window.show_toast(f"Created '{pid}'"), self.refresh()),
                on_error=lambda e: self._window.show_toast(f"Create failed: {e}"),
            )

        dlg.connect("response", _on_resp)
        dlg.present(self._window)

    def _run_tool(self, tool_name: str) -> None:
        pid = self._selected_prefix_id()
        if not pid:
            return
        self._window.show_toast(f"Launching {tool_name} in '{pid}'...")
        run_async(
            lambda: self._window.services.prefix_runtime.run_tool(pid, tool_name, inherit_stdio=False),
            on_success=lambda _: (self._window.show_toast(f"{tool_name} closed"), self._update_selected_view()),
            on_error=lambda e: self._window.show_toast(f"Tool error: {e}"),
        )

    def _audit_prefix(self) -> None:
        pid = self._selected_prefix_id()
        if not pid:
            return
        try:
            issues = self._window.services.prefix_lifecycle.audit_prefix(pid)
            msg = f"Audit clean for '{pid}'" if not issues else f"Audit found {len(issues)} issue(s)"
            self._window.show_toast(msg)
        except Exception as e:
            self._window.show_toast(f"Audit error: {e}")

    def _backup_prefix(self) -> None:
        pid = self._selected_prefix_id()
        if not pid:
            return
        backups_dir = self._window.services.repo.data_root / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        default_filename = f"{pid}_{ts}{BackupAdapter.default_extension()}"

        dlg = Gtk.FileDialog(title=f"Save Backup for '{pid}'")
        dlg.set_initial_folder(Gio.File.new_for_path(str(backups_dir)))
        dlg.set_initial_name(default_filename)

        def _on_save_chosen(dialog: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
            try:
                gfile = dialog.save_finish(res)
                if not gfile or not gfile.get_path():
                    return
                chosen_path = Path(gfile.get_path())
                self._window.show_toast(f"Creating snapshot backup for '{pid}'...")
                run_async(
                    lambda: self._window.services.prefix_backup.backup_prefix(pid, output_path=chosen_path),
                    on_success=lambda path: self._window.show_toast(f"Backup saved: {path.name}"),
                    on_error=lambda e: self._window.show_toast(f"Backup failed: {e}"),
                )
            except Exception:
                pass

        dlg.save(self._window, None, _on_save_chosen)

    def _restore_prefix(self) -> None:
        backups_dir = self._window.services.repo.data_root / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)

        dlg = Gtk.FileDialog(title="Select Prefix Backup Archive")
        if backups_dir.is_dir():
            dlg.set_initial_folder(Gio.File.new_for_path(str(backups_dir)))

        tar_filter = Gtk.FileFilter()
        tar_filter.set_name("Backup Archives (*.tar.zst, *.tar.gz, *.tgz)")
        for pat in ("*.tar.zst", "*.tar.gz", "*.tgz"):
            tar_filter.add_pattern(pat)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(tar_filter)
        dlg.set_filters(filters)

        def _on_open_chosen(dialog: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
            try:
                gfile = dialog.open_finish(res)
                if not gfile or not gfile.get_path():
                    return
                archive_path = Path(gfile.get_path())
                self._prompt_restore_options(archive_path)
            except Exception:
                pass

        dlg.open(self._window, None, _on_open_chosen)

    def _prompt_restore_options(self, archive_path: Path) -> None:
        dlg = Adw.AlertDialog.new("Restore Prefix Backup", f"Archive: {archive_path.name}")
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content_box.set_margin_top(8)
        content_box.set_margin_bottom(8)

        id_entry = Gtk.Entry(placeholder_text="Target Prefix ID (leave empty to use original)")
        content_box.append(id_entry)

        force_chk = Gtk.CheckButton(label="Overwrite if prefix already exists")
        content_box.append(force_chk)

        dlg.set_extra_child(content_box)
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("restore", "Restore")
        dlg.set_response_appearance("restore", Adw.ResponseAppearance.SUGGESTED)

        def _on_resp(_d: Adw.AlertDialog, resp: str) -> None:
            if resp != "restore":
                return
            target_id = id_entry.get_text().strip().lower().replace(" ", "-") or None
            force = force_chk.get_active()

            self._window.show_toast(f"Restoring '{archive_path.name}'...")
            run_async(
                lambda: self._window.services.prefix_backup.restore_prefix(
                    archive_path=archive_path,
                    target_prefix_id=target_id,
                    force=force,
                ),
                on_success=lambda restored: (
                    self._window.show_toast(f"Restored prefix '{restored.id}'"),
                    self.refresh(),
                    self.select_prefix(restored.id),
                    self._window.pages["library"].refresh(),
                ),
                on_error=lambda e: self._window.show_toast(f"Restore failed: {e}"),
            )

        dlg.connect("response", _on_resp)
        dlg.present(self._window)

    def _kill_prefix(self) -> None:
        pid = self._selected_prefix_id()
        if not pid:
            return
        run_async(
            lambda: self._window.services.prefix_runtime.kill_prefix(pid),
            on_success=lambda _: (self._window.show_toast(f"Terminated '{pid}'"), self._update_selected_view()),
            on_error=lambda e: self._window.show_toast(f"Kill failed: {e}"),
        )
