"""Prefix and application security auditor."""

import os
from pathlib import Path
from typing import List, Tuple
from winebox.common.exceptions import PrefixAuditError


class PrefixAuditor:
    """Audits and sanitizes Wine prefixes to prevent host escapes and malicious configuration."""

    @staticmethod
    def sanitize_dosdevices(prefix_path: Path) -> List[str]:
        """Removes or neutralizes dangerous drive mappings (e.g. Z:/z: pointing outside prefix)."""
        resolved_prefix = prefix_path.resolve()
        dosdevices = resolved_prefix / "dosdevices"
        actions = []
        if not dosdevices.exists():
            return actions

        for entry in list(dosdevices.iterdir()):
            if not entry.name.endswith(":"):
                continue
            drive_lower = entry.name.lower()
            if entry.is_symlink() or (drive_lower == "z:" and entry.exists()):
                try:
                    if entry.is_symlink():
                        raw_target = os.readlink(entry)
                        if os.path.isabs(raw_target):
                            norm_target = Path(os.path.normpath(raw_target))
                        else:
                            norm_target = Path(os.path.normpath(str(dosdevices / raw_target)))
                        if str(norm_target) in ("/", "/root") or not norm_target.is_relative_to(resolved_prefix):
                            entry.unlink(missing_ok=True)
                            actions.append(
                                f"Neutralized dangerous drive {entry.name} mapping pointing to '{raw_target}'"
                            )
                    elif entry.is_file():
                        entry.unlink(missing_ok=True)
                        actions.append(f"Removed unexpected drive {entry.name} file")
                except OSError:
                    if entry.is_symlink() or entry.is_file():
                        entry.unlink(missing_ok=True)
                        actions.append(f"Removed unreadable drive {entry.name} link")

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

        # 1. Dosdevices audit (case-insensitive across drive symlinks)
        dosdevices = prefix_dir / "dosdevices"
        if dosdevices.exists():
            for entry in dosdevices.iterdir():
                if entry.name.lower() == "z:" and entry.is_symlink():
                    raw_target = os.readlink(entry)
                    norm_target = (
                        os.path.normpath(raw_target)
                        if os.path.isabs(raw_target)
                        else os.path.normpath(str(dosdevices / raw_target))
                    )
                    if norm_target == "/" or not Path(norm_target).is_relative_to(prefix_dir):
                        raise PrefixAuditError(
                            f"Prefix audit failed: drive {entry.name} maps outside prefix ('{raw_target}'). Run sanitize first."
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

