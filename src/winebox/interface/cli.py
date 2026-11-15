"""WineBox Command Line Interface root router built with Typer and Rich."""

from typing import Optional
import typer
from rich.console import Console

from winebox.interface.commands.add_cmd import add_wizard
from winebox.interface.commands.app_cmd import app_app
from winebox.interface.commands.gui_cmd import launch_gui_command
from winebox.interface.commands.import_cmd import import_app
from winebox.interface.commands.lutris_cmd import lutris_app
from winebox.interface.commands.prefix_cmd import prefix_app
from winebox.interface.commands.profile_cmd import profile_app
from winebox.interface.commands.runner_cmd import runner_app
from winebox.interface.commands.system_cmd import system_app

app = typer.Typer(
    name="winebox",
    help="WineBox: Secure orchestrator for managing Windows applications in Linux via Bubblewrap.",
    no_args_is_help=True,
)

app.add_typer(prefix_app, name="prefix")
app.add_typer(app_app, name="app")
app.add_typer(runner_app, name="runner")
app.add_typer(system_app, name="system")
app.add_typer(import_app, name="import")
app.add_typer(profile_app, name="profile")
app.add_typer(lutris_app, name="lutris")

app.command("add")(add_wizard)
app.command("gui")(launch_gui_command)

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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
