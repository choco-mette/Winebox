"""GTK4 + Libadwaita GUI Launcher package (ADR-028)."""

from winebox.common.exceptions import WineboxError


def launch_gui() -> int:
    """Lazily loads PyGObject GTK4/Libadwaita and starts the WineBox GUI application."""
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
    except (ImportError, ValueError) as e:
        raise WineboxError(
            "GTK4 / Libadwaita (PyGObject) is not available in this Python environment. "
            "Install 'python3-gi', 'gir1.2-gtk-4.0', and 'gir1.2-adw-1' (or enable system-site-packages in .venv)."
        ) from e

    from winebox.interface.gui.app import WineboxGuiApp

    app = WineboxGuiApp()
    return app.run(None)
