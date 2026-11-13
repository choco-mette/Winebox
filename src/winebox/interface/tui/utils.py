"""Text utilities and console helpers for TUI."""

import re
from rich.console import Console

console = Console()


def slugify(text: str) -> str:
    """Converts a display name into a clean lowercase kebab-case ID."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug or "app"

