"""CLI commands for managing application master groups."""

from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from winebox.application.group_service import GroupService
from winebox.common.exceptions import WineboxError

group_app = typer.Typer(help="Manage application master groups for library organization.")
console = Console()


@group_app.command("list")
def group_list() -> None:
    """List all application master groups."""
    svc = GroupService()
    groups = svc.list_groups()
    if not groups:
        console.print("[dim]No application groups defined yet. Use 'winebox group create <name>' to create one.[/dim]")
        return

    table = Table(title="Application Groups")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Icon", style="yellow")
    table.add_column("Created At", style="dim")

    for g in groups:
        table.add_row(g.id, g.name, g.icon or "-", g.created_at.strftime("%Y-%m-%d %H:%M"))
    console.print(table)


@group_app.command("create")
def group_create(
    name: str = typer.Argument(..., help="Display name for the group"),
    group_id: Optional[str] = typer.Option(None, "--id", help="Optional custom identifier (defaults to slug)"),
    icon: Optional[str] = typer.Option("", "--icon", help="Optional icon name or path"),
) -> None:
    """Create a new application group."""
    svc = GroupService()
    try:
        grp = svc.create_group(name=name, group_id=group_id, icon=icon or "")
        console.print(f"[bold green]✓[/bold green] Created group '[bold]{grp.name}[/bold]' (id: [cyan]{grp.id}[/cyan])")
    except WineboxError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@group_app.command("rename")
def group_rename(
    group_id: str = typer.Argument(..., help="Group identifier to rename"),
    new_name: str = typer.Argument(..., help="New display name"),
) -> None:
    """Rename an application group."""
    svc = GroupService()
    try:
        grp = svc.rename_group(group_id, new_name)
        console.print(f"[bold green]✓[/bold green] Renamed group to '[bold]{grp.name}[/bold]'")
    except WineboxError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@group_app.command("delete")
def group_delete(
    group_id: str = typer.Argument(..., help="Group identifier to delete"),
) -> None:
    """Delete an application group (unlinks applications without deleting them)."""
    svc = GroupService()
    try:
        svc.delete_group(group_id)
        console.print(f"[bold green]✓[/bold green] Deleted group '[cyan]{group_id}[/cyan]'")
    except WineboxError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
