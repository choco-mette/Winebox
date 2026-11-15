#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"
VENV_DIR="$DATA_DIR/winebox/venv"
BIN_PATH="$HOME/.local/bin/winebox"
DESKTOP_FILE="$DATA_DIR/applications/id.winebox.WineBox.desktop"
ICON_FILE="$DATA_DIR/icons/hicolor/scalable/apps/id.winebox.WineBox.svg"

rm -f "$BIN_PATH" "$DESKTOP_FILE" "$ICON_FILE"
rm -rf "$VENV_DIR"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q "$DATA_DIR/applications" || true
fi

echo "WineBox uninstalled from ~/.local (user prefixes and winebox.db were preserved)."
