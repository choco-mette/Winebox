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
    echo "Built RPM package in: $RPM_STAGE/RPMS/noarch"
else
    echo "Staged RPM build tree at: $RPM_STAGE (run 'rpmbuild --define \"_topdir \$PWD\" -bb SPECS/winebox.spec' on Fedora/RHEL/openSUSE)"
fi
