"""Dialog for assigning an application to one or more master groups (ADR-020)."""

from typing import Callable, Dict, List, Optional
from gi.repository import Adw, Gtk

from winebox.domain.models import Application
from winebox.interface.gui.state import ServiceContainer


class GroupAssignmentDialog(Adw.Dialog):
    """Allows checking/unchecking groups for an app and adding new master groups on the fly."""

    def __init__(
        self,
        parent_window: Adw.ApplicationWindow,
        services: ServiceContainer,
        app_obj: Application,
        on_saved: Optional[Callable[[List[str]], None]] = None,
    ) -> None:
        super().__init__(title=f"Groups: {app_obj.name}", content_width=440, content_height=460)
        self._parent = parent_window
        self._services = services
        self._app = app_obj
        self._on_saved = on_saved
        self._check_buttons: Dict[str, Gtk.CheckButton] = {}

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar(show_start_title_buttons=False, show_end_title_buttons=False)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda *_: self.close())
        header.pack_start(cancel_btn)

        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save_clicked)
        header.pack_end(save_btn)
        toolbar.add_top_bar(header)

        page = Adw.PreferencesPage()

        # Groups list group
        self._list_group = Adw.PreferencesGroup(
            title="Assigned Groups",
            description="Select all collections and categories this application belongs to.",
        )
        self._empty_label = Gtk.Label(label="No groups created yet. Add one below!")
        self._empty_label.add_css_class("dim-label")
        self._empty_label.set_margin_top(12)
        self._empty_label.set_margin_bottom(12)
        self._list_group.add(self._empty_label)

        # Populate existing groups
        self._reload_groups()
        page.add(self._list_group)

        # Inline new group creation
        create_group_pref = Adw.PreferencesGroup(
            title="Create New Group",
            description="Add a new category collection to your library.",
        )
        add_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._new_group_entry = Gtk.Entry(placeholder_text="Group Name (e.g. RPG, Favorites)", hexpand=True)
        add_btn = Gtk.Button(label="+ Add")
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._on_create_group)
        add_box.append(self._new_group_entry)
        add_box.append(add_btn)
        create_group_pref.add(add_box)
        page.add(create_group_pref)

        toolbar.set_content(page)
        self.set_child(toolbar)

    def _reload_groups(self) -> None:
        all_groups = self._services.group_svc.list_groups()
        current_assigned = set(self._services.repo.get_app_group_ids(self._app.id))

        # Clear existing rows
        for ch in list(self._check_buttons.values()):
            parent_row = ch.get_parent()
            if parent_row:
                self._list_group.remove(parent_row)
        self._check_buttons.clear()

        if not all_groups:
            self._empty_label.set_visible(True)
            return

        self._empty_label.set_visible(False)
        for g in all_groups:
            row = Adw.ActionRow(title=g.name)
            check = Gtk.CheckButton(active=(g.id in current_assigned))
            check.set_valign(Gtk.Align.CENTER)
            row.add_suffix(check)
            row.set_activatable_widget(check)
            self._list_group.add(row)
            self._check_buttons[g.id] = check

    def _on_create_group(self, *_args: object) -> None:
        name = self._new_group_entry.get_text().strip()
        if not name:
            return
        try:
            new_grp = self._services.group_svc.create_group(name=name)
            self._new_group_entry.set_text("")
            self._reload_groups()
            # Automatically check newly created group
            if new_grp.id in self._check_buttons:
                self._check_buttons[new_grp.id].set_active(True)
        except Exception as e:
            toast = Adw.Toast.new(f"Cannot create group: {e}")
            toast.set_timeout(3)
            # Find toast overlay or show via parent
            self._parent.show_toast(f"Group error: {e}")

    def _on_save_clicked(self, *_args: object) -> None:
        selected_ids = [gid for gid, btn in self._check_buttons.items() if btn.get_active()]
        try:
            self._services.group_svc.assign_groups(self._app.id, selected_ids)
            if self._on_saved:
                self._on_saved(selected_ids)
            self.close()
        except Exception as e:
            self._parent.show_toast(f"Failed to update groups: {e}")
