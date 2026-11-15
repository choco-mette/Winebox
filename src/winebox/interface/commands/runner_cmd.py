"""Wine runner management CLI commands."""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table
from winebox.application.runner_service import RunnerService
from winebox.common.exceptions import WineboxError
from winebox.interface.tui import tui_select

runner_app = typer.Typer(help="Manage system, external, and Winebox-managed Wine/Proton runners.")
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


@runner_app.command("available")
def runner_available(
    source: Optional[str] = typer.Argument(None, help="Runner source key (e.g. wine-builds, ge-proton)"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of releases to display"),
) -> None:
    """List supported runner sources or available releases from a source."""
    svc = RunnerService()
    if not source:
        sources = svc.list_sources()
        table = Table(title="Supported Runner Sources")
        table.add_column("Source Key", style="bold cyan")
        table.add_column("Kind")
        table.add_column("Repository")
        table.add_column("Description")
        for key, meta in sources.items():
            table.add_row(key, meta["kind"], meta["repo"], meta["description"])
        console.print(table)
        return

    try:
        releases = svc.fetch_available_releases(source, limit=limit)
    except WineboxError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    table = Table(title=f"Available Releases ({source})")
    table.add_column("Version", style="bold cyan")
    table.add_column("Kind")
    table.add_column("Archive")
    for rel in releases:
        table.add_row(rel["version"], rel["kind"], rel["filename"])
    console.print(table)


@runner_app.command("install")
def runner_install(
    source: Optional[str] = typer.Argument(None, help="Runner source key (e.g. wine-builds, ge-proton)"),
    version: Optional[str] = typer.Argument(None, help="Specific release version tag (defaults to latest)"),
    share: bool = typer.Option(
        False,
        "--share",
        help="Symlink installed runner to Lutris/Steam user directory for ecosystem sharing",
    ),
) -> None:
    """Download, safely extract, and register a Wine/Proton runner."""
    svc = RunnerService()
    try:
        selected_source = source
        selected_version = version

        interactive_mode = source is None
        if interactive_mode:
            sources = svc.list_sources()
            source_options = [(k, f"{k} — {m['description']}") for k, m in sources.items()]
            selected_source = tui_select("Select Runner Source", source_options)
            if not selected_source:
                raise typer.Exit(code=0)

            if not selected_version:
                with console.status(f"[cyan]Fetching releases for {selected_source}...[/cyan]"):
                    releases = svc.fetch_available_releases(selected_source, limit=30)
                if not releases:
                    console.print(f"[yellow]No downloadable releases found for '{selected_source}'.[/yellow]")
                    raise typer.Exit(code=1)
                ver_options = [(r["version"], f"{r['version']} ({r['filename']})") for r in releases]
                selected_version = tui_select(f"Select {selected_source} Version", ver_options)
                if not selected_version:
                    raise typer.Exit(code=0)

            if not share:
                share = typer.confirm("Share this runner to Lutris/Steam?", default=False)

        console.print(f"\nInstalling runner from [cyan]{selected_source}[/cyan] ([bold]{selected_version or 'latest'}[/bold])...")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            stage_task = progress.add_task("[cyan]Preparing...", total=None)
            dl_task: Optional[TaskID] = None
            ext_task: Optional[TaskID] = None

            def on_stage(msg: str) -> None:
                progress.update(stage_task, description=f"[cyan]{msg}")

            def on_download(downloaded: int, total: Optional[int]) -> None:
                nonlocal dl_task
                if dl_task is None:
                    dl_task = progress.add_task("[green]Downloading", total=total)
                progress.update(dl_task, completed=downloaded, total=total)

            def on_extract(done: int, total: int) -> None:
                nonlocal ext_task
                if ext_task is None:
                    ext_task = progress.add_task("[yellow]Extracting files", total=total)
                progress.update(ext_task, completed=done, total=total, description=f"[yellow]Extracting ({done}/{total} files)")

            runner, shared_link = svc.install_runner(
                selected_source,
                version=selected_version,
                share=share,
                on_stage=on_stage,
                on_download_progress=on_download,
                on_extract_progress=on_extract,
            )
            progress.update(stage_task, description="[green]Completed", total=1, completed=1)

        console.print(f"[bold green]✓[/bold green] Installed runner '[bold]{runner.id}[/bold]' ({runner.wine_bin})")
        if shared_link:
            console.print(f"[bold green]✓[/bold green] Shared symlink created at {shared_link}")
    except WineboxError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@runner_app.command("scan")
def runner_scan() -> None:
    """Scan Lutris and Steam user directories and register discovered runners."""
    svc = RunnerService()
    added = svc.scan_external_runners()
    if not added:
        console.print("[yellow]No new external runners found.[/yellow]")
        return

    for runner in added:
        console.print(f"[bold green]✓[/bold green] Registered external runner '[bold]{runner.id}[/bold]' ({runner.wine_bin})")


@runner_app.command("share")
def runner_share(
    runner_id: str = typer.Argument(..., help="Registered runner ID to share"),
) -> None:
    """Symlink a Winebox runner into Lutris or Steam user directory."""
    svc = RunnerService()
    try:
        link_path = svc.share_runner(runner_id)
        console.print(f"[bold green]✓[/bold green] Shared '{runner_id}' at {link_path}")
    except WineboxError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@runner_app.command("remove")
def runner_remove(
    runner_id: str = typer.Argument(..., help="Runner ID to remove"),
    keep_files: bool = typer.Option(False, "--keep-files", help="Unregister runner without deleting files"),
) -> None:
    """Unregister a runner, clean shared symlinks, and optionally delete managed files."""
    svc = RunnerService()
    try:
        svc.remove_runner(runner_id, delete_files=not keep_files)
        console.print(f"[bold green]✓[/bold green] Runner '{runner_id}' removed.")
    except WineboxError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
