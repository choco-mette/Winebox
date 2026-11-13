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
from winebox.application.lutris_service import LutrisService
from winebox.application.prefix_service import PrefixService
from winebox.application.profile_service import ProfileService
from winebox.application.runner_service import RunnerService
from winebox.common.doctor import SystemDoctor
from winebox.common.exceptions import WineboxError
from winebox.domain.models import HostMount, MountMode, SecurityPolicy
from winebox.infrastructure.log_manager import LogManager
from winebox.infrastructure.lutris_adapter import LutrisAdapter
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.interface.tui import slugify, tui_browse_directory, tui_browse_file, tui_select

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
profile_app = typer.Typer(help="Manage security profiles and permissions (ADR-020).")
lutris_app = typer.Typer(help="Export and integrate WineBox apps with Lutris GUI (ADR-022).")

app.add_typer(prefix_app, name="prefix")
app.add_typer(app_app, name="app")
app.add_typer(runner_app, name="runner")
app.add_typer(system_app, name="system")
app.add_typer(import_app, name="import")
app.add_typer(profile_app, name="profile")
app.add_typer(lutris_app, name="lutris")

console = Console()


@app.command("help")
def show_help(
    ctx: typer.Context,
    command_name: Optional[str] = typer.Argument(None, help="Command or topic to get help for"),
) -> None:
    """Show help for WineBox or a specific command."""
    root_ctx = ctx.find_root()
    root_cmd = root_ctx.command


    if not command_name:
        console.print(root_cmd.get_help(root_ctx))
        return

    sub_cmd = root_cmd.get_command(root_ctx, command_name)
    if sub_cmd:
        sub_ctx = typer.Context(sub_cmd, parent=root_ctx, info_name=command_name)
        console.print(sub_cmd.get_help(sub_ctx))
    else:
        console.print(f"[bold red]Unknown command or topic:[/bold red] '{command_name}'.\n")
        console.print(root_cmd.get_help(root_ctx))
        raise typer.Exit(code=1)


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
    profile_id: str = typer.Option("permissive", "--profile", help="Default security profile (permissive/balanced/zero-trust/paranoid)"),
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
                default_profile_id=profile_id,
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


# ---------------- Unified Interactive Add Wizard (ADR-021) ----------------
@app.command("add")
def add_wizard(
    source_path: Optional[Path] = typer.Argument(
        None,
        help="Optional path to pre-installed game/app folder or Windows installer (.exe/.msi)",
    ),
    prefix_id: Optional[str] = typer.Option(None, "--prefix", "-p", help="Target prefix ID"),
    profile_id: Optional[str] = typer.Option(None, "--profile", help="Security profile ID (default: permissive)"),
) -> None:
    """Interactive TUI Wizard to add a pre-installed game/app or run a Windows installer."""
    console.print("\n[bold cyan]✨ WineBox Interactive Setup Wizard[/bold cyan]\n")

    # Step 1: Determine Mode & Source Path
    if source_path is not None:
        resolved_source = source_path.expanduser().resolve()
        if not resolved_source.exists():
            console.print(f"[bold red]Error:[/bold red] Path tidak ditemukan: {resolved_source}")
            raise typer.Exit(code=1)
        mode = "portable" if resolved_source.is_dir() else "installer"
        console.print(f"[bold green]✔[/bold green] [bold]Sumber:[/bold] [cyan]{resolved_source}[/cyan] ({mode})")
    else:
        mode = tui_select(
            "Pilih Jenis Aplikasi / Game",
            [
                ("portable", "Folder Game / Aplikasi Pre-installed (Portable)"),
                ("installer", "File Installer Windows (.exe / .msi)"),
            ],
            default_index=0,
        )
        if mode == "portable":
            resolved_source = tui_browse_directory("Pilih Direktori Game / Aplikasi")
        else:
            resolved_source = tui_browse_file("Pilih File Installer (.exe / .msi)")

        if not resolved_source.exists():
            console.print(f"[bold red]Error:[/bold red] Path tidak ditemukan: {resolved_source}")
            raise typer.Exit(code=1)

    # Step 2: Application Name & Auto-Slug ID
    default_name = resolved_source.name if resolved_source.is_dir() else resolved_source.stem
    app_name = typer.prompt("\n◆ Nama Game / Aplikasi", default=default_name)
    app_id = slugify(app_name)
    console.print(f"  [dim]ID otomatis:[/dim] [bold cyan]{app_id}[/bold cyan]\n")

    # Step 3: Security Profile Selection (Default: permissive)
    profile_svc = ProfileService()
    profiles = profile_svc.list_profiles()
    chosen_profile = profile_id
    if not chosen_profile:
        prof_options = []
        default_prof_idx = 0
        # Sort so permissive appears first
        sorted_profiles = sorted(profiles, key=lambda p: (0 if p.id == "permissive" else 1, p.id))
        for idx, p in enumerate(sorted_profiles):
            tag = " [Default - Cocok Game]" if p.id == "permissive" else ""
            prof_options.append((p.id, f"{p.id}{tag} — {p.description}"))
            if p.id == "permissive":
                default_prof_idx = idx

        chosen_profile = tui_select(
            "Pilih Security Profile",
            prof_options,
            default_index=default_prof_idx,
        )

    # Step 4: Prefix Selection or Creation
    prefix_svc = PrefixService()
    prefixes = prefix_svc.list_prefixes()
    target_prefix = prefix_id
    if not target_prefix:
        prefix_options = [
            (p.id, f"{p.id} ({p.name}) [Profile: {p.default_profile_id}]") for p in prefixes
        ]
        prefix_options.append(("__new__", "+ [Buat Prefix Baru]"))
        chosen_prefix = tui_select(
            "Pilih Wine Prefix",
            prefix_options,
            default_index=0,
        )
        if chosen_prefix == "__new__":
            new_prefix_name = typer.prompt("\n◆ Nama Prefix Baru", default=app_name)
            new_prefix_id = slugify(new_prefix_name)
            console.print(f"  [dim]Prefix ID otomatis:[/dim] [bold cyan]{new_prefix_id}[/bold cyan]\n")
            with console.status(f"[bold green]Membuat prefix '{new_prefix_id}' (profile: {chosen_profile})..."):
                try:
                    prefix_svc.create_prefix(
                        prefix_id=new_prefix_id,
                        name=new_prefix_name,
                        default_profile_id=chosen_profile,
                    )
                except WineboxError as e:
                    console.print(f"[bold red]Error membuat prefix:[/bold red] {e}")
                    raise typer.Exit(code=1)
            target_prefix = new_prefix_id
        else:
            target_prefix = chosen_prefix

    # Step 5: Executable Selection & Execution
    try:
        if mode == "portable":
            import_svc = ImportService()
            candidates = import_svc.scan_portable_executables(resolved_source)
            exe_options = [(exe, f"🚀 {exe}") for exe in candidates]
            exe_options.append(("__manual__", "⌨ [Ketik path .exe manual]"))

            chosen_exe = tui_select(
                "Pilih File Executable Utama (.exe)",
                exe_options,
                default_index=0,
            )
            if chosen_exe == "__manual__":
                chosen_exe = typer.prompt("Masukkan path relatif file .exe di dalam folder")

            with console.status(f"[bold green]Mengimpor dan mengaudit '{app_name}' ke prefix '{target_prefix}'..."):
                import_svc.import_portable_app(
                    source_dir=resolved_source,
                    prefix_id=target_prefix,
                    app_id=app_id,
                    name=app_name,
                    exe_rel_path=chosen_exe,
                    profile_id=chosen_profile,
                )

            console.print(
                Panel(
                    f"[bold green]✓ Game / Aplikasi berhasil ditambahkan![/bold green]\n\n"
                    f"• [bold]Nama:[/bold] {app_name} ([cyan]{app_id}[/cyan])\n"
                    f"• [bold]Prefix:[/bold] {target_prefix}\n"
                    f"• [bold]Profile:[/bold] {chosen_profile}\n"
                    f"• [bold]Executable:[/bold] {chosen_exe}\n\n"
                    f"Jalankan dengan perintah:\n"
                    f"  [bold yellow]winebox app run {app_id}[/bold yellow]",
                    title="[bold green]Setup Selesai[/bold green]",
                    border_style="green",
                )
            )
        else:
            prof_obj = profile_svc.get_profile(chosen_profile)
            install_svc = InstallService()
            console.print("\n[bold green]Menjalankan installer di dalam sandbox Bubblewrap...[/bold green]")
            candidates = install_svc.run_installer(
                installer_path=resolved_source,
                prefix_id=target_prefix,
                policy=prof_obj.to_policy(),
            )
            console.print("\n[bold green]✓ Eksekusi installer selesai.[/bold green]")

            exe_options = [(exe, f"🚀 {exe}") for exe in candidates]
            exe_options.append(("__manual__", "⌨ [Ketik path .exe manual]"))
            exe_options.append(("__skip__", "⏭ [Lewati registrasi aplikasi]"))

            chosen_exe = tui_select(
                "Pilih File Executable Hasil Install (.exe)",
                exe_options,
                default_index=0,
            )
            if chosen_exe == "__manual__":
                chosen_exe = typer.prompt("Masukkan path relatif .exe di dalam prefix (misal: drive_c/Program Files/...)")

            if chosen_exe != "__skip__":
                app_svc = AppService()
                app_svc.register_app(
                    app_id=app_id,
                    name=app_name,
                    prefix_id=target_prefix,
                    exe_path=chosen_exe,
                    profile_id=chosen_profile,
                )
                console.print(
                    Panel(
                        f"[bold green]✓ Aplikasi berhasil terinstal dan terdaftar![/bold green]\n\n"
                        f"• [bold]Nama:[/bold] {app_name} ([cyan]{app_id}[/cyan])\n"
                        f"• [bold]Prefix:[/bold] {target_prefix}\n"
                        f"• [bold]Profile:[/bold] {chosen_profile}\n"
                        f"• [bold]Executable:[/bold] {chosen_exe}\n\n"
                        f"Jalankan dengan perintah:\n"
                        f"  [bold yellow]winebox app run {app_id}[/bold yellow]",
                        title="[bold green]Instalasi Selesai[/bold green]",
                        border_style="green",
                    )
                )

        # Step 6: Optional Lutris Integration (ADR-022)
        if (mode == "portable" or chosen_exe != "__skip__") and LutrisAdapter.find_lutris_binary():
            lutris_choice = tui_select(
                "Tambahkan Game ke Lutris Library?",
                [
                    ("yes", "Ya — Buka installer Lutris (lutris --install)"),
                    ("no", "Tidak — Cukup di WineBox saja"),
                ],
                default_index=0,
            )
            if lutris_choice == "yes":
                lutris_svc = LutrisService()
                yaml_file = lutris_svc.export_app_to_lutris(app_id, launch_lutris=True)
                console.print(
                    f"[bold green]✓[/bold green] Script Lutris dibuat ([dim]{yaml_file}[/dim]). "
                    "Silakan klik [bold cyan]Install[/bold cyan] pada jendela Lutris yang muncul."
                )
    except WineboxError as e:
        console.print(f"[bold red]Setup Error:[/bold red] {e}")
        raise typer.Exit(code=1)


# ---------------- Lutris Integration Commands (ADR-022) ----------------
@lutris_app.command("add")
def lutris_add(
    app_id: Optional[str] = typer.Argument(None, help="Application ID to export to Lutris (interactive if omitted)"),
    launch: bool = typer.Option(True, "--launch/--no-launch", help="Launch 'lutris --install' automatically"),
) -> None:
    """Generate an official Lutris installer YAML for a WineBox app and open Lutris to install it."""
    app_svc = AppService()
    apps = app_svc.list_apps()
    if not apps:
        console.print("[yellow]Belum ada aplikasi yang terdaftar di WineBox. Jalankan 'winebox add' terlebih dahulu.[/yellow]")
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
            console.print(f"Jalankan manual dengan: [bold yellow]lutris --install \"{yaml_path}\"[/bold yellow]")
    except WineboxError as e:
        console.print(f"[bold red]Lutris Error:[/bold red] {e}")
        raise typer.Exit(code=1)


# ---------------- Security Profile Commands (ADR-020) ----------------
@profile_app.command("list")
def profile_list() -> None:
    """List all available security profiles."""
    svc = ProfileService()
    profiles = svc.list_profiles()

    table = Table(title="Security Profiles")
    table.add_column("ID", style="bold cyan")
    table.add_column("Display", justify="center")
    table.add_column("Audio", justify="center")
    table.add_column("Network", justify="center")
    table.add_column("GPU", justify="center")
    table.add_column("Type", justify="center")
    table.add_column("Description")

    for p in profiles:
        disp = "[green]ON[/green]" if p.display else "[dim]OFF[/dim]"
        aud = "[green]ON[/green]" if p.audio else "[dim]OFF[/dim]"
        net = "[green]ON[/green]" if p.network else "[dim]OFF[/dim]"
        gpu = "[green]ON[/green]" if p.gpu else "[dim]OFF[/dim]"
        p_type = "[green]Built-in[/green]" if p.is_builtin else "[yellow]Custom[/yellow]"
        table.add_row(p.id, disp, aud, net, gpu, p_type, p.description)

    console.print(table)


@profile_app.command("create")
def profile_create(
    profile_id: Optional[str] = typer.Option(None, "--id", "-i", help="Profile ID (prompted if omitted)"),
) -> None:
    """Interactive wizard to create a new custom security profile."""
    console.print("\n[bold cyan]WineBox Security Profile Creator[/bold cyan]")

    p_id = profile_id or typer.prompt("Profile ID (lowercase, e.g. gaming-strict)")
    p_name = typer.prompt("Display Name", default=p_id.title())
    p_desc = typer.prompt("Description", default="Custom user profile")

    console.print("\n[bold]Configure Permissions:[/bold]")
    allow_display = typer.confirm("Allow Display Server (X11/Wayland)?", default=True)
    allow_audio = typer.confirm("Allow Audio (PulseAudio/PipeWire)?", default=True)
    allow_net = typer.confirm("Allow Network / Internet access?", default=False)
    allow_gpu = typer.confirm("Allow 3D GPU acceleration (/dev/dri)?", default=False)

    svc = ProfileService()
    try:
        prof = svc.create_profile(
            profile_id=p_id,
            name=p_name,
            display=allow_display,
            audio=allow_audio,
            network=allow_net,
            gpu=allow_gpu,
            description=p_desc,
        )
        console.print(f"\n[bold green]✓[/bold green] Security Profile '[bold cyan]{prof.id}[/bold cyan]' created successfully.")
    except WineboxError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@profile_app.command("edit")
def profile_edit(
    profile_id: str = typer.Argument(..., help="Profile ID to edit"),
) -> None:
    """Interactively edit permissions for an existing security profile."""
    svc = ProfileService()
    try:
        prof = svc.get_profile(profile_id)
    except WineboxError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    console.print(f"\n[bold cyan]Editing Profile: {prof.name} ({prof.id})[/bold cyan]")
    if prof.is_builtin:
        console.print("[yellow]Note: Editing a built-in profile will customize its default permissions.[/yellow]")

    new_name = typer.prompt("Display Name", default=prof.name)
    new_desc = typer.prompt("Description", default=prof.description)
    new_disp = typer.confirm("Allow Display Server?", default=prof.display)
    new_aud = typer.confirm("Allow Audio?", default=prof.audio)
    new_net = typer.confirm("Allow Network / Internet?", default=prof.network)
    new_gpu = typer.confirm("Allow 3D GPU acceleration?", default=prof.gpu)

    try:
        svc.update_profile(
            profile_id=profile_id,
            name=new_name,
            display=new_disp,
            audio=new_aud,
            network=new_net,
            gpu=new_gpu,
            description=new_desc,
        )
        console.print(f"[bold green]✓[/bold green] Security Profile '{profile_id}' updated.")
    except WineboxError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@profile_app.command("remove")
def profile_remove(
    profile_id: str = typer.Argument(..., help="Custom profile ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Bypass confirmation prompt"),
) -> None:
    """Delete a custom security profile (fails if in use by active prefixes/apps)."""
    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete profile '{profile_id}'?")
        if not confirm:
            raise typer.Abort()

    svc = ProfileService()
    try:
        svc.delete_profile(profile_id)
        console.print(f"[bold green]✓[/bold green] Security Profile '{profile_id}' deleted.")
    except WineboxError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

