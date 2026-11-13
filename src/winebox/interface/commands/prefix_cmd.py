"""Wine prefix management CLI commands."""

from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from winebox.application.prefix_service import PrefixService
from winebox.common.exceptions import WineboxError
from winebox.infrastructure.log_manager import LogManager
from winebox.infrastructure.sqlite_repository import SqliteRepository

prefix_app = typer.Typer(help="Manage isolated Wine prefixes.")
console = Console()


@prefix_app.command("list")
def prefix_list() -> None:
    """List all registered Wine prefixes."""
    svc = PrefixService()
    prefixes = svc.list_prefixes()

    if not prefixes:
        console.print("[dim]No prefixes found. Create one with 'winebox prefix create <id>'.[/dim]")
        return

    table = Table(title="Wine Prefixes")
    table.add_column("ID", style="bold cyan")
    table.add_column("Name")
    table.add_column("Runner", style="green")
    table.add_column("Origin")
    table.add_column("Status")
    table.add_column("Created At", style="dim")

    for p in prefixes:
        table.add_row(
            p.id,
            p.name,
            p.runner_id,
            p.origin.value,
            f"[green]{p.status.value}[/green]",
            p.created_at.strftime("%Y-%m-%d %H:%M"),
        )
    console.print(table)


@prefix_app.command("create")
def prefix_create(
    prefix_id: str = typer.Argument(..., help="Unique identifier for the prefix"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Display name"),
    runner_id: str = typer.Option("system-wine", "--runner", "-r", help="Runner ID to use"),
    profile_id: str = typer.Option(
        "permissive", "--profile", help="Default security profile (permissive/balanced/zero-trust/paranoid)"
    ),
    init_wine: bool = typer.Option(True, "--wineboot/--no-wineboot", help="Run wineboot inside sandbox"),
    network: bool = typer.Option(
        True, "--network/--no-network", help="Allow network access during wineboot (e.g. for Gecko/Mono)"
    ),
) -> None:
    """Create a new isolated Wine prefix and run initial sandboxed wineboot."""
    svc = PrefixService()
    with console.status(f"[bold green]Initializing isolated prefix '{prefix_id}'..."):
        try:
            prefix = svc.create_prefix(
                prefix_id=prefix_id,
                name=name,
                runner_id=runner_id,
                default_profile_id=profile_id,
                initialize_wineboot=init_wine,
                allow_network=network,
            )
            console.print(f"[bold green]✓[/bold green] Prefix '[bold cyan]{prefix.id}[/bold cyan]' created successfully.")
        except WineboxError as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=1)


@prefix_app.command("audit")
def prefix_audit(
    prefix_id: str = typer.Argument(..., help="Prefix ID to audit"),
) -> None:
    """Audit a Wine prefix for security violations (symlink escapes, drive Z: mapping)."""
    svc = PrefixService()
    try:
        warnings = svc.audit_prefix(prefix_id)
        if warnings:
            for w in warnings:
                console.print(f"[bold yellow]![/bold yellow] {w}")
        console.print(f"[bold green]✓[/bold green] Prefix '{prefix_id}' passed security audit.")
    except WineboxError as e:
        console.print(f"[bold red]Security Audit Failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@prefix_app.command("remove")
def prefix_remove(
    prefix_id: str = typer.Argument(..., help="Prefix ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Bypass confirmation prompt"),
) -> None:
    """Remove a Wine prefix and all its data."""
    if not force:
        confirm = typer.confirm(f"Are you sure you want to permanently delete prefix '{prefix_id}'?")
        if not confirm:
            raise typer.Abort()

    svc = PrefixService()
    try:
        svc.remove_prefix(prefix_id)
        console.print(f"[bold green]✓[/bold green] Prefix '{prefix_id}' removed.")
    except WineboxError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@prefix_app.command("logs")
def prefix_logs(
    prefix_id: str = typer.Argument(..., help="Prefix ID to view logs for"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of trailing log lines to display"),
) -> None:
    """View rotated execution logs for a Wine prefix (ADR-020)."""
    repo = SqliteRepository()
    log_mgr = LogManager(prefixes_dir=repo.prefixes_dir)
    log_lines = log_mgr.read_logs(prefix_id=prefix_id, max_lines=lines)

    if not log_lines:
        console.print(f"[dim]No logs found for prefix '{prefix_id}'.[/dim]")
        return

    console.print(f"[bold cyan]Log output for prefix '{prefix_id}' (last {len(log_lines)} lines):[/bold cyan]\n")
    for line in log_lines:
        if "[STDERR]" in line or "[WARNING]" in line:
            console.print(f"[yellow]{line}[/yellow]")
        elif "Finished with Exit Code 0" in line or "[INFO]" in line:
            console.print(f"[dim]{line}[/dim]")
        else:
            console.print(line)

