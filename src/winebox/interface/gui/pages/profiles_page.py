"""Security Profiles management page with custom profile creation, deletion, and permission toggles."""

from typing import Dict, Tuple
from gi.repository import Adw, Gtk
from winebox.domain.models import SecurityProfile

PERMISSION_FIELDS: Tuple[Tuple[str, str], ...] = (
    ("display", "Display Server (X11/Wayland)"),
    ("audio", "Audio Output (PulseAudio/PipeWire)"),
    ("network", "Network / Internet Access"),
    ("gpu", "3D GPU Acceleration (/dev/dri)"),
    ("gamepad", "Gamepad / Controller (/dev/input)"),
    ("hidraw", "Raw HID Devices (/dev/hidraw*)"),
    ("mic", "Microphone Audio Input"),
)


class ProfilesPage(Gtk.Box):
    """Displays built-in and custom security profiles with live hardware permission switches."""

    def __init__(self, window: Adw.ApplicationWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._window = window
        self.set_margin_top(16)
        self.set_margin_bottom(16)
        self.set_margin_start(16)
        self.set_margin_end(16)

        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        spacer = Gtk.Box(hexpand=True)
        top_bar.append(spacer)
        new_btn = Gtk.Button(label="+ New Profile")
        new_btn.add_css_class("suggested-action")
        new_btn.connect("clicked", self._on_new_profile)
        top_bar.append(new_btn)
        self.append(top_bar)

        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self._container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        scrolled.set_child(self._container)
        self.append(scrolled)

    def refresh(self) -> None:
        while child := self._container.get_first_child():
            self._container.remove(child)

        profiles = self._window.services.profile_svc.list_profiles()
        for prof in profiles:
            group = Adw.PreferencesGroup(
                title=f"{prof.name} ({prof.id})",
                description=prof.description,
            )
            if not prof.is_builtin:
                del_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
                del_btn.add_css_class("flat")
                del_btn.set_tooltip_text("Delete custom profile")
                del_btn.connect("clicked", lambda _b, p=prof: self._confirm_delete(p))
                group.set_header_suffix(del_btn)

            for field, label in PERMISSION_FIELDS:
                sw = Adw.SwitchRow(title=label)
                sw.set_active(bool(getattr(prof, field)))
                sw.connect("notify::active", self._on_toggle, prof, field)
                group.add(sw)
            self._container.append(group)

    def _on_toggle(self, sw: Adw.SwitchRow, _pspec: object, prof: SecurityProfile, field: str) -> None:
        try:
            self._window.services.profile_svc.update_profile(prof.id, **{field: sw.get_active()})
            self._window.show_toast(f"Updated '{prof.id}' ({field}={sw.get_active()})")
        except Exception as e:
            self._window.show_toast(f"Update failed: {e}")

    def _confirm_delete(self, prof: SecurityProfile) -> None:
        dlg = Adw.AlertDialog.new(
            f"Delete profile '{prof.id}'?",
            "Deletion fails if any prefix or application currently uses this profile.",
        )
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("delete", "Delete")
        dlg.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.connect("response", lambda _d, resp: self._do_delete(prof.id) if resp == "delete" else None)
        dlg.present(self._window)

    def _do_delete(self, profile_id: str) -> None:
        try:
            self._window.services.profile_svc.delete_profile(profile_id)
            self._window.show_toast(f"Deleted profile '{profile_id}'")
            self.refresh()
        except Exception as e:
            self._window.show_toast(f"Delete failed: {e}")

    def _on_new_profile(self, *_args: object) -> None:
        dlg = Adw.Dialog(title="New Security Profile", content_width=480, content_height=560)
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda *_: dlg.close())
        header.pack_start(cancel_btn)

        create_btn = Gtk.Button(label="Create")
        create_btn.add_css_class("suggested-action")
        header.pack_end(create_btn)
        toolbar.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        info_group = Adw.PreferencesGroup(title="Profile Info")
        id_row = Adw.EntryRow(title="Profile ID (e.g. racing-sim)")
        name_row = Adw.EntryRow(title="Display Name")
        desc_row = Adw.EntryRow(title="Description")
        info_group.add(id_row)
        info_group.add(name_row)
        info_group.add(desc_row)
        box.append(info_group)

        perm_group = Adw.PreferencesGroup(title="Permissions")
        switches: Dict[str, Adw.SwitchRow] = {}
        for field, label in PERMISSION_FIELDS:
            sw = Adw.SwitchRow(title=label)
            sw.set_active(field in ("display", "audio"))
            perm_group.add(sw)
            switches[field] = sw
        box.append(perm_group)

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_child(box)
        toolbar.set_content(scrolled)
        dlg.set_child(toolbar)

        def _submit(*_a: object) -> None:
            pid = id_row.get_text().strip()
            pname = name_row.get_text().strip() or pid.title()
            pdesc = desc_row.get_text().strip() or "Custom user profile"
            if not pid:
                return
            try:
                self._window.services.profile_svc.create_profile(
                    profile_id=pid,
                    name=pname,
                    description=pdesc,
                    **{k: s.get_active() for k, s in switches.items()},
                )
                dlg.close()
                self._window.show_toast(f"Created profile '{pid}'")
                self.refresh()
            except Exception as e:
                self._window.show_toast(f"Create failed: {e}")

        create_btn.connect("clicked", _submit)
        dlg.present(self._window)
