"""Import portable applications and external Wine prefixes CLI commands."""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from winebox.application.import_service import ImportService
from winebox.common.exceptions import WineboxError

import_app = typer.Typer(help="Import portable applications and external prefixes.")
console = Console()


@import_app.command("app")
def import_portable_app(
    source_dir: Path = typer.Argument(..., help="Path to source portable app folder"),
    prefix_id: str = typer.Option(..., "--prefix", "-p", help="Target Prefix ID"),
    app_id: str = typer.Option(..., "--id", "-i", help="Application ID"),
    name: str = typer.Option(..., "--name", "-n", help="Application display name"),
    exe: str = typer.Option(..., "--exe", "-e", help="Relative executable name inside folder"),
    profile_id: str = typer.Option("permissive", "--profile", help="Security profile ID"),
) -> None:
    """Import a portable Windows application folder into a Wine prefix."""
    svc = ImportService()
    with console.status(f"[bold green]Importing portable app '{name}'..."):
        try:
            app_obj = svc.import_portable_app(
                source_dir=source_dir,
                prefix_id=prefix_id,
                app_id=app_id,
                name=name,
                exe_rel_path=exe,
                profile_id=profile_id,
            )
            console.print(
                f"[bold green]✓[/bold green] Portable app '[bold cyan]{app_obj.name}[/bold cyan]' imported and registered."
            )
        except WineboxError as e:
            console.print(f"[bold red]Import Error:[/bold red] {e}")
            raise typer.Exit(code=1)


@import_app.command("prefix")
def import_prefix(
    source_dir: Path = typer.Argument(..., help="Path to external Wine prefix folder"),
    prefix_id: str = typer.Option(..., "--id", "-i", help="Prefix ID in WineBox"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Prefix display name"),
) -> None:
    """Import an external Wine prefix into WineBox (clones, sanitizes, and audits)."""
    svc = ImportService()
    with console.status(f"[bold green]Importing external prefix '{prefix_id}'..."):
        try:
            p = svc.import_prefix(source_dir=source_dir, prefix_id=prefix_id, name=name)
            console.print(
                f"[bold green]✓[/bold green] External prefix '[bold cyan]{p.id}[/bold cyan]' imported and sanitized."
            )
        except WineboxError as e:
            console.print(f"[bold red]Import Error:[/bold red] {e}")
            raise typer.Exit(code=1)
