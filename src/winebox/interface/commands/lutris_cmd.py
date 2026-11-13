"""Lutris GUI integration CLI commands (ADR-022)."""

from typing import Optional
import typer
from rich.console import Console
from winebox.application.app_service import AppService
from winebox.application.lutris_service import LutrisService
from winebox.common.exceptions import WineboxError
from winebox.interface.tui import tui_select

lutris_app = typer.Typer(help="Export and integrate WineBox apps with Lutris GUI (ADR-022).")
console = Console()


@lutris_app.command("add")
def lutris_add(
    app_id: Optional[str] = typer.Argument(None, help="Application ID to export to Lutris (interactive if omitted)"),
    launch: bool = typer.Option(True, "--launch/--no-launch", help="Launch 'lutris --install' automatically"),
) -> None:
    """Generate an official Lutris installer YAML for a WineBox app and open Lutris to install it."""
    app_svc = AppService()
    apps = app_svc.list_apps()
    if not apps:
        console.print(
            "[yellow]Belum ada aplikasi yang terdaftar di WineBox. Jalankan 'winebox add' terlebih dahulu.[/yellow]"
        )
        raise typer.Exit(code=1)

    target_app_id = app_id
    if not target_app_id:
        options = [(a.id, f"{a.name} ({a.id}) [Prefix: {a.prefix_id}, Profile: {a.profile_id}]") for a in apps]
        target_app_id = tui_select("Pilih Game / Aplikasi untuk Ditambahkan ke Lutris", options, default_index=0)

    lutris_svc = LutrisService()
    try:
        yaml_path = lutris_svc.export_app_to_lutris(target_app_id, launch_lutris=launch)
        console.print(f"[bold green]✓[/bold green] File installer Lutris dibuat: [cyan]{yaml_path}[/cyan]")
        if launch:
            console.print(
                "[bold green]✓[/bold green] Jendela instalasi Lutris telah dipanggil! "
                "Klik [bold cyan]Install[/bold cyan] di Lutris untuk menyimpan ke Library."
            )
        else:
            console.print(f'Jalankan manual dengan: [bold yellow]lutris --install "{yaml_path}"[/bold yellow]')
    except WineboxError as e:
        console.print(f"[bold red]Lutris Error:[/bold red] {e}")
        raise typer.Exit(code=1)
