"""Library page displaying registered Windows applications and Lutris-style quick controls."""

from gi.repository import Adw, Gtk
from winebox.domain.models import Application
from winebox.infrastructure.process_manager import PrefixLock
from winebox.interface.gui.state import run_async
from winebox.interface.gui.widgets.add_app_dialog import AddAppDialog
from winebox.interface.gui.widgets.configure_app_dialog import ConfigureAppDialog
from winebox.interface.gui.widgets.log_viewer_dialog import LogViewerDialog


class LibraryPage(Gtk.Box):
    """Displays registered apps with search, Play/Kill, Configure, and overflow actions."""

    def __init__(self, window: Adw.ApplicationWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._window = window
        self.set_margin_top(16)
        self.set_margin_bottom(16)
        self.set_margin_start(16)
        self.set_margin_end(16)

        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._search = Gtk.SearchEntry(placeholder_text="Search applications...", hexpand=True)
        self._search.connect("search-changed", lambda *_: self.refresh())
        top_bar.append(self._search)

        add_btn = Gtk.Button(label="+ Add App")
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._on_add_app)
        top_bar.append(add_btn)
        self.append(top_bar)

        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self._list_box = Gtk.ListBox()
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.set_child(self._list_box)
        self.append(scrolled)

    def refresh(self) -> None:
        while child := self._list_box.get_first_child():
            self._list_box.remove(child)

        query = self._search.get_text().strip().lower()
        apps = self._window.services.app_svc.list_apps()
        filtered = [a for a in apps if not query or query in a.name.lower() or query in a.id.lower()]

        if not filtered:
            empty = Adw.ActionRow(
                title="No applications found",
                subtitle="Click '+ Add App' or run 'winebox add' to register a Windows app or game.",
            )
            self._list_box.append(empty)
            return

        for app_obj in filtered:
            p_dir = self._window.services.repo.get_prefix_dir(app_obj.prefix_id)
            is_running = PrefixLock.is_locked(p_dir)
            flags = [
                lbl
                for lbl, enabled in (
                    ("Display", app_obj.policy.display),
                    ("Audio", app_obj.policy.audio),
                    ("Net", app_obj.policy.network),
                    ("GPU", app_obj.policy.gpu),
                    ("Gamepad", app_obj.policy.gamepad),
                    ("HIDRaw", app_obj.policy.hidraw),
                    ("Mic", app_obj.policy.mic),
                )
                if enabled
            ]
            subtitle = (
                f"Prefix: {app_obj.prefix_id}  •  Runner: {app_obj.runner_id}  •  "
                f"Policy: {', '.join(flags) or 'Headless'}"
            )
            row = Adw.ActionRow(title=app_obj.name, subtitle=subtitle)

            if is_running:
                kill_btn = Gtk.Button(label="Kill")
                kill_btn.add_css_class("destructive-action")
                kill_btn.set_valign(Gtk.Align.CENTER)
                kill_btn.connect("clicked", lambda _b, aid=app_obj.id: self._kill_app(aid))
                row.add_suffix(kill_btn)
            else:
                play_btn = Gtk.Button(label="Play")
                play_btn.add_css_class("suggested-action")
                play_btn.set_valign(Gtk.Align.CENTER)
                play_btn.connect("clicked", lambda _b, aid=app_obj.id: self._run_app(aid))
                row.add_suffix(play_btn)

            cfg_btn = Gtk.Button.new_from_icon_name("emblem-system-symbolic")
            cfg_btn.set_valign(Gtk.Align.CENTER)
            cfg_btn.set_tooltip_text("Configure application")
            cfg_btn.connect("clicked", lambda _b, obj=app_obj: self._open_configure(obj))
            row.add_suffix(cfg_btn)

            row.add_suffix(self._build_overflow_button(app_obj))
            self._list_box.append(row)

    def _build_overflow_button(self, app_obj: Application) -> Gtk.MenuButton:
        menu_btn = Gtk.MenuButton(icon_name="view-more-symbolic", valign=Gtk.Align.CENTER)
        menu_btn.add_css_class("flat")
        menu_btn.set_tooltip_text("More actions")

        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)

        has_shortcut = self._window.services.desktop_svc.desktop_entry_exists(app_obj.id)
        shortcut_label = "Remove Desktop Shortcut" if has_shortcut else "Create Desktop Shortcut"

        actions = (
            ("Rename Application", lambda: self._prompt_rename_app(app_obj), False),
            ("View Logs", lambda: self._show_logs(app_obj.prefix_id), False),
            ("Open Prefix Files", lambda: self._window.open_prefix_files(app_obj.prefix_id), False),
            ("Winecfg", lambda: self._run_wine_tool(app_obj.prefix_id, "winecfg", app_obj.runner_id), False),
            ("Winetricks", lambda: self._run_winetricks(app_obj.prefix_id), False),
            (shortcut_label, lambda: self._toggle_shortcut(app_obj.id, has_shortcut), False),
            ("Remove from Library", lambda: self._confirm_remove_app(app_obj), True),
        )
        for label, cb, is_destructive in actions:
            btn = Gtk.Button(label=label, halign=Gtk.Align.FILL)
            btn.add_css_class("flat")
            if is_destructive:
                btn.add_css_class("destructive-action")
            btn.connect("clicked", lambda _b, p=popover, fn=cb: (p.popdown(), fn()))
            box.append(btn)

        popover.set_child(box)
        menu_btn.set_popover(popover)
        return menu_btn

    def _on_add_app(self, *_args: object) -> None:
        dlg = AddAppDialog(
            parent_window=self._window,
            services=self._window.services,
            on_added=lambda msg: (self._window.show_toast(msg), self.refresh()),
        )
        dlg.present(self._window)

    def _open_configure(self, app_obj: Application) -> None:
        dlg = ConfigureAppDialog(
            parent_window=self._window,
            services=self._window.services,
            app_obj=app_obj,
            on_saved=lambda msg: (self._window.show_toast(msg), self.refresh()),
        )
        dlg.present(self._window)

    def _run_app(self, app_id: str) -> None:
        self._window.show_toast(f"Launching '{app_id}'...")
        run_async(
            lambda: self._window.services.exec_svc.run_app(app_id, inherit_stdio=False),
            on_success=lambda rc: (self._window.show_toast(f"'{app_id}' exited ({rc})"), self.refresh()),
            on_error=lambda e: (self._window.show_toast(f"Launch error: {e}"), self.refresh()),
        )

    def _kill_app(self, app_id: str) -> None:
        run_async(
            lambda: self._window.services.app_svc.kill_app(app_id),
            on_success=lambda _: (self._window.show_toast(f"Stopped '{app_id}'"), self.refresh()),
            on_error=lambda e: self._window.show_toast(f"Kill failed: {e}"),
        )

    def _run_wine_tool(self, prefix_id: str, tool_name: str, runner_id: str | None = None) -> None:
        self._window.show_toast(f"Launching {tool_name} in '{prefix_id}'...")
        run_async(
            lambda: self._window.services.prefix_runtime.run_tool(
                prefix_id, tool_name, inherit_stdio=False, runner_id=runner_id
            ),
            on_success=lambda _: (self._window.show_toast(f"{tool_name} closed"), self.refresh()),
            on_error=lambda e: self._window.show_toast(f"{tool_name} error: {e}"),
        )

    def _run_winetricks(self, prefix_id: str) -> None:
        self._window.show_toast(f"Launching Winetricks in '{prefix_id}'...")
        run_async(
            lambda: self._window.services.winetricks_svc.run_winetricks(
                prefix_id, unattended=False, inherit_stdio=False
            ),
            on_success=lambda _: (self._window.show_toast("Winetricks closed"), self.refresh()),
            on_error=lambda e: self._window.show_toast(f"Winetricks error: {e}"),
        )

    def _toggle_shortcut(self, app_id: str, exists: bool) -> None:
        try:
            if exists:
                self._window.services.desktop_svc.remove_desktop_entry(app_id)
                self._window.show_toast(f"Removed desktop shortcut for '{app_id}'")
            else:
                self._window.services.desktop_svc.create_desktop_entry(app_id)
                self._window.show_toast(f"Created desktop shortcut for '{app_id}'")
            self.refresh()
        except Exception as e:
            self._window.show_toast(f"Shortcut error: {e}")

    def _show_logs(self, prefix_id: str) -> None:
        lines = self._window.services.prefix_lifecycle.read_logs(prefix_id, max_lines=200)
        dlg = LogViewerDialog(
            prefix_id=prefix_id,
            lines=lines,
            fetch_logs_fn=self._window.services.prefix_lifecycle.read_logs,
            clear_logs_fn=self._window.services.prefix_lifecycle.clear_logs,
        )
        dlg.present(self._window)

    def _prompt_rename_app(self, app_obj: Application) -> None:
        dlg = Adw.AlertDialog.new("Rename Application", f"Enter a new display name for '{app_obj.name}':")
        entry = Gtk.Entry(text=app_obj.name)
        dlg.set_extra_child(entry)
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("rename", "Rename")
        dlg.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)

        def _on_resp(_d: Adw.AlertDialog, resp: str) -> None:
            if resp != "rename":
                return
            new_name = entry.get_text().strip()
            if not new_name:
                self._window.show_toast("Name cannot be empty")
                return
            try:
                self._window.services.app_svc.update_app(app_obj.id, name=new_name)
                self._window.services.desktop_svc.sync_shortcuts(app_obj.id)
                self._window.show_toast(f"Renamed to '{new_name}'")
                self.refresh()
            except Exception as e:
                self._window.show_toast(f"Rename failed: {e}")

        dlg.connect("response", _on_resp)
        dlg.present(self._window)

    def _confirm_remove_app(self, app_obj: Application) -> None:
        dlg = Adw.AlertDialog.new(
            f"Remove '{app_obj.name}'?",
            "Removes the application registration from Library (prefix files on disk are preserved).",
        )
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("remove", "Remove")
        dlg.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)

        def _on_resp(_d: Adw.AlertDialog, resp: str) -> None:
            if resp == "remove":
                self._remove_app(app_obj.id)

        dlg.connect("response", _on_resp)
        dlg.present(self._window)

    def _remove_app(self, app_id: str) -> None:
        try:
            self._window.services.app_svc.remove_app(app_id)
            self._window.show_toast(f"Removed '{app_id}'")
            self.refresh()
        except Exception as e:
            self._window.show_toast(f"Error: {e}")
