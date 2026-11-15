"""Log viewer dialog for Wine prefix execution logs."""

from typing import List
from gi.repository import Adw, Gtk


class LogViewerDialog(Adw.Dialog):
    """Displays recent execution log lines for a prefix."""

    def __init__(self, prefix_id: str, lines: List[str]) -> None:
        super().__init__(title=f"Logs: {prefix_id}", content_width=760, content_height=480)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())

        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        text_view = Gtk.TextView(editable=False, monospace=True)
        text_view.set_top_margin(10)
        text_view.set_bottom_margin(10)
        text_view.set_left_margin(12)
        text_view.set_right_margin(12)
        content = "\n".join(lines) if lines else "No execution logs recorded yet."
        text_view.get_buffer().set_text(content)

        scrolled.set_child(text_view)
        toolbar.set_content(scrolled)
        self.set_child(toolbar)
