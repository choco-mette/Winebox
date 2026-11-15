#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/winebox/venv"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"

echo "[1/4] Checking system prerequisites..."
for cmd in python3 bwrap; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Missing required command: $cmd"
        echo "On Debian/Ubuntu install:"
        echo "  sudo apt install bubblewrap python3-venv python3-gi gir1.2-gtk-4.0 gir1.2-adw-1"
        exit 1
    fi
done

if ! python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1')" 2>/dev/null; then
    echo "Warning: GTK4 / Libadwaita Python bindings not found for system python3."
    echo "GUI will require: sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1"
fi

echo "[2/4] Creating user virtual environment at $VENV_DIR..."
mkdir -p "$(dirname "$VENV_DIR")" "$BIN_DIR" "$APPS_DIR" "$ICONS_DIR"
python3 -m venv --system-site-packages "$VENV_DIR"

echo "[3/4] Installing WineBox..."
"$VENV_DIR/bin/pip" install --upgrade pip >/dev/null
"$VENV_DIR/bin/pip" install --no-build-isolation "$ROOT_DIR"

ln -sf "$VENV_DIR/bin/winebox" "$BIN_DIR/winebox"

echo "[4/4] Installing Desktop Entry and Icon..."
install -m 0644 "$ROOT_DIR/packaging/linux/id.winebox.WineBox.desktop" "$APPS_DIR/id.winebox.WineBox.desktop"
install -m 0644 "$ROOT_DIR/packaging/linux/id.winebox.WineBox.svg" "$ICONS_DIR/id.winebox.WineBox.svg"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q "$APPS_DIR" || true
fi

echo "Done! Installed binary at $BIN_DIR/winebox"
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "Note: Add $BIN_DIR to your PATH (e.g. export PATH=\"\$HOME/.local/bin:\$PATH\")" ;;
esac
