"""Interactive CLI filesystem browser for directories and executable files."""

import sys
from pathlib import Path
from typing import List, Optional, Tuple, Union
import typer
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from winebox.interface.tui.keyboard import read_key
from winebox.interface.tui.utils import console


def _tui_browse_fs(
    title: str,
    mode: str,
    start_dir: Optional[Path] = None,
    extensions: Tuple[str, ...] = (".exe", ".msi"),
    root_boundary: Optional[Path] = None,
    relative_to: Optional[Path] = None,
) -> str:
    """Shared interactive CLI directory/file browser engine."""
    current_dir = (start_dir or Path.cwd()).resolve()
    boundary = root_boundary.resolve() if root_boundary else None
    rel_root = relative_to.resolve() if relative_to else None

    if not sys.stdin.isatty():
        raw = typer.prompt(title, default=str(current_dir) if mode == "dir" else "")
        resolved = Path(raw).expanduser().resolve()
        if rel_root:
            try:
                return str(resolved.relative_to(rel_root))
            except ValueError:
                pass
        return str(resolved)

    cursor = 0
    selected_path: Optional[Path] = None
    max_visible = 12
    selectable_kinds = ("SELECT_CURRENT", "DIR") if mode == "dir" else ("FILE",)

    def build_entries(directory: Path) -> List[Tuple[str, str, Optional[Path]]]:
        entries: List[Tuple[str, str, Optional[Path]]] = []
        if mode == "dir":
            entries.append(("SELECT_CURRENT", f"✓ [Select this directory: {directory.name or '/'}]", directory))

        can_go_up = (directory.parent != directory) and (not boundary or directory != boundary)
        if can_go_up:
            entries.append(("NAV_UP", f"↩ .. (Back to {directory.parent.name or '/'})", directory.parent))

        try:
            items = list(directory.iterdir())
        except PermissionError:
            items = []

        if mode == "file":
            files = sorted([p for p in items if p.is_file() and p.suffix.lower() in extensions], key=lambda x: x.name.lower())
            for f in files:
                entries.append(("FILE", f"⚙ {f.name}", f))

        subdirs = sorted([p for p in items if p.is_dir() and not p.name.startswith(".")], key=lambda x: x.name.lower())
        for d in subdirs:
            entries.append(("DIR", f"📁 {d.name}/", d))

        entries.append(("MANUAL", "⌨ [Enter path manually]", None))
        return entries

    entries = build_entries(current_dir)

    def render() -> Panel:
        text = Text()
        text.append("📂 Current directory: ", style="bold yellow")
        text.append(f"{current_dir}\n\n", style="bold white")
        total = len(entries)
        start = max(0, min(cursor - max_visible // 2, max(0, total - max_visible)))
        end = min(total, start + max_visible)
        if start > 0:
            text.append("  ↑ ... more items above ...\n", style="dim")

        for idx in range(start, end):
            kind, label, path_obj = entries[idx]
            is_cur = idx == cursor
            is_sel = kind in selectable_kinds and path_obj is not None and selected_path == path_obj
            text.append("❯ " if is_cur else "  ", style="bold cyan" if is_cur else "dim")
            text.append("● " if is_sel else "○ ", style="bold green" if is_sel else "dim")
            style = "bold white" if is_cur else ("bold green" if is_sel else ("cyan" if kind in ("SELECT_CURRENT", "FILE") else ("yellow" if kind == "NAV_UP" else "white")))
            text.append(f"{label}\n", style=style)

        if end < total:
            text.append("  ↓ ... more items below ...\n", style="dim")
        if selected_path is not None:
            disp_sel = str(selected_path.relative_to(rel_root)) if rel_root and selected_path.is_relative_to(rel_root) else str(selected_path)
            text.append(f"\nSelected (●): {disp_sel}", style="bold green")
        text.append("\n↑/↓: Navigate  •  Enter on 📁/..: Open folder  •  Space: Select (●)  •  Enter: Continue", style="dim")
        return Panel(text, title=f"[bold cyan]◆ {title}[/bold cyan]", title_align="left", border_style="cyan", padding=(0, 1))

    try:
        with Live(render(), console=console, auto_refresh=False, transient=True) as live:
            while True:
                key = read_key()
                if key == "UP":
                    cursor = (cursor - 1) % len(entries)
                    live.update(render(), refresh=True)
                elif key == "DOWN":
                    cursor = (cursor + 1) % len(entries)
                    live.update(render(), refresh=True)
                elif key == "SPACE":
                    kind, _, path_obj = entries[cursor]
                    if kind in selectable_kinds and path_obj is not None:
                        selected_path = None if selected_path == path_obj else path_obj
                        live.update(render(), refresh=True)
                elif key == "ENTER":
                    kind, _, path_obj = entries[cursor]
                    if selected_path is not None:
                        chosen = selected_path
                        break
                    if kind in ("SELECT_CURRENT", "FILE") and path_obj is not None:
                        chosen = path_obj
                        break
                    if kind in ("NAV_UP", "DIR") and path_obj is not None:
                        current_dir = path_obj.resolve()
                        entries = build_entries(current_dir)
                        cursor = 0
                        selected_path = None
                        live.update(render(), refresh=True)
                    elif kind == "MANUAL":
                        chosen = None
                        break
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user.[/yellow]")
        raise typer.Exit(code=1)

    if chosen is None:
        raw_path = typer.prompt("Enter path", default=str(current_dir) if mode == "dir" else "")
        resolved = Path(raw_path).expanduser().resolve()
    else:
        resolved = chosen

    if rel_root:
        try:
            result_str = str(resolved.relative_to(rel_root))
        except ValueError:
            result_str = str(resolved)
    else:
        result_str = str(resolved)

    console.print(f"[bold green]✔[/bold green] [bold]{title}:[/bold] [cyan]{result_str}[/cyan]")
    return result_str


def tui_browse_directory(title: str = "Select Game / Application Directory", start_dir: Optional[Path] = None) -> Path:
    """Interactive CLI directory browser starting from current working directory."""
    path_str = _tui_browse_fs(title=title, mode="dir", start_dir=start_dir)
    return Path(path_str)


def tui_browse_file(
    title: str = "Select Executable (.exe)",
    start_dir: Optional[Path] = None,
    extensions: Tuple[str, ...] = (".exe", ".msi"),
    root_boundary: Optional[Path] = None,
    relative_to: Optional[Path] = None,
) -> str:
    """Interactive CLI file browser with gear icon (⚙) for executables."""
    return _tui_browse_fs(
        title=title,
        mode="file",
        start_dir=start_dir,
        extensions=extensions,
        root_boundary=root_boundary,
        relative_to=relative_to,
    )
