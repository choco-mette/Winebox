"""Windows application management and execution CLI commands."""

from typing import List, Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from winebox.application.app_service import AppService
from winebox.application.desktop_service import DesktopService
from winebox.application.execution_service import ExecutionService
from winebox.common.exceptions import WineboxError

app_app = typer.Typer(help="Manage and execute registered Windows applications.")
console = Console()


@app_app.command("list")
def app_list() -> None:
    """List all registered Windows applications."""
    svc = AppService()
    apps = svc.list_apps()

    if not apps:
        console.print(
            "[dim]No applications registered. Add one with 'winebox add' or register manually.[/dim]"
        )
        return

    table = Table(title="Registered Applications")
    table.add_column("ID", style="bold cyan")
    table.add_column("Name")
    table.add_column("Prefix", style="magenta")
    table.add_column("Profile", style="blue")
    table.add_column("Executable Path")
    table.add_column("Last Run", style="dim")
    table.add_column("Status", style="green")

    for a in apps:
        last_run_str = "-"
        if a.last_run_at:
            code_color = "green" if a.last_exit_code == 0 else "red"
            last_run_str = f"[{code_color}]Exit {a.last_exit_code}[/{code_color}] ({a.last_run_at.strftime('%m-%d %H:%M')})"

        table.add_row(
            a.id,
            a.name,
            a.prefix_id,
            a.profile_id,
            a.exe_path,
            last_run_str,
            a.status.value,
        )
    console.print(table)


@app_app.command("run")
def app_run(
    app_id: str = typer.Argument(..., help="Application ID to run"),
    extra_args: List[str] = typer.Argument(None, help="Additional arguments passed to executable"),
) -> None:
    """Launch a Windows application inside Bubblewrap sandbox."""
    svc = ExecutionService()
    try:
        res = svc.run_app(app_id, extra_args=extra_args or [], inherit_stdio=True)
        if res.returncode != 0:
            raise typer.Exit(code=res.returncode)
    except WineboxError as e:
        console.print(f"[bold red]Execution Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app_app.command("info")
def app_info(
    app_id: str = typer.Argument(..., help="Application ID to inspect"),
) -> None:
    """Display configuration and security policy details of an application."""
    svc = AppService()
    try:
        app_obj = svc.get_app(app_id)
        panel = Panel(
            f"[bold]ID:[/bold] {app_obj.id}\n"
            f"[bold]Name:[/bold] {app_obj.name}\n"
            f"[bold]Prefix:[/bold] {app_obj.prefix_id}\n"
            f"[bold]Runner:[/bold] {app_obj.runner_id}\n"
            f"[bold]Executable:[/bold] {app_obj.exe_path}\n"
            f"[bold]Default Args:[/bold] {app_obj.arguments}\n\n"
            f"[bold cyan]Security Policy:[/bold cyan]\n"
            f"  Display: {app_obj.policy.display}\n"
            f"  Audio: {app_obj.policy.audio}\n"
            f"  Network: {app_obj.policy.network}\n"
            f"  GPU: {app_obj.policy.gpu}\n"
            f"  Gamepad: {app_obj.policy.gamepad}\n"
            f"  HIDRaw: {app_obj.policy.hidraw}\n"
            f"  Mic: {app_obj.policy.mic}\n"
            f"  Host Mounts: {len(app_obj.policy.host_mounts)}",
            title=f"Application: {app_obj.name}",
        )
        console.print(panel)
    except WineboxError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app_app.command("register")
def app_register(
    app_id: str = typer.Option(..., "--id", "-i", help="Unique ID for the application"),
    name: str = typer.Option(..., "--name", "-n", help="Display name"),
    prefix_id: str = typer.Option(..., "--prefix", "-p", help="Target Prefix ID"),
    exe_path: str = typer.Option(..., "--exe", "-e", help="Relative path to .exe in prefix (e.g. drive_c/...)"),
    profile_id: str = typer.Option("permissive", "--profile", help="Security profile ID (ADR-020)"),
) -> None:
    """Register an existing executable inside a prefix as an application."""
    svc = AppService()
    try:
        app_obj = svc.register_app(
            app_id=app_id,
            name=name,
            prefix_id=prefix_id,
            exe_path=exe_path,
            profile_id=profile_id,
        )
        console.print(f"[bold green]✓[/bold green] Application '{app_obj.name}' registered.")
    except WineboxError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app_app.command("remove")
def app_remove(
    app_id: str = typer.Argument(..., help="Application ID to unregister"),
) -> None:
    """Unregister an application (does not delete prefix data)."""
    svc = AppService()
    try:
        svc.remove_app(app_id)
        console.print(f"[bold green]✓[/bold green] Application '{app_id}' unregistered.")
    except WineboxError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app_app.command("desktop")
def app_desktop(
    app_id: str = typer.Argument(..., help="Application ID to create/remove desktop shortcut for"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Rename application and shortcut display name"),
    icon: Optional[str] = typer.Option(None, "--icon", help="Path to icon file (.png/.svg/.ico) or icon name"),
    categories: Optional[str] = typer.Option("Game;Utility;", "--categories", help="XDG Categories separated by semicolons"),
    remove: bool = typer.Option(False, "--remove", "-r", help="Remove the desktop shortcut"),
) -> None:
    """Create or remove a Freedesktop .desktop shortcut for an application (ADR-024)."""
    svc = DesktopService()
    try:
        if remove:
            removed = svc.remove_desktop_entry(app_id)
            if removed:
                console.print(f"[bold green]✓[/bold green] Desktop shortcut for '{app_id}' removed.")
            else:
                console.print(f"[yellow]No desktop shortcut found for '{app_id}'.[/yellow]")
        else:
            path = svc.create_desktop_entry(app_id, name=name, icon=icon, categories=categories)
            console.print(f"[bold green]✓[/bold green] Desktop shortcut created: [cyan]{path}[/cyan]")
    except WineboxError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app_app.command("kill")
def app_kill(
    app_id: str = typer.Argument(..., help="Application ID to terminate"),
    force: bool = typer.Option(False, "--force", "-f", help="Force immediate SIGKILL without SIGTERM grace period"),
) -> None:
    """Terminate all running processes in the application's prefix (ADR-025)."""
    svc = AppService()
    try:
        res = svc.kill_app(app_id, force=force)
        if not res["running"]:
            console.print(f"[yellow]Application '{app_id}' is not running. Prefix is idle.[/yellow]")
        else:
            pids_str = ", ".join(str(p) for p in res["killed_pids"]) or "none"
            console.print(
                f"[bold green]✓[/bold green] Terminated processes for application '[bold cyan]{app_id}[/bold cyan]' "
                f"([dim]PIDs: {pids_str}[/dim])."
            )
    except WineboxError as e:
        console.print(f"[bold red]Kill Error:[/bold red] {e}")
        raise typer.Exit(code=1)

