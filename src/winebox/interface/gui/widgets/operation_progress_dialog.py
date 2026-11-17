"""Modal progress dialog for long-running operations with manual completion dismissal (ADR-020)."""

import threading
from typing import Any, Callable, List, Optional
from gi.repository import Adw, GLib, Gtk


class OperationProgressDialog(Adw.Dialog):
    """Displays an active spinner, operation status, optional live logs, and requires manual close."""

    def __init__(
        self,
        title: str,
        task_fn: Callable[[], Any],
        parent_window: Adw.ApplicationWindow,
        status_text: str = "Please wait, operation is in progress...",
        prefix_id: Optional[str] = None,
        log_fetch_fn: Optional[Callable[[str, int], List[str]]] = None,
        on_success: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        super().__init__(title=title, content_width=520, content_height=380)
        self._task_fn = task_fn
        self._parent = parent_window
        self._prefix_id = prefix_id
        self._log_fetch_fn = log_fetch_fn
        self._on_success = on_success
        self._on_error = on_error

        self._task_result: Any = None
        self._task_error: Optional[Exception] = None
        self._is_completed = False
        self._log_timer_id: Optional[int] = None

        toolbar = Adw.ToolbarView()
        self._header = Adw.HeaderBar(show_start_title_buttons=False, show_end_title_buttons=False)
        toolbar.add_top_bar(self._header)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        main_box.set_margin_top(24)
        main_box.set_margin_bottom(24)
        main_box.set_margin_start(24)
        main_box.set_margin_end(24)
        main_box.set_valign(Gtk.Align.CENTER)

        # Status icon / Spinner
        self._icon_stack = Gtk.Stack()
        self._icon_stack.set_halign(Gtk.Align.CENTER)

        self._spinner = Gtk.Spinner()
        self._spinner.set_size_request(48, 48)
        self._spinner.start()
        self._icon_stack.add_named(self._spinner, "spinner")

        self._success_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        self._success_icon.set_pixel_size(48)
        self._success_icon.add_css_class("success")
        self._icon_stack.add_named(self._success_icon, "success")

        self._error_icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic")
        self._error_icon.set_pixel_size(48)
        self._error_icon.add_css_class("error")
        self._icon_stack.add_named(self._error_icon, "error")

        self._icon_stack.set_visible_child_name("spinner")
        main_box.append(self._icon_stack)

        # Title and status description
        self._title_label = Gtk.Label(label=title)
        self._title_label.add_css_class("title-2")
        main_box.append(self._title_label)

        self._status_label = Gtk.Label(label=status_text)
        self._status_label.set_wrap(True)
        self._status_label.set_justify(Gtk.Justification.CENTER)
        self._status_label.add_css_class("body")
        main_box.append(self._status_label)

        # Embedded live log expander
        self._expander = Gtk.Expander(label="Details & Logs")
        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scrolled.set_min_content_height(120)
        self._log_view = Gtk.TextView(editable=False, monospace=True)
        self._log_view.set_top_margin(8)
        self._log_view.set_bottom_margin(8)
        self._log_view.set_left_margin(8)
        self._log_view.set_right_margin(8)
        scrolled.set_child(self._log_view)
        self._expander.set_child(scrolled)
        main_box.append(self._expander)

        # Close button (disabled while running)
        self._close_btn = Gtk.Button(label="Close")
        self._close_btn.set_halign(Gtk.Align.CENTER)
        self._close_btn.set_sensitive(False)
        self._close_btn.connect("clicked", self._on_close_clicked)
        main_box.append(self._close_btn)

        toolbar.set_content(main_box)
        self.set_child(toolbar)

        # Connect map/unmap hooks
        self.connect("map", self._on_map)
        self.connect("unmap", self._on_unmap)

    def _on_map(self, *_args: object) -> None:
        if not self._is_completed:
            # Start background thread
            thread = threading.Thread(target=self._run_task_thread, daemon=True)
            thread.start()

            # Start periodic log check if enabled
            if self._prefix_id and self._log_fetch_fn and self._log_timer_id is None:
                self._log_timer_id = GLib.timeout_add_seconds(1, self._poll_logs)

    def _on_unmap(self, *_args: object) -> None:
        if self._log_timer_id is not None:
            GLib.source_remove(self._log_timer_id)
            self._log_timer_id = None

    def _poll_logs(self) -> bool:
        if self._prefix_id and self._log_fetch_fn:
            lines = self._log_fetch_fn(self._prefix_id, 30)
            if lines:
                buf = self._log_view.get_buffer()
                buf.set_text("\n".join(lines))
        return not self._is_completed

    def _run_task_thread(self) -> None:
        try:
            result = self._task_fn()
            GLib.idle_add(self._handle_task_success, result)
        except Exception as exc:
            GLib.idle_add(self._handle_task_error, exc)

    def _handle_task_success(self, result: Any) -> bool:
        self._is_completed = True
        self._task_result = result
        self._spinner.stop()
        self._icon_stack.set_visible_child_name("success")
        self._title_label.set_text("Completed Successfully")
        msg = f"Task completed." if result is None else str(result)
        self._status_label.set_text(msg)
        self._close_btn.set_sensitive(True)
        self._close_btn.add_css_class("suggested-action")
        self._poll_logs()
        return False

    def _handle_task_error(self, exc: Exception) -> bool:
        self._is_completed = True
        self._task_error = exc
        self._spinner.stop()
        self._icon_stack.set_visible_child_name("error")
        self._title_label.set_text("Operation Failed")
        self._status_label.set_text(str(exc))
        self._expander.set_expanded(True)
        self._close_btn.set_sensitive(True)
        self._poll_logs()
        return False

    def _on_close_clicked(self, *_args: object) -> None:
        self.close()
        if self._task_error is not None:
            if self._on_error:
                self._on_error(self._task_error)
        else:
            if self._on_success:
                self._on_success(self._task_result)
