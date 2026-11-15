"""Interactive TUI select and multi-select components."""

import sys
from typing import List, Optional, Sequence, Set, Tuple
import typer
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from winebox.interface.tui.keyboard import read_key
from winebox.interface.tui.utils import console


def _is_interactive() -> bool:
    """Checks whether stdin is a genuine interactive terminal."""
    return sys.stdin.isatty() and not getattr(sys.stdin, "closed", False)


def tui_select(
    title: str,
    options: Sequence[Tuple[str, str]],
    default_index: int = 0,
    subtitle: str = "↑/↓: Navigate  •  Space: Select (●)  •  Enter: Continue",
    force_non_interactive: bool = False,
) -> str:
    """Interactive selector with Up/Down navigation, Space to mark, and Enter to confirm."""
    if not options:
        raise ValueError("tui_select requires at least one option")

    default_index = max(0, min(default_index, len(options) - 1))
    if force_non_interactive or not _is_interactive():
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


def tui_multiselect(
    title: str,
    options: Sequence[Tuple[str, str]],
    subtitle: str = "↑/↓: Navigate  •  Space: Toggle [✓]  •  Enter: Confirm",
    force_non_interactive: bool = False,
) -> List[str]:
    """Interactive multi-selector with Up/Down navigation, Space to toggle checkboxes, and Enter to finish."""
    if not options:
        return []

    if force_non_interactive or not _is_interactive():
        return [options[0][0]]

    cursor = 0
    selected_indices: Set[int] = set()
    max_visible = 14

    def render() -> Panel:
        text = Text()
        total = len(options)
        start = max(0, min(cursor - max_visible // 2, max(0, total - max_visible)))
        end = min(total, start + max_visible)
        if start > 0:
            text.append("  ↑ ... more items above ...\n", style="dim")

        for idx in range(start, end):
            val, label = options[idx]
            is_cur = idx == cursor
            is_sel = idx in selected_indices

            pointer = "❯ " if is_cur else "  "
            box = "[✓] " if is_sel else "[ ] "

            text.append(pointer, style="bold cyan" if is_cur else "dim")
            text.append(box, style="bold green" if is_sel else "dim")
            text.append(f"{label}\n", style="bold white" if is_cur else ("green" if is_sel else "white"))

        if end < total:
            text.append("  ↓ ... more items below ...\n", style="dim")

        sel_count = len(selected_indices)
        text.append(f"\n{sel_count} items selected.  {subtitle}", style="dim")
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
                    if cursor in selected_indices:
                        selected_indices.remove(cursor)
                    else:
                        selected_indices.add(cursor)
                    live.update(render(), refresh=True)
                elif key == "ENTER":
                    break
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user.[/yellow]")
        raise typer.Exit(code=1)

    chosen = [options[i][0] for i in sorted(selected_indices)]
    console.print(f"[bold green]✔[/bold green] [bold]{title}:[/bold] [cyan]{', '.join(chosen) if chosen else 'None'}[/cyan]")
    return chosen
