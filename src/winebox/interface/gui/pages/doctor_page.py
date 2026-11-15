"""System Doctor diagnostics page."""

from gi.repository import Adw, Gtk
from winebox.common.doctor import SystemDoctor


class DoctorPage(Gtk.Box):
    """Displays host readiness checks (bwrap, userns, wine, display, audio, GPU)."""

    def __init__(self, window: Adw.ApplicationWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._window = window
        self.set_margin_top(16)
        self.set_margin_bottom(16)
        self.set_margin_start(16)
        self.set_margin_end(16)

        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self._list_box = Gtk.ListBox()
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.set_child(self._list_box)
        self.append(scrolled)

    def refresh(self) -> None:
        while child := self._list_box.get_first_child():
            self._list_box.remove(child)

        results = SystemDoctor().run_all()
        for res in results:
            subtitle = res.details if res.passed else f"{res.details} — Fix: {res.remediation}"
            row = Adw.ActionRow(title=res.name, subtitle=subtitle)
            icon_name = "emblem-ok-symbolic" if res.passed else "dialog-error-symbolic"
            img = Gtk.Image.new_from_icon_name(icon_name)
            row.add_prefix(img)
            status = Gtk.Label(label="PASS" if res.passed else "FAIL")
            status.add_css_class("success" if res.passed else "error")
            row.add_suffix(status)
            self._list_box.append(row)
