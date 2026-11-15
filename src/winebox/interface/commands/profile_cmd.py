"""Security profile management CLI commands (ADR-020)."""

from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from winebox.application.profile_service import ProfileService
from winebox.common.exceptions import WineboxError

profile_app = typer.Typer(help="Manage security profiles and permissions (ADR-020).")
console = Console()


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
    table.add_column("Gamepad", justify="center")
    table.add_column("HIDRaw", justify="center")
    table.add_column("Mic", justify="center")
    table.add_column("Type", justify="center")
    table.add_column("Description")

    for p in profiles:
        disp = "[green]ON[/green]" if p.display else "[dim]OFF[/dim]"
        aud = "[green]ON[/green]" if p.audio else "[dim]OFF[/dim]"
        net = "[green]ON[/green]" if p.network else "[dim]OFF[/dim]"
        gpu = "[green]ON[/green]" if p.gpu else "[dim]OFF[/dim]"
        gp = "[green]ON[/green]" if p.gamepad else "[dim]OFF[/dim]"
        hid = "[green]ON[/green]" if p.hidraw else "[dim]OFF[/dim]"
        mic = "[green]ON[/green]" if p.mic else "[dim]OFF[/dim]"
        p_type = "[green]Built-in[/green]" if p.is_builtin else "[yellow]Custom[/yellow]"
        table.add_row(p.id, disp, aud, net, gpu, gp, hid, mic, p_type, p.description)

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
    allow_gamepad = typer.confirm("Allow Gamepad / Controller input (/dev/input)?", default=False)
    allow_hidraw = typer.confirm("Allow Raw HID devices (/dev/hidraw*)?", default=False)
    allow_mic = typer.confirm("Allow Microphone audio input?", default=False)

    svc = ProfileService()
    try:
        prof = svc.create_profile(
            profile_id=p_id,
            name=p_name,
            display=allow_display,
            audio=allow_audio,
            network=allow_net,
            gpu=allow_gpu,
            gamepad=allow_gamepad,
            hidraw=allow_hidraw,
            mic=allow_mic,
            description=p_desc,
        )
        console.print(
            f"\n[bold green]✓[/bold green] Security Profile '[bold cyan]{prof.id}[/bold cyan]' created successfully."
        )
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
    new_gamepad = typer.confirm("Allow Gamepad / Controller input (/dev/input)?", default=prof.gamepad)
    new_hidraw = typer.confirm("Allow Raw HID devices (/dev/hidraw*)?", default=prof.hidraw)
    new_mic = typer.confirm("Allow Microphone audio input?", default=prof.mic)

    try:
        svc.update_profile(
            profile_id=profile_id,
            name=new_name,
            display=new_disp,
            audio=new_aud,
            network=new_net,
            gpu=new_gpu,
            gamepad=new_gamepad,
            hidraw=new_hidraw,
            mic=new_mic,
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

