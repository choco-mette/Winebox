"""Prefix and application security auditor."""

import os
from pathlib import Path
from typing import List, Tuple
from winebox.common.exceptions import PrefixAuditError


class PrefixAuditor:
    """Audits and sanitizes Wine prefixes to prevent host escapes and malicious configuration."""

    @staticmethod
    def sanitize_dosdevices(prefix_path: Path) -> List[str]:
        """Removes or neutralizes dangerous drive mappings like Z: pointing to host root."""
        dosdevices = prefix_path / "dosdevices"
        actions = []
        if not dosdevices.exists():
            return actions

        z_drive = dosdevices / "z:"
        if z_drive.is_symlink() or z_drive.exists():
            try:
                target = os.readlink(z_drive)
                if target in ("/", "/root") or not Path(target).is_relative_to(prefix_path):
                    z_drive.unlink(missing_ok=True)
                    actions.append(f"Neutralized dangerous drive Z: mapping pointing to '{target}'")
            except OSError:
                z_drive.unlink(missing_ok=True)
                actions.append("Removed unreadable drive Z: link")

        return actions

    @classmethod
    def scan_escaping_symlinks(cls, root_dir: Path) -> List[Tuple[Path, Path]]:
        """Finds any symlink within root_dir whose realpath resolves outside root_dir."""
        resolved_root = root_dir.resolve()
        escaping_links: List[Tuple[Path, Path]] = []

        if not root_dir.exists():
            return escaping_links

        for path in root_dir.rglob("*"):
            if path.is_symlink():
                try:
                    resolved_target = path.resolve()
                    if not resolved_target.is_relative_to(resolved_root):
                        escaping_links.append((path, resolved_target))
                except (OSError, RuntimeError):
                    # Broken or circular symlinks
                    escaping_links.append((path, Path("<broken_or_circular>")))

        return escaping_links

    @classmethod
    def audit_prefix(cls, prefix_path: Path, check_registry: bool = True) -> List[str]:
        """Performs a comprehensive security audit of a Wine prefix.

        Raises:
            PrefixAuditError: If high-severity security violations are discovered.
        """
        prefix_dir = prefix_path.resolve()
        if not prefix_dir.exists() or not prefix_dir.is_dir():
            raise PrefixAuditError(f"Prefix directory does not exist: {prefix_dir}")

        warnings: List[str] = []

        # 1. Dosdevices audit
        dosdevices = prefix_dir / "dosdevices"
        if dosdevices.exists():
            z_drive = dosdevices / "z:"
            if z_drive.is_symlink():
                target = os.readlink(z_drive)
                if target == "/":
                    raise PrefixAuditError(
                        "Prefix audit failed: drive Z: directly maps to host root '/'. Run sanitize first."
                    )

        # 2. Symlink escape scan
        escaping = cls.scan_escaping_symlinks(prefix_dir)
        # Exception: links inside dosdevices pointing to valid drive_c are allowed
        critical_escapes = []
        for link, target in escaping:
            # Check if this is an internal Wine dosdevice mapping (e.g. c: -> ../drive_c)
            if link.parent == dosdevices and link.name.lower() in ("c:", "d:"):
                try:
                    if target.is_relative_to(prefix_dir):
                        continue
                except ValueError:
                    pass
            critical_escapes.append((link, target))

        if critical_escapes:
            escapes_summary = ", ".join(f"{l.name} -> {t}" for l, t in critical_escapes[:3])
            raise PrefixAuditError(
                f"Prefix audit failed: detected {len(critical_escapes)} escaping symlinks ({escapes_summary})"
            )

        # 3. Registry presence
        if check_registry:
            system_reg = prefix_dir / "system.reg"
            if not system_reg.exists():
                warnings.append("Notice: 'system.reg' not yet created (prefix may be uninitialized)")

        return warnings

