"""Prefixes management page with Quick Wine Tools, Backup/Restore, and File Manager."""

from typing import List, Optional
from gi.repository import Adw, Gtk
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

        # Action toolbar: Winecfg, Regedit, CMD, Audit, Backup, Kill
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for label, fn in (
            ("Winecfg", lambda: self._run_tool("winecfg")),
            ("Regedit", lambda: self._run_tool("regedit")),
            ("CMD", lambda: self._run_tool("cmd")),
            ("Audit", self._audit_prefix),
            ("Backup", self._backup_prefix),
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
        self._window.show_toast(f"Creating snapshot backup for '{pid}'...")
        run_async(
            lambda: self._window.services.prefix_backup.backup_prefix(pid),
            on_success=lambda path: self._window.show_toast(f"Backup saved: {path.name}"),
            on_error=lambda e: self._window.show_toast(f"Backup failed: {e}"),
        )

    def _kill_prefix(self) -> None:
        pid = self._selected_prefix_id()
        if not pid:
            return
        run_async(
            lambda: self._window.services.prefix_runtime.kill_prefix(pid),
            on_success=lambda _: (self._window.show_toast(f"Terminated '{pid}'"), self._update_selected_view()),
            on_error=lambda e: self._window.show_toast(f"Kill failed: {e}"),
        )
