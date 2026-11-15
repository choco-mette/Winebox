"""Library page displaying registered Windows applications and quick launch controls."""

from gi.repository import Adw, Gtk
from winebox.infrastructure.process_manager import PrefixLock
from winebox.interface.gui.state import run_async
from winebox.interface.gui.widgets.add_app_dialog import AddAppDialog
from winebox.interface.gui.widgets.log_viewer_dialog import LogViewerDialog


class LibraryPage(Gtk.Box):
    """Displays registered apps with search, launch/kill, logs, and desktop shortcut toggle."""

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

            logs_btn = Gtk.Button(label="Logs")
            logs_btn.set_valign(Gtk.Align.CENTER)
            logs_btn.connect("clicked", lambda _b, pid=app_obj.prefix_id: self._show_logs(pid))
            row.add_suffix(logs_btn)

            del_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
            del_btn.add_css_class("flat")
            del_btn.set_valign(Gtk.Align.CENTER)
            del_btn.set_tooltip_text("Remove registration")
            del_btn.connect("clicked", lambda _b, aid=app_obj.id: self._remove_app(aid))
            row.add_suffix(del_btn)

            self._list_box.append(row)

    def _on_add_app(self, *_args: object) -> None:
        dlg = AddAppDialog(
            parent_window=self._window,
            services=self._window.services,
            on_added=lambda msg: (self._window.show_toast(msg), self.refresh()),
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

    def _show_logs(self, prefix_id: str) -> None:
        lines = self._window.services.prefix_lifecycle.read_logs(prefix_id, max_lines=100)
        LogViewerDialog(prefix_id, lines).present(self._window)

    def _remove_app(self, app_id: str) -> None:
        try:
            self._window.services.app_svc.remove_app(app_id)
            self._window.show_toast(f"Removed '{app_id}'")
            self.refresh()
        except Exception as e:
            self._window.show_toast(f"Error: {e}")
