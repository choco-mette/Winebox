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
        resolved_source = (
            tui_browse_directory("Pilih Direktori Game / Aplikasi")
            if mode == "portable"
            else tui_browse_file("Pilih File Installer (.exe / .msi)")
        )
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
        sorted_profiles = sorted(profiles, key=lambda p: (0 if p.id == "permissive" else 1, p.id))
        prof_options = [
            (p.id, f"{p.id}{' [Default - Cocok Game]' if p.id == 'permissive' else ''} — {p.description}")
            for p in sorted_profiles
        ]
        default_prof_idx = next((i for i, p in enumerate(sorted_profiles) if p.id == "permissive"), 0)
        chosen_profile = tui_select("Pilih Security Profile", prof_options, default_index=default_prof_idx)

    # Step 4: Prefix Selection or Creation
    prefix_svc = PrefixService()
    prefixes = prefix_svc.list_prefixes()
    target_prefix = prefix_id
    if not target_prefix:
        prefix_options = [(p.id, f"{p.id} ({p.name}) [Profile: {p.default_profile_id}]") for p in prefixes]
        prefix_options.append(("__new__", "+ [Buat Prefix Baru]"))
        chosen_prefix = tui_select("Pilih Wine Prefix", prefix_options, default_index=0)
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
            exe_options = [(exe, f"🚀 {exe}") for exe in candidates] + [("__manual__", "⌨ [Ketik path .exe manual]")]
            chosen_exe = tui_select("Pilih File Executable Utama (.exe)", exe_options, default_index=0)
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
            _print_summary_panel(app_name, app_id, target_prefix, chosen_profile, chosen_exe, "Setup Selesai")
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

            exe_options = [(exe, f"🚀 {exe}") for exe in candidates] + [
                ("__manual__", "⌨ [Ketik path .exe manual]"),
                ("__skip__", "⏭ [Lewati registrasi aplikasi]"),
            ]
            chosen_exe = tui_select("Pilih File Executable Hasil Install (.exe)", exe_options, default_index=0)
            if chosen_exe == "__manual__":
                chosen_exe = typer.prompt("Masukkan path relatif .exe di dalam prefix (misal: drive_c/Program Files/...)")

            if chosen_exe != "__skip__":
                AppService().register_app(
                    app_id=app_id,
                    name=app_name,
                    prefix_id=target_prefix,
                    exe_path=chosen_exe,
                    profile_id=chosen_profile,
                )
                _print_summary_panel(app_name, app_id, target_prefix, chosen_profile, chosen_exe, "Instalasi Selesai")

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
                yaml_file = LutrisService().export_app_to_lutris(app_id, launch_lutris=True)
                console.print(
                    f"[bold green]✓[/bold green] Script Lutris dibuat ([dim]{yaml_file}[/dim]). "
                    "Silakan klik [bold cyan]Install[/bold cyan] pada jendela Lutris yang muncul."
                )
    except WineboxError as e:
        console.print(f"[bold red]Setup Error:[/bold red] {e}")
        raise typer.Exit(code=1)


def _print_summary_panel(name: str, app_id: str, prefix: str, profile: str, exe: str, title: str) -> None:
    console.print(
        Panel(
            f"[bold green]✓ Game / Aplikasi berhasil ditambahkan![/bold green]\n\n"
            f"• [bold]Nama:[/bold] {name} ([cyan]{app_id}[/cyan])\n"
            f"• [bold]Prefix:[/bold] {prefix}\n"
            f"• [bold]Profile:[/bold] {profile}\n"
            f"• [bold]Executable:[/bold] {exe}\n\n"
            f"Jalankan dengan perintah:\n"
            f"  [bold yellow]winebox app run {app_id}[/bold yellow]",
            title=f"[bold green]{title}[/bold green]",
            border_style="green",
        )
    )
