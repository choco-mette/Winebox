"""Libadwaita application entrypoint and lifecycle manager (ADR-028)."""

from typing import Optional
from gi.repository import Adw, Gio
from winebox.interface.gui.state import ServiceContainer
from winebox.interface.gui.window import WineboxMainWindow


class WineboxGuiApp(Adw.Application):
    """Single-instance GTK4 + Libadwaita application for WineBox."""

    def __init__(self, services: Optional[ServiceContainer] = None) -> None:
        super().__init__(
            application_id="id.winebox.WineBox",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.services: Optional[ServiceContainer] = services
        self._window: Optional[WineboxMainWindow] = None

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        if self.services is None:
            self.services = ServiceContainer()

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Control>q"])

        refresh_action = Gio.SimpleAction.new("refresh", None)
        refresh_action.connect("activate", self._on_refresh_action)
        self.add_action(refresh_action)
        self.set_accels_for_action("app.refresh", ["F5", "<Control>r"])

    def _on_refresh_action(self, *_args: object) -> None:
        if self._window:
            self._window.refresh_all()

    def do_activate(self) -> None:
        assert self.services is not None
        if self._window is None:
            self._window = WineboxMainWindow(application=self, services=self.services)
        self._window.present()
