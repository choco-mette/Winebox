#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(python3 -c "import tomllib, pathlib; print(tomllib.loads(pathlib.Path('$ROOT_DIR/pyproject.toml').read_text())['project']['version'])")"
DIST_DIR="$ROOT_DIR/dist"
RPM_STAGE="$DIST_DIR/rpm"
TARBALL="$DIST_DIR/winebox-${VERSION}-linux-noarch.tar.gz"

if [ ! -f "$TARBALL" ]; then
    "$ROOT_DIR/scripts/build_tarball.sh"
fi

rm -rf "$RPM_STAGE"
mkdir -p "$RPM_STAGE/SOURCES" "$RPM_STAGE/SPECS" "$RPM_STAGE/RPMS" "$RPM_STAGE/SRPMS" "$RPM_STAGE/BUILD"
cp "$TARBALL" "$RPM_STAGE/SOURCES/"
sed -e "s/^Version:.*/Version:        ${VERSION}/" \
    "$ROOT_DIR/packaging/rpm/winebox.spec" > "$RPM_STAGE/SPECS/winebox.spec"

if command -v rpmbuild >/dev/null 2>&1; then
    rpmbuild --define "_topdir $RPM_STAGE" -bb "$RPM_STAGE/SPECS/winebox.spec"
    cp "$RPM_STAGE"/RPMS/noarch/*.rpm "$DIST_DIR/"
    echo "Built RPM package(s) in: $DIST_DIR"
elif command -v docker >/dev/null 2>&1; then
    echo "rpmbuild not found on host; building RPM inside fedora:latest container..."
    docker run --rm -v "$RPM_STAGE:/rpmbuild" fedora:latest bash -c \
        "dnf install -y -q rpm-build python3-devel python3-rpm-macros && rpmbuild --define '_topdir /rpmbuild' -bb /rpmbuild/SPECS/winebox.spec && chown -R $(id -u):$(id -g) /rpmbuild"
    cp "$RPM_STAGE"/RPMS/noarch/*.rpm "$DIST_DIR/"
    echo "Built RPM package(s) via Docker in: $DIST_DIR"
else
    echo "Staged RPM build tree at: $RPM_STAGE (install rpmbuild or docker to build .rpm)"
fi
