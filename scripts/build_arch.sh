#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(python3 -c "import tomllib, pathlib; print(tomllib.loads(pathlib.Path('$ROOT_DIR/pyproject.toml').read_text())['project']['version'])")"
DIST_DIR="$ROOT_DIR/dist"
ARCH_DIR="$DIST_DIR/arch"
TARBALL="$DIST_DIR/winebox-${VERSION}-linux-noarch.tar.gz"

if [ ! -f "$TARBALL" ]; then
    "$ROOT_DIR/scripts/build_tarball.sh"
fi

rm -rf "$ARCH_DIR"
mkdir -p "$ARCH_DIR"
cp "$TARBALL" "$ARCH_DIR/"

SHA256="$(sha256sum "$TARBALL" | awk '{print $1}')"
sed -e "s/^pkgver=.*/pkgver=${VERSION}/" \
    -e "s/^sha256sums=.*/sha256sums=('${SHA256}')/" \
    "$ROOT_DIR/packaging/arch/PKGBUILD" > "$ARCH_DIR/PKGBUILD"

if command -v makepkg >/dev/null 2>&1; then
    (cd "$ARCH_DIR" && makepkg -sf --noconfirm)
    echo "Built Arch package in: $ARCH_DIR"
else
    echo "Staged Arch PKGBUILD bundle at: $ARCH_DIR (run 'makepkg -si' on Arch Linux)"
fi
