"""Security Profiles management page with interactive permission toggles."""

from gi.repository import Adw, Gtk
from winebox.domain.models import SecurityProfile


class ProfilesPage(Gtk.Box):
    """Displays built-in and custom security profiles with live hardware permission switches."""

    def __init__(self, window: Adw.ApplicationWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._window = window
        self.set_margin_top(16)
        self.set_margin_bottom(16)
        self.set_margin_start(16)
        self.set_margin_end(16)

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
            for field, label in (
                ("display", "Display Server (X11/Wayland)"),
                ("audio", "Audio (PulseAudio/PipeWire)"),
                ("network", "Network / Internet Access"),
                ("gpu", "3D GPU Acceleration (/dev/dri)"),
                ("gamepad", "Gamepad / Controller (/dev/input)"),
            ):
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
