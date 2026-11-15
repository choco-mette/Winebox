"""CLI entrypoint to launch the GTK4 + Libadwaita GUI Launcher."""

import typer
from rich.console import Console
from winebox.common.exceptions import WineboxError

console = Console()


def launch_gui_command() -> None:
    """Launch the WineBox GTK4 + Libadwaita desktop GUI."""
    from winebox.interface.gui import launch_gui

    try:
        code = launch_gui()
    except WineboxError as e:
        console.print(f"[bold red]GUI Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    if code != 0:
        raise typer.Exit(code=code)
