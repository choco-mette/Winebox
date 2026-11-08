"""WineBox Command Line Interface built with Typer and Rich."""

import sys
from pathlib import Path
from typing import List, Optional
import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from winebox import __version__
from winebox.application.app_service import AppService
from winebox.application.execution_service import ExecutionService
from winebox.application.import_service import ImportService
from winebox.application.install_service import InstallService
from winebox.application.prefix_service import PrefixService
from winebox.application.runner_service import RunnerService
from winebox.common.doctor import SystemDoctor
from winebox.common.exceptions import WineboxError
from winebox.domain.models import HostMount, MountMode, SecurityPolicy

app = typer.Typer(
    name="winebox",
    help="WineBox: Secure orchestrator for managing Windows applications in Linux via Bubblewrap.",
    no_args_is_help=True,
)

prefix_app = typer.Typer(help="Manage isolated Wine prefixes.")
app_app = typer.Typer(help="Manage and execute registered Windows applications.")
runner_app = typer.Typer(help="Manage system and custom Wine runners.")
system_app = typer.Typer(help="Host system diagnostics and version info.")
import_app = typer.Typer(help="Import portable applications and external prefixes.")

app.add_typer(prefix_app, name="prefix")
app.add_typer(app_app, name="app")
app.add_typer(runner_app, name="runner")
app.add_typer(system_app, name="system")
app.add_typer(import_app, name="import")

console = Console()


# ---------------- System Commands ----------------
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


# ---------------- Prefix Commands ----------------
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
    init_wine: bool = typer.Option(True, "--wineboot/--no-wineboot", help="Run wineboot inside sandbox"),
    network: bool = typer.Option(True, "--network/--no-network", help="Allow network access during wineboot (e.g. for Gecko/Mono)"),
) -> None:
    """Create a new isolated Wine prefix and run initial sandboxed wineboot."""
    svc = PrefixService()
    with console.status(f"[bold green]Initializing isolated prefix '{prefix_id}'..."):
        try:
            prefix = svc.create_prefix(
                prefix_id=prefix_id,
                name=name,
                runner_id=runner_id,
                initialize_wineboot=init_wine,
                allow_network=network,
            )
            console.print(
                f"[bold green]✓[/bold green] Prefix '[bold cyan]{prefix.id}[/bold cyan]' created successfully."
            )
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


# ---------------- Application Commands ----------------
@app_app.command("list")
def app_list() -> None:
    """List all registered Windows applications."""
    svc = AppService()
    apps = svc.list_apps()

    if not apps:
        console.print(
            "[dim]No applications registered. Install one with 'winebox install <file.exe>' or register manually.[/dim]"
        )
        return

    table = Table(title="Registered Applications")
    table.add_column("ID", style="bold cyan")
    table.add_column("Name")
    table.add_column("Prefix", style="magenta")
    table.add_column("Executable Path")
    table.add_column("Status", style="green")

    for a in apps:
        table.add_row(a.id, a.name, a.prefix_id, a.exe_path, a.status.value)
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
    network: bool = typer.Option(True, help="Enable or disable internet access"),
) -> None:
    """Register an existing executable inside a prefix as an application."""
    svc = AppService()
    try:
        policy = SecurityPolicy(network=network)
        app_obj = svc.register_app(
            app_id=app_id,
            name=name,
            prefix_id=prefix_id,
            exe_path=exe_path,
            policy=policy,
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


# ---------------- Runner Commands ----------------
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


# ---------------- Import Commands ----------------
@import_app.command("app")
def import_portable_app(
    source_dir: Path = typer.Argument(..., help="Path to source portable app folder"),
    prefix_id: str = typer.Option(..., "--prefix", "-p", help="Target Prefix ID"),
    app_id: str = typer.Option(..., "--id", "-i", help="Application ID"),
    name: str = typer.Option(..., "--name", "-n", help="Application display name"),
    exe: str = typer.Option(..., "--exe", "-e", help="Relative executable name inside folder"),
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


# ---------------- Top-level Install Wizard ----------------
@app.command("install")
def install_wizard(
    installer_path: Path = typer.Argument(..., help="Path to Windows installer (.exe or .msi)"),
    prefix_id: Optional[str] = typer.Option(None, "--prefix", "-p", help="Target prefix ID (prompts if omitted)"),
) -> None:
    """Interactive Installation Wizard for Windows EXE / MSI installers."""
    prefix_svc = PrefixService()
    prefixes = prefix_svc.list_prefixes()

    # Step 1: Prefix Selection / Creation
    target_prefix = prefix_id
    if not target_prefix:
        console.print("\n[bold cyan]WineBox Installation Wizard[/bold cyan]")
        console.print("Installer:", str(installer_path.resolve()))

        if prefixes:
            console.print("\nExisting prefixes:")
            for idx, p in enumerate(prefixes, 1):
                console.print(f"  {idx}. [bold cyan]{p.id}[/bold cyan] ({p.name})")
            console.print(f"  {len(prefixes) + 1}. [bold yellow][Create New Prefix][/bold yellow]")

            choice = typer.prompt(
                f"Select prefix (1-{len(prefixes) + 1})",
                default="1",
            )
            try:
                choice_int = int(choice)
                if 1 <= choice_int <= len(prefixes):
                    target_prefix = prefixes[choice_int - 1].id
            except ValueError:
                pass

        if not target_prefix:
            # Create new prefix
            new_id = typer.prompt("Enter new prefix ID", default="default")
            new_name = typer.prompt("Enter new prefix display name", default=new_id)
            with console.status(f"[bold green]Creating prefix '{new_id}'..."):
                prefix_svc.create_prefix(prefix_id=new_id, name=new_name)
            target_prefix = new_id

    # Step 2: Policy Configuration
    allow_net = typer.confirm("Allow internet access for installer?", default=True)

    # Step 3: Run installer in sandbox
    install_svc = InstallService()
    console.print(f"\n[bold green]Launching installer inside sandbox...[/bold green]")
    try:
        candidates = install_svc.run_installer(
            installer_path=installer_path,
            prefix_id=target_prefix,
            policy=SecurityPolicy(network=allow_net),
        )

        console.print("\n[bold green]✓ Installer execution finished.[/bold green]")
        if candidates:
            console.print("\n[bold cyan]Discovered new executables:[/bold cyan]")
            for idx, c in enumerate(candidates, 1):
                console.print(f"  {idx}. {c}")

            reg_choice = typer.prompt(
                f"Select executable to register as application (1-{len(candidates)}, or 'skip')",
                default="1",
            )
            if reg_choice.lower() != "skip":
                try:
                    c_idx = int(reg_choice) - 1
                    chosen_exe = candidates[c_idx]
                    app_id = typer.prompt(
                        "Application ID",
                        default=Path(chosen_exe).stem.lower().replace(" ", "-"),
                    )
                    app_name = typer.prompt("Application Display Name", default=Path(chosen_exe).stem)

                    app_svc = AppService()
                    app_svc.register_app(
                        app_id=app_id,
                        name=app_name,
                        prefix_id=target_prefix,
                        exe_path=chosen_exe,
                    )
                    console.print(
                        f"[bold green]✓[/bold green] Application '{app_name}' registered! Run it with: 'winebox app run {app_id}'"
                    )
                except (ValueError, IndexError):
                    console.print("[dim]Skipping application registration.[/dim]")
    except WineboxError as e:
        console.print(f"[bold red]Installation Error:[/bold red] {e}")
        raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

