"""Main Libadwaita window with NavigationSplitView and ToastOverlay (ADR-028)."""

from typing import Dict, Tuple
from gi.repository import Adw, Gtk
from winebox.interface.gui.pages.doctor_page import DoctorPage
from winebox.interface.gui.pages.library_page import LibraryPage
from winebox.interface.gui.pages.prefixes_page import PrefixesPage
from winebox.interface.gui.pages.profiles_page import ProfilesPage
from winebox.interface.gui.pages.runners_page import RunnersPage
from winebox.interface.gui.state import ServiceContainer


class WineboxMainWindow(Adw.ApplicationWindow):
    """Main WineBox desktop window hosting the 5 primary management views."""

    def __init__(self, application: Adw.Application, services: ServiceContainer) -> None:
        super().__init__(application=application, title="WineBox", default_width=1120, default_height=740)
        self.services = services

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        self.split_view = Adw.NavigationSplitView()
        self.split_view.set_sidebar_width_unit(Adw.LengthUnit.PX)
        self.split_view.set_min_sidebar_width(220)
        self.split_view.set_max_sidebar_width(220)
        self.toast_overlay.set_child(self.split_view)

        # Sidebar
        sidebar_toolbar = Adw.ToolbarView()
        sidebar_header = Adw.HeaderBar()
        sidebar_toolbar.add_top_bar(sidebar_header)

        self.nav_list = Gtk.ListBox()
        self.nav_list.add_css_class("navigation-sidebar")
        self.nav_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        sidebar_toolbar.set_content(self.nav_list)

        sidebar_page = Adw.NavigationPage.new(sidebar_toolbar, "WineBox")
        self.split_view.set_sidebar(sidebar_page)

        # Content stack
        content_toolbar = Adw.ToolbarView()
        self.content_header = Adw.HeaderBar()
        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Refresh (F5)")
        refresh_btn.connect("clicked", lambda *_: self.refresh_all())
        self.content_header.pack_end(refresh_btn)
        content_toolbar.add_top_bar(self.content_header)

        self.view_stack = Adw.ViewStack()
        content_toolbar.set_content(self.view_stack)
        self.content_page = Adw.NavigationPage.new(content_toolbar, "Library")
        self.split_view.set_content(self.content_page)

        self.pages: Dict[str, Gtk.Widget] = {
            "library": LibraryPage(self),
            "prefixes": PrefixesPage(self),
            "runners": RunnersPage(self),
            "profiles": ProfilesPage(self),
            "doctor": DoctorPage(self),
        }
        nav_items: Tuple[Tuple[str, str, str], ...] = (
            ("library", "Library", "applications-games-symbolic"),
            ("prefixes", "Prefixes", "folder-symbolic"),
            ("runners", "Runners", "system-run-symbolic"),
            ("profiles", "Security Profiles", "security-high-symbolic"),
            ("doctor", "System Doctor", "dialog-information-symbolic"),
        )

        self._row_to_key: Dict[Gtk.ListBoxRow, Tuple[str, str]] = {}
        for key, title, icon_name in nav_items:
            self.view_stack.add_named(self.pages[key], key)
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            box.set_margin_top(8)
            box.set_margin_bottom(8)
            box.set_margin_start(8)
            box.set_margin_end(8)
            box.append(Gtk.Image.new_from_icon_name(icon_name))
            box.append(Gtk.Label(label=title, xalign=0.0))
            row.set_child(box)
            self.nav_list.append(row)
            self._row_to_key[row] = (key, title)

        self.nav_list.connect("row-selected", self._on_nav_selected)
        first_row = self.nav_list.get_row_at_index(0)
        if first_row:
            self.nav_list.select_row(first_row)

    def _on_nav_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        if row is None or row not in self._row_to_key:
            return
        key, title = self._row_to_key[row]
        self.view_stack.set_visible_child_name(key)
        self.content_page.set_title(title)
        page = self.pages[key]
        if hasattr(page, "refresh"):
            page.refresh()

    def open_prefix_files(self, prefix_id: str) -> None:
        """Navigate to the Prefixes page and focus the requested prefix in the File Manager."""
        for row, (key, _title) in self._row_to_key.items():
            if key == "prefixes":
                self.nav_list.select_row(row)
                break
        prefixes_page = self.pages.get("prefixes")
        if hasattr(prefixes_page, "select_prefix"):
            prefixes_page.select_prefix(prefix_id)

    def show_toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast.new(message))

    def refresh_all(self) -> None:
        for page in self.pages.values():
            if hasattr(page, "refresh"):
                page.refresh()
