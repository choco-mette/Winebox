#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT_DIR/scripts/build_tarball.sh"
"$ROOT_DIR/scripts/build_deb.sh"
"$ROOT_DIR/scripts/build_arch.sh"
"$ROOT_DIR/scripts/build_rpm.sh"

echo ""
echo "=== Build Summary (dist/) ==="
ls -lh "$ROOT_DIR/dist"
