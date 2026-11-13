"""Interactive TUI components using termios/tty and Rich Live (npx skills / Clack style)."""

import re
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple
import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

console = Console()


def slugify(text: str) -> str:
    """Converts a display name into a clean lowercase kebab-case ID."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug or "app"


def _read_key() -> str:
    """Reads a single keypress from stdin using termios/tty."""
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            seq = sys.stdin.read(2)
            return {"[A": "UP", "[B": "DOWN", "[C": "RIGHT", "[D": "LEFT"}.get(seq, "ESC")
        if ch in ("\r", "\n"):
            return "ENTER"
        if ch == " ":
            return "SPACE"
        if ch == "\x03":
            raise KeyboardInterrupt()
        return {"k": "UP", "K": "UP", "j": "DOWN", "J": "DOWN"}.get(ch, ch)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def tui_select(
    title: str,
    options: Sequence[Tuple[str, str]],
    default_index: int = 0,
    subtitle: str = "↑/↓: Navigasi  •  Space: Pilih (●)  •  Enter: Lanjut",
) -> str:
    """Interactive selector with Up/Down navigation, Space to mark, and Enter to confirm."""
    if not options:
        raise ValueError("tui_select requires at least one option")

    default_index = max(0, min(default_index, len(options) - 1))
    if not sys.stdin.isatty():
        console.print(f"\n[bold cyan]◆ {title}[/bold cyan]")
        for idx, (_, label) in enumerate(options, 1):
            console.print(f"  {idx}. {label}")
        choice = typer.prompt("Pilih nomor", default=str(default_index + 1))
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
            text.append("  ↑ ... opsi di atas ...\n", style="dim")
        for idx in range(start, end):
            _, label = options[idx]
            is_cur = idx == cursor
            is_sel = idx == selected
            text.append("❯ " if is_cur else "  ", style="bold cyan" if is_cur else "dim")
            text.append("● " if is_sel else "○ ", style="bold green" if is_sel else "dim")
            text.append(f"{label}\n", style="bold white" if is_cur else ("green" if is_sel else "white"))
        if end < total:
            text.append("  ↓ ... opsi di bawah ...\n", style="dim")
        text.append(f"\n{subtitle}", style="dim")
        return Panel(text, title=f"[bold cyan]◆ {title}[/bold cyan]", title_align="left", border_style="cyan", padding=(0, 1))

    try:
        with Live(render(), console=console, auto_refresh=False, transient=True) as live:
            while True:
                key = _read_key()
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
        console.print("\n[yellow]Dibatalkan oleh pengguna.[/yellow]")
        raise typer.Exit(code=1)

    console.print(f"[bold green]✔[/bold green] [bold]{title}:[/bold] [cyan]{chosen_label}[/cyan]")
    return chosen_val


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
                key = _read_key()
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
