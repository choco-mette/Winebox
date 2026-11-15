#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(python3 -c "import tomllib, pathlib; print(tomllib.loads(pathlib.Path('$ROOT_DIR/pyproject.toml').read_text())['project']['version'])")"
STAGE_BASE="$ROOT_DIR/build/tarball"
PKG_DIR="$STAGE_BASE/winebox-${VERSION}"
DIST_DIR="$ROOT_DIR/dist"
OUT_TAR="$DIST_DIR/winebox-${VERSION}-linux-noarch.tar.gz"

rm -rf "$STAGE_BASE"
mkdir -p "$PKG_DIR" "$DIST_DIR"

cp -a "$ROOT_DIR/src" "$PKG_DIR/"
cp -a "$ROOT_DIR/packaging" "$PKG_DIR/"
cp -a "$ROOT_DIR/scripts" "$PKG_DIR/"
cp "$ROOT_DIR/pyproject.toml" "$PKG_DIR/"
[ -f "$ROOT_DIR/README.md" ] && cp "$ROOT_DIR/README.md" "$PKG_DIR/"

find "$PKG_DIR" -name "__pycache__" -type d -exec rm -rf {} +

tar -C "$STAGE_BASE" -czf "$OUT_TAR" "winebox-${VERSION}"
echo "Built portable tarball: $OUT_TAR"
