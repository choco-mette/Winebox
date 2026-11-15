"""Wine prefix management CLI commands."""

from pathlib import Path
from typing import List, Optional
import typer
from rich.console import Console
from rich.table import Table
from winebox.application.prefix_service import PrefixService
from winebox.application.winetricks_service import WinetricksService
from winebox.common.exceptions import WineboxError
from winebox.interface.tui import tui_multiselect, tui_select

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
    log_lines = PrefixService().read_logs(prefix_id=prefix_id, max_lines=lines)

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


WINETRICKS_CATALOG = [
    # DirectX / Vulkan
    ("dxvk", "DXVK — Vulkan-based D3D9/D3D10/D3D11 translation layer"),
    ("vkd3d", "VKD3D — Direct3D 12 to Vulkan translation library"),
    ("d3dcompiler_47", "D3DCompiler_47 — Microsoft Direct3D shader compiler"),
    ("d3dx9", "D3DX9 — Microsoft Direct3D 9 auxiliary libraries"),
    # Visual C++ Runtimes
    ("vcrun2022", "Visual C++ 2015-2022 — MSVC runtime libraries (x86 & x64)"),
    ("vcrun2019", "Visual C++ 2019 — MSVC runtime libraries"),
    ("vcrun2015", "Visual C++ 2015 — MSVC runtime libraries"),
    ("vcrun2013", "Visual C++ 2013 — MSVC runtime libraries"),
    ("vcrun2010", "Visual C++ 2010 — MSVC runtime libraries"),
    # .NET Frameworks
    ("dotnet48", ".NET Framework 4.8 — Microsoft .NET runtime"),
    ("dotnet40", ".NET Framework 4.0 — Microsoft .NET runtime"),
    # Fonts & Audio
    ("corefonts", "Corefonts — Microsoft TrueType core fonts (Arial, Times, Courier)"),
    ("faudio", "FAudio — Accurate XAudio reimplementation for games"),
    # Actions
    ("gui", "🖥 Open Winetricks GUI (Zenity desktop dialog)"),
]


def _select_winetricks_prefix(prefix_svc: PrefixService, prefix_id: Optional[str]) -> str:
    """Resolves prefix_id or prompts interactively when omitted."""
    prefixes = prefix_svc.list_prefixes()
    if not prefixes:
        console.print("[yellow]No prefixes found. Create one first with 'winebox prefix create <id>'.[/yellow]")
        raise typer.Exit(code=1)
    if prefix_id:
        return prefix_id
    pref_options = [(p.id, f"{p.id} ({p.name})") for p in prefixes]
    return tui_select("Select Wine Prefix for Winetricks", pref_options, default_index=0)


def _select_winetricks_verbs(verbs: Optional[List[str]]) -> Optional[List[str]]:
    """Returns CLI verbs or opens interactive catalog selector; returns None if cancelled."""
    selected = list(verbs or [])
    if selected:
        return selected

    catalog_options = list(WINETRICKS_CATALOG) + [("__custom__", "⌨ Enter custom verbs manually")]
    chosen = tui_multiselect("Select Winetricks Packages to Install", catalog_options)
    if not chosen:
        console.print("[dim]No winetricks packages selected. Operation cancelled.[/dim]")
        return None

    if "__custom__" in chosen:
        chosen.remove("__custom__")
        custom_input = typer.prompt("Enter package verbs separated by space (e.g. vcrun2015 mfc42)")
        chosen.extend(custom_input.split())
    return chosen


@prefix_app.command("winetricks")
def prefix_winetricks(
    prefix_id: Optional[str] = typer.Argument(None, help="Prefix ID to run winetricks on (interactive if omitted)"),
    verbs: List[str] = typer.Argument(None, help="Winetricks package verbs to install (e.g. vcrun2022 dxvk)"),
) -> None:
    """Run Winetricks inside the Bubblewrap sandbox with shared cache across prefixes (ADR-023)."""
    target_prefix = _select_winetricks_prefix(PrefixService(), prefix_id)
    selected_verbs = _select_winetricks_verbs(verbs)
    if not selected_verbs:
        return

    console.print(f"\n[bold cyan]Running Winetricks on prefix '{target_prefix}'...[/bold cyan]")
    console.print(f"[dim]Verbs:[/dim] [green]{', '.join(selected_verbs)}[/green]\n")

    try:
        WinetricksService().run_winetricks(
            prefix_id=target_prefix,
            verbs=selected_verbs,
            unattended="gui" not in selected_verbs,
            inherit_stdio=True,
        )
        console.print(f"\n[bold green]✓[/bold green] Winetricks execution on prefix '[bold cyan]{target_prefix}[/bold cyan]' completed successfully.")
    except WineboxError as e:
        console.print(f"\n[bold red]Winetricks Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@prefix_app.command("kill")
def prefix_kill(
    prefix_id: str = typer.Argument(..., help="Prefix ID to terminate processes for"),
    force: bool = typer.Option(False, "--force", "-f", help="Force immediate SIGKILL without SIGTERM grace period"),
) -> None:
    """Terminate all running processes (Wine, bwrap, wineserver) in a prefix (ADR-025)."""
    svc = PrefixService()
    try:
        res = svc.kill_prefix(prefix_id, force=force)
        if not res["running"]:
            console.print(f"[yellow]Prefix '{prefix_id}' is not running. Prefix is idle.[/yellow]")
        else:
            pids_str = ", ".join(str(p) for p in res["killed_pids"]) or "none"
            console.print(
                f"[bold green]✓[/bold green] Terminated processes for prefix '[bold cyan]{prefix_id}[/bold cyan]' "
                f"([dim]PIDs: {pids_str}[/dim])."
            )
    except WineboxError as e:
        console.print(f"[bold red]Kill Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@prefix_app.command("tool")
def prefix_tool(
    prefix_id: Optional[str] = typer.Argument(None, help="Prefix ID to run Wine tool in (interactive if omitted)"),
    tool: Optional[str] = typer.Argument(None, help="Wine tool: winecfg, regedit, cmd, taskmgr, control, uninstaller"),
    args: Optional[List[str]] = typer.Argument(None, help="Optional arguments passed to the Wine tool"),
) -> None:
    """Run a built-in Wine tool (winecfg, regedit, cmd, etc.) inside the Bubblewrap sandbox."""
    svc = PrefixService()
    target_prefix = _select_winetricks_prefix(svc, prefix_id)

    target_tool = tool
    if not target_tool:
        tool_options = [(t, t) for t in PrefixService.ALLOWED_WINE_TOOLS]
        target_tool = tui_select(f"Select Wine Tool for '{target_prefix}'", tool_options, default_index=0)
        if not target_tool:
            raise typer.Exit(code=0)

    console.print(f"\n[bold cyan]Launching '{target_tool}' inside sandbox for prefix '{target_prefix}'...[/bold cyan]")
    try:
        svc.run_tool(prefix_id=target_prefix, tool_name=target_tool, args=args, inherit_stdio=True)
        console.print(f"[bold green]✓[/bold green] Wine tool '{target_tool}' exited cleanly.")
    except WineboxError as e:
        console.print(f"[bold red]Tool Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@prefix_app.command("backup")
def prefix_backup(
    prefix_id: Optional[str] = typer.Argument(None, help="Prefix ID to back up (interactive if omitted)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Destination archive path (.tar.zst or .tar.gz)"),
) -> None:
    """Create a compressed snapshot backup (.tar.zst / .tar.gz) of a prefix and its savegames (ADR-027)."""
    svc = PrefixService()
    target_prefix = _select_winetricks_prefix(svc, prefix_id)

    console.print(f"\n[bold cyan]Backing up prefix '{target_prefix}'...[/bold cyan]")
    try:
        archive_path = svc.backup_prefix(target_prefix, output_path=output)
        size_mb = archive_path.stat().st_size / (1024 * 1024)
        console.print(
            f"[bold green]✓[/bold green] Backup saved to [bold]{archive_path}[/bold] ([dim]{size_mb:.2f} MiB[/dim])."
        )
    except WineboxError as e:
        console.print(f"[bold red]Backup Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@prefix_app.command("restore")
def prefix_restore(
    archive: Optional[Path] = typer.Argument(None, help="Path to backup archive (.tar.zst / .tar.gz)"),
    prefix_id: Optional[str] = typer.Option(None, "--id", help="Target prefix ID (defaults to manifest ID)"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite target prefix if it already exists"),
) -> None:
    """Restore a prefix snapshot safely from a backup archive (ADR-027)."""
    svc = PrefixService()
    target_archive = archive
    if target_archive is None:
        backups = svc.list_backups()
        if not backups:
            console.print("[yellow]No backup archives found in WineBox backups directory.[/yellow]")
            raise typer.Exit(code=1)
        options = [
            (str(b["path"]), f"{b['name']} ({b['size_bytes'] / (1024 * 1024):.2f} MiB)")
            for b in backups
        ]
        chosen = tui_select("Select Prefix Backup to Restore", options, default_index=0)
        if not chosen:
            raise typer.Exit(code=0)
        target_archive = Path(chosen)

    console.print(f"\n[bold cyan]Restoring prefix from '{target_archive.name}'...[/bold cyan]")
    try:
        restored = svc.restore_prefix(target_archive, target_prefix_id=prefix_id, force=force)
        console.print(
            f"[bold green]✓[/bold green] Prefix '[bold cyan]{restored.id}[/bold cyan]' restored and ready."
        )
    except WineboxError as e:
        console.print(f"[bold red]Restore Error:[/bold red] {e}")
        raise typer.Exit(code=1)



