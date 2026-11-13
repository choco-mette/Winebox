"""Wine runner management CLI commands."""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from winebox.application.runner_service import RunnerService
from winebox.common.exceptions import WineboxError

runner_app = typer.Typer(help="Manage system and custom Wine runners.")
console = Console()


@runner_app.command("list")
def runner_list() -> None:
    """List available Wine runners."""
    svc = RunnerService()
    runners = svc.list_runners()

    table = Table(title="Wine Runners")
    table.add_column("ID", style="bold cyan")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Wine Binary")

    for r in runners:
        r_type = "[green]System[/green]" if r.is_system else "[yellow]Custom[/yellow]"
        table.add_row(r.id, r.name, r_type, str(r.wine_bin))
    console.print(table)


@runner_app.command("register")
def runner_register(
    runner_id: str = typer.Argument(..., help="Unique ID for custom runner"),
    name: str = typer.Option(..., "--name", "-n", help="Display name"),
    wine_bin: Path = typer.Option(..., "--wine", "-w", help="Path to wine binary"),
    wineserver_bin: Optional[Path] = typer.Option(None, "--wineserver", "-s", help="Path to wineserver binary"),
) -> None:
    """Register a custom Wine runner directory."""
    svc = RunnerService()
    try:
        runner = svc.register_custom_runner(
            runner_id=runner_id,
            name=name,
            wine_bin=wine_bin,
            wineserver_bin=wineserver_bin,
        )
        console.print(f"[bold green]✓[/bold green] Custom runner '{runner.name}' registered.")
    except WineboxError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)

