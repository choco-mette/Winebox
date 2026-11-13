"""Unified interactive TUI 'winebox add' wizard command (ADR-021 & ADR-022)."""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from winebox.application.app_service import AppService
from winebox.application.import_service import ImportService
from winebox.application.install_service import InstallService
from winebox.application.lutris_service import LutrisService
from winebox.application.prefix_service import PrefixService
from winebox.application.profile_service import ProfileService
from winebox.common.exceptions import WineboxError
from winebox.infrastructure.lutris_adapter import LutrisAdapter
from winebox.interface.tui import slugify, tui_browse_directory, tui_browse_file, tui_select

console = Console()


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
            console.print(f"[bold red]Error:[/bold red] Path not found: {resolved_source}")
            raise typer.Exit(code=1)
        mode = "portable" if resolved_source.is_dir() else "installer"
        console.print(f"[bold green]✔[/bold green] [bold]Source:[/bold] [cyan]{resolved_source}[/cyan] ({mode})")
    else:
        mode = tui_select(
            "Select Application / Game Type",
            [
                ("portable", "Pre-installed Game / Application Folder (Portable)"),
                ("installer", "Windows Installer File (.exe / .msi)"),
            ],
            default_index=0,
        )
        resolved_source = (
            tui_browse_directory("Select Game / Application Directory")
            if mode == "portable"
            else tui_browse_file("Select Windows Installer (.exe / .msi)")
        )
        if not resolved_source.exists():
            console.print(f"[bold red]Error:[/bold red] Path not found: {resolved_source}")
            raise typer.Exit(code=1)

    # Step 2: Application Name & Auto-Slug ID
    default_name = resolved_source.name if resolved_source.is_dir() else resolved_source.stem
    app_name = typer.prompt("\n◆ Game / Application Name", default=default_name)
    app_id = slugify(app_name)
    console.print(f"  [dim]Auto-generated ID:[/dim] [bold cyan]{app_id}[/bold cyan]\n")

    # Step 3: Security Profile Selection (Default: permissive)
    profile_svc = ProfileService()
    profiles = profile_svc.list_profiles()
    chosen_profile = profile_id
    if not chosen_profile:
        sorted_profiles = sorted(profiles, key=lambda p: (0 if p.id == "permissive" else 1, p.id))
        prof_options = [
            (p.id, f"{p.id}{' [Default - Recommended for Games]' if p.id == 'permissive' else ''} — {p.description}")
            for p in sorted_profiles
        ]
        default_prof_idx = next((i for i, p in enumerate(sorted_profiles) if p.id == "permissive"), 0)
        chosen_profile = tui_select("Select Security Profile", prof_options, default_index=default_prof_idx)

    # Step 4: Prefix Selection or Creation
    prefix_svc = PrefixService()
    prefixes = prefix_svc.list_prefixes()
    target_prefix = prefix_id
    if not target_prefix:
        prefix_options = [(p.id, f"{p.id} ({p.name}) [Profile: {p.default_profile_id}]") for p in prefixes]
        prefix_options.append(("__new__", "+ [Create New Prefix]"))
        chosen_prefix = tui_select("Select Wine Prefix", prefix_options, default_index=0)
        if chosen_prefix == "__new__":
            new_prefix_name = typer.prompt("\n◆ New Prefix Name", default=app_name)
            new_prefix_id = slugify(new_prefix_name)
            console.print(f"  [dim]Auto-generated Prefix ID:[/dim] [bold cyan]{new_prefix_id}[/bold cyan]\n")
            with console.status(f"[bold green]Creating prefix '{new_prefix_id}' (profile: {chosen_profile})..."):
                try:
                    prefix_svc.create_prefix(
                        prefix_id=new_prefix_id,
                        name=new_prefix_name,
                        default_profile_id=chosen_profile,
                    )
                except WineboxError as e:
                    console.print(f"[bold red]Prefix creation error:[/bold red] {e}")
                    raise typer.Exit(code=1)
            target_prefix = new_prefix_id
        else:
            target_prefix = chosen_prefix

    # Step 5: Executable Selection & Execution
    try:
        if mode == "portable":
            import_svc = ImportService()
            chosen_exe = tui_browse_file(
                title="Select Main Executable File (.exe)",
                start_dir=resolved_source,
                root_boundary=resolved_source,
                relative_to=resolved_source,
                extensions=(".exe",),
            )

            with console.status(f"[bold green]Importing and auditing '{app_name}' into prefix '{target_prefix}'..."):
                import_svc.import_portable_app(
                    source_dir=resolved_source,
                    prefix_id=target_prefix,
                    app_id=app_id,
                    name=app_name,
                    exe_rel_path=chosen_exe,
                    profile_id=chosen_profile,
                )
            _print_summary_panel(app_name, app_id, target_prefix, chosen_profile, chosen_exe, "Setup Completed")
        else:
            prof_obj = profile_svc.get_profile(chosen_profile)
            install_svc = InstallService()
            console.print("\n[bold green]Launching installer inside Bubblewrap sandbox...[/bold green]")
            candidates = install_svc.run_installer(
                installer_path=resolved_source,
                prefix_id=target_prefix,
                policy=prof_obj.to_policy(),
            )
            console.print("\n[bold green]✓ Installer execution finished.[/bold green]")

            exe_options = [(exe, f"⚙ {exe}") for exe in candidates] + [
                ("__manual__", "⌨ [Enter .exe path manually]"),
                ("__skip__", "⏭ [Skip application registration]"),
            ]
            chosen_exe = tui_select("Select Installed Executable (.exe)", exe_options, default_index=0)
            if chosen_exe == "__manual__":
                chosen_exe = typer.prompt("Enter relative .exe path inside prefix (e.g. drive_c/Program Files/...)")

            if chosen_exe != "__skip__":
                AppService().register_app(
                    app_id=app_id,
                    name=app_name,
                    prefix_id=target_prefix,
                    exe_path=chosen_exe,
                    profile_id=chosen_profile,
                )
                _print_summary_panel(app_name, app_id, target_prefix, chosen_profile, chosen_exe, "Installation Completed")

        # Step 6: Optional Lutris Integration (ADR-022)
        if (mode == "portable" or chosen_exe != "__skip__") and LutrisAdapter.find_lutris_binary():
            lutris_choice = tui_select(
                "Add Game to Lutris Library?",
                [
                    ("yes", "Yes — Launch Lutris installer dialog (lutris --install)"),
                    ("no", "No — Keep in WineBox only"),
                ],
                default_index=0,
            )
            if lutris_choice == "yes":
                yaml_file = LutrisService().export_app_to_lutris(app_id, launch_lutris=True)
                console.print(
                    f"[bold green]✓[/bold green] Lutris script generated ([dim]{yaml_file}[/dim]). "
                    "Please click [bold cyan]Install[/bold cyan] on the Lutris prompt window."
                )
    except WineboxError as e:
        console.print(f"[bold red]Setup Error:[/bold red] {e}")
        raise typer.Exit(code=1)


def _print_summary_panel(name: str, app_id: str, prefix: str, profile: str, exe: str, title: str) -> None:
    console.print(
        Panel(
            f"[bold green]✓ Game / Application successfully added![/bold green]\n\n"
            f"• [bold]Name:[/bold] {name} ([cyan]{app_id}[/cyan])\n"
            f"• [bold]Prefix:[/bold] {prefix}\n"
            f"• [bold]Profile:[/bold] {profile}\n"
            f"• [bold]Executable:[/bold] {exe}\n\n"
            f"Launch command:\n"
            f"  [bold yellow]winebox app run {app_id}[/bold yellow]",
            title=f"[bold green]{title}[/bold green]",
            border_style="green",
        )
    )
