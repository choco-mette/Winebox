"""Interactive TUI select component."""

import sys
from typing import Optional, Sequence, Tuple
import typer
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from winebox.interface.tui.keyboard import read_key
from winebox.interface.tui.utils import console


def tui_select(
    title: str,
    options: Sequence[Tuple[str, str]],
    default_index: int = 0,
    subtitle: str = "↑/↓: Navigate  •  Space: Select (●)  •  Enter: Continue",
) -> str:
    """Interactive selector with Up/Down navigation, Space to mark, and Enter to confirm."""
    if not options:
        raise ValueError("tui_select requires at least one option")

    default_index = max(0, min(default_index, len(options) - 1))
    if not sys.stdin.isatty():
        console.print(f"\n[bold cyan]◆ {title}[/bold cyan]")
        for idx, (_, label) in enumerate(options, 1):
            console.print(f"  {idx}. {label}")
        choice = typer.prompt("Select number", default=str(default_index + 1))
        try:
            c_idx = int(choice) - 1
            if 0 <= c_idx < len(options):
                return options[c_idx][0]
        except ValueError:
            pass
        return options[default_index][0]

    cursor = default_index
    selected: Optional[int] = default_index
    max_visible = 12

    def render() -> Panel:
        text = Text()
        total = len(options)
        start = max(0, min(cursor - max_visible // 2, max(0, total - max_visible)))
        end = min(total, start + max_visible)
        if start > 0:
            text.append("  ↑ ... more options above ...\n", style="dim")
        for idx in range(start, end):
            _, label = options[idx]
            is_cur = idx == cursor
            is_sel = idx == selected
            text.append("❯ " if is_cur else "  ", style="bold cyan" if is_cur else "dim")
            text.append("● " if is_sel else "○ ", style="bold green" if is_sel else "dim")
            text.append(f"{label}\n", style="bold white" if is_cur else ("green" if is_sel else "white"))
        if end < total:
            text.append("  ↓ ... more options below ...\n", style="dim")
        text.append(f"\n{subtitle}", style="dim")
        return Panel(text, title=f"[bold cyan]◆ {title}[/bold cyan]", title_align="left", border_style="cyan", padding=(0, 1))

    try:
        with Live(render(), console=console, auto_refresh=False, transient=True) as live:
            while True:
                key = read_key()
                if key == "UP":
                    cursor = (cursor - 1) % len(options)
                    live.update(render(), refresh=True)
                elif key == "DOWN":
                    cursor = (cursor + 1) % len(options)
                    live.update(render(), refresh=True)
                elif key == "SPACE":
                    selected = cursor
                    live.update(render(), refresh=True)
                elif key == "ENTER":
                    final_idx = selected if selected is not None else cursor
                    chosen_val, chosen_label = options[final_idx]
                    break
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user.[/yellow]")
        raise typer.Exit(code=1)

    console.print(f"[bold green]✔[/bold green] [bold]{title}:[/bold] [cyan]{chosen_label}[/cyan]")
    return chosen_val
