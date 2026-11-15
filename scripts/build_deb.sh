#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(python3 -c "import tomllib, pathlib; print(tomllib.loads(pathlib.Path('$ROOT_DIR/pyproject.toml').read_text())['project']['version'])")"
ARCH="all"
PKG_NAME="winebox_${VERSION}_${ARCH}"
STAGE_DIR="$ROOT_DIR/build/deb/$PKG_NAME"
DIST_DIR="$ROOT_DIR/dist"

rm -rf "$STAGE_DIR"
mkdir -p \
  "$STAGE_DIR/DEBIAN" \
  "$STAGE_DIR/usr/bin" \
  "$STAGE_DIR/usr/lib/python3/dist-packages" \
  "$STAGE_DIR/usr/share/applications" \
  "$STAGE_DIR/usr/share/icons/hicolor/scalable/apps" \
  "$DIST_DIR"

# Copy Python package without __pycache__
cp -a "$ROOT_DIR/src/winebox" "$STAGE_DIR/usr/lib/python3/dist-packages/"
find "$STAGE_DIR/usr/lib/python3/dist-packages/winebox" -name "__pycache__" -type d -exec rm -rf {} +

# Install /usr/bin/winebox wrapper
cat > "$STAGE_DIR/usr/bin/winebox" <<'EOF'
#!/usr/bin/python3
import sys
from winebox.interface.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
EOF
chmod 0755 "$STAGE_DIR/usr/bin/winebox"

# Install desktop entry and icon
install -m 0644 "$ROOT_DIR/packaging/linux/id.winebox.WineBox.desktop" \
  "$STAGE_DIR/usr/share/applications/id.winebox.WineBox.desktop"
install -m 0644 "$ROOT_DIR/packaging/linux/id.winebox.WineBox.svg" \
  "$STAGE_DIR/usr/share/icons/hicolor/scalable/apps/id.winebox.WineBox.svg"

INSTALLED_KB="$(du -sk "$STAGE_DIR/usr" | awk '{print $1}')"

cat > "$STAGE_DIR/DEBIAN/control" <<EOF
Package: winebox
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${INSTALLED_KB}
Maintainer: WineBox Developers <winebox@example.invalid>
Depends: python3 (>= 3.11), bubblewrap, python3-typer, python3-rich, python3-tomli-w, python3-platformdirs, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1
Recommends: wine | wine64
Description: Sandboxed Wine orchestrator for Linux using Bubblewrap
 WineBox isolates Windows applications and games in per-prefix Bubblewrap
 sandboxes with configurable hardware permissions, runner management, and a
 GTK4 + Libadwaita desktop GUI.
EOF

cat > "$STAGE_DIR/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
EOF
chmod 0755 "$STAGE_DIR/DEBIAN/postinst"

cat > "$STAGE_DIR/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
EOF
chmod 0755 "$STAGE_DIR/DEBIAN/postrm"

OUT_DEB="$DIST_DIR/${PKG_NAME}.deb"
dpkg-deb --build --root-owner-group "$STAGE_DIR" "$OUT_DEB"
echo "Built Debian package: $OUT_DEB"
