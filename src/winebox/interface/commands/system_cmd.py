"""System diagnostic and version CLI commands."""

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from winebox import __version__
from winebox.common.doctor import SystemDoctor

system_app = typer.Typer(help="Host system diagnostics and version info.")
console = Console()


@system_app.command("doctor")
def system_doctor() -> None:
    """Run comprehensive host environment diagnostics (bwrap, wine, userns, hardware)."""
    doctor = SystemDoctor()
    results = doctor.run_all()

    table = Table(title="WineBox System Doctor Diagnostics", show_lines=True)
    table.add_column("Check", style="bold cyan")
    table.add_column("Status", justify="center")
    table.add_column("Details")
    table.add_column("Remediation", style="yellow")

    all_passed = True
    for res in results:
        status_text = "[bold green]PASS[/bold green]" if res.passed else "[bold red]FAIL[/bold red]"
        if not res.passed:
            all_passed = False
        table.add_row(res.name, status_text, res.details, res.remediation)

    console.print(table)
    if all_passed:
        console.print("\n[bold green]✓ System is 100% ready for WineBox![/bold green]\n")
    else:
        console.print(
            "\n[bold red]✗ Some checks failed. Resolve the remediations above before running applications.[/bold red]\n"
        )
        raise typer.Exit(code=1)


@system_app.command("version")
def system_version() -> None:
    """Show WineBox version."""
    rprint(f"[bold cyan]WineBox[/bold cyan] version [bold green]{__version__}[/bold green]")

