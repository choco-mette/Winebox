"""Log viewer dialog for Wine prefix execution logs."""

from typing import Callable, List, Optional
from gi.repository import Adw, Gdk, GLib, Gtk


class LogViewerDialog(Adw.Dialog):
    """Displays real-time execution log lines for a prefix with refresh, copy, and clear."""

    def __init__(
        self,
        prefix_id: str,
        lines: Optional[List[str]] = None,
        fetch_logs_fn: Optional[Callable[[str, int], List[str]]] = None,
        clear_logs_fn: Optional[Callable[[str], None]] = None,
        max_lines: int = 500,
    ) -> None:
        super().__init__(title=f"Logs: {prefix_id}", content_width=780, content_height=520)
        self._prefix_id = prefix_id
        self._fetch_logs_fn = fetch_logs_fn
        self._clear_logs_fn = clear_logs_fn
        self._max_lines = max_lines
        self._timeout_id: Optional[int] = None
        self._last_content: str = ""

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()

        # Action buttons in header
        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Refresh logs")
        refresh_btn.connect("clicked", lambda _: self.refresh_logs())
        header.pack_start(refresh_btn)

        copy_btn = Gtk.Button(icon_name="edit-copy-symbolic", tooltip_text="Copy all logs to clipboard")
        copy_btn.connect("clicked", lambda _: self._copy_to_clipboard())
        header.pack_start(copy_btn)

        if self._clear_logs_fn is not None:
            clear_btn = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Clear logs")
            clear_btn.add_css_class("destructive-action")
            clear_btn.connect("clicked", lambda _: self._confirm_clear_logs())
            header.pack_end(clear_btn)

        toolbar.add_top_bar(header)

        self._scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self._text_view = Gtk.TextView(editable=False, monospace=True)
        self._text_view.set_top_margin(10)
        self._text_view.set_bottom_margin(10)
        self._text_view.set_left_margin(12)
        self._text_view.set_right_margin(12)
        self._buffer = self._text_view.get_buffer()

        initial_content = "\n".join(lines) if lines else ""
        self._set_content(initial_content)

        self._scrolled.set_child(self._text_view)
        toolbar.set_content(self._scrolled)
        self.set_child(toolbar)

        # Lifecycle hooks for auto-refresh timer
        self.connect("map", self._on_map)
        self.connect("unmap", self._on_unmap)
        self.connect("closed", self._on_unmap)

    def _set_content(self, text: str) -> None:
        display_text = text if text.strip() else "No execution logs recorded yet."
        if display_text == self._last_content:
            return
        self._last_content = display_text
        self._buffer.set_text(display_text)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        def _scroll() -> bool:
            end_iter = self._buffer.get_end_iter()
            self._text_view.scroll_to_iter(end_iter, 0.0, False, 0.0, 1.0)
            return False

        GLib.idle_add(_scroll)

    def refresh_logs(self) -> None:
        if self._fetch_logs_fn:
            lines = self._fetch_logs_fn(self._prefix_id, self._max_lines)
            self._set_content("\n".join(lines))

    def _copy_to_clipboard(self) -> None:
        start_iter = self._buffer.get_start_iter()
        end_iter = self._buffer.get_end_iter()
        text = self._buffer.get_text(start_iter, end_iter, False)
        display = Gdk.Display.get_default()
        if display:
            clipboard = display.get_clipboard()
            clipboard.set(text)

    def _confirm_clear_logs(self) -> None:
        dlg = Adw.AlertDialog.new(
            f"Clear logs for '{self._prefix_id}'?",
            "This will delete all past execution and event logs for this prefix.",
        )
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("clear", "Clear Logs")
        dlg.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)

        def _on_resp(_d: Adw.AlertDialog, resp: str) -> None:
            if resp == "clear" and self._clear_logs_fn:
                self._clear_logs_fn(self._prefix_id)
                self.refresh_logs()

        dlg.connect("response", _on_resp)
        dlg.present(self)

    def _on_map(self, *_args: object) -> None:
        if self._fetch_logs_fn and self._timeout_id is None:
            self._timeout_id = GLib.timeout_add_seconds(2, self._on_poll_timer)

    def _on_unmap(self, *_args: object) -> None:
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

    def _on_poll_timer(self) -> bool:
        self.refresh_logs()
        return True
