"""Interactive CLI filesystem browser for directories and installer files."""

import sys
from pathlib import Path
from typing import List, Optional, Tuple
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
) -> Path:
    """Shared interactive CLI directory/file browser engine."""
    current_dir = (start_dir or Path.cwd()).resolve()
    if not sys.stdin.isatty():
        raw = typer.prompt(title, default=str(current_dir) if mode == "dir" else "")
        return Path(raw).expanduser().resolve()

    cursor = 0
    selected_path: Optional[Path] = None
    max_visible = 12
    selectable_kinds = ("SELECT_CURRENT", "DIR") if mode == "dir" else ("FILE",)

    def build_entries(directory: Path) -> List[Tuple[str, str, Optional[Path]]]:
        entries: List[Tuple[str, str, Optional[Path]]] = []
        if mode == "dir":
            entries.append(("SELECT_CURRENT", f"✓ [Pilih Direktori Ini: {directory.name or '/'}]", directory))
        if directory.parent != directory:
            entries.append(("NAV_UP", f"↩ .. (Kembali ke {directory.parent.name or '/'})", directory.parent))
        try:
            items = list(directory.iterdir())
        except PermissionError:
            items = []

        if mode == "file":
            files = sorted([p for p in items if p.is_file() and p.suffix.lower() in extensions], key=lambda x: x.name.lower())
            for f in files:
                entries.append(("FILE", f"📦 {f.name}", f))

        subdirs = sorted([p for p in items if p.is_dir() and not p.name.startswith(".")], key=lambda x: x.name.lower())
        for d in subdirs:
            entries.append(("DIR", f"📁 {d.name}/", d))

        entries.append(("MANUAL", "⌨ [Ketik path manual]", None))
        return entries

    entries = build_entries(current_dir)

    def render() -> Panel:
        text = Text()
        text.append("📂 Lokasi saat ini: ", style="bold yellow")
        text.append(f"{current_dir}\n\n", style="bold white")
        total = len(entries)
        start = max(0, min(cursor - max_visible // 2, max(0, total - max_visible)))
        end = min(total, start + max_visible)
        if start > 0:
            text.append("  ↑ ... item di atas ...\n", style="dim")

        for idx in range(start, end):
            kind, label, path_obj = entries[idx]
            is_cur = idx == cursor
            is_sel = kind in selectable_kinds and path_obj is not None and selected_path == path_obj
            text.append("❯ " if is_cur else "  ", style="bold cyan" if is_cur else "dim")
            text.append("● " if is_sel else "○ ", style="bold green" if is_sel else "dim")
            style = "bold white" if is_cur else ("bold green" if is_sel else ("cyan" if kind in ("SELECT_CURRENT", "FILE") else ("yellow" if kind == "NAV_UP" else "white")))
            text.append(f"{label}\n", style=style)

        if end < total:
            text.append("  ↓ ... item di bawah ...\n", style="dim")
        if selected_path is not None:
            text.append(f"\nTerpilih (●): {selected_path}", style="bold green")
        text.append("\n↑/↓: Navigasi  •  Enter pada 📁/..: Buka folder  •  Space: Pilih (●)  •  Enter: Lanjut", style="dim")
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
        console.print("\n[yellow]Dibatalkan oleh pengguna.[/yellow]")
        raise typer.Exit(code=1)

    if chosen is None:
        raw_path = typer.prompt("Masukkan path lengkap", default=str(current_dir) if mode == "dir" else "")
        chosen = Path(raw_path).expanduser().resolve()

    console.print(f"[bold green]✔[/bold green] [bold]{title}:[/bold] [cyan]{chosen}[/cyan]")
    return chosen


def tui_browse_directory(title: str = "Pilih Direktori Game / Aplikasi", start_dir: Optional[Path] = None) -> Path:
    """Interactive CLI directory browser starting from current working directory."""
    return _tui_browse_fs(title=title, mode="dir", start_dir=start_dir)


def tui_browse_file(
    title: str = "Pilih File Installer (.exe / .msi)",
    start_dir: Optional[Path] = None,
    extensions: Tuple[str, ...] = (".exe", ".msi"),
) -> Path:
    """Interactive CLI file browser for Windows installers."""
    return _tui_browse_fs(title=title, mode="file", start_dir=start_dir, extensions=extensions)
