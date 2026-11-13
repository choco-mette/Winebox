"""Import service for portable applications and external Wine prefixes."""

import uuid
from pathlib import Path
from typing import Any, Optional
from winebox.common.exceptions import PrefixAuditError, WineboxError
from winebox.domain.models import Application, Prefix, PrefixOrigin, PrefixStatus, SecurityPolicy
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.infrastructure.fs_adapter import FilesystemAdapter
from winebox.security.auditor import PrefixAuditor


class ImportService:
    """Manages cloning, sanitizing, and importing portable apps and external prefixes."""

    def __init__(self, repo: Optional[Any] = None) -> None:
        self.repo = repo or SqliteRepository()

    def import_portable_app(
        self,
        source_dir: Path,
        prefix_id: str,
        app_id: str,
        name: str,
        exe_rel_path: str,
        runner_id: str = "system-wine",
        policy: Optional[SecurityPolicy] = None,
    ) -> Application:
        """Imports portable app folder via staging directly into the prefix (ADR-008 & ADR-009)."""
        resolved_src = source_dir.resolve()
        if not resolved_src.exists() or not resolved_src.is_dir():
            raise WineboxError(f"Source portable directory not found: {resolved_src}")

        p_dir = self.repo.get_prefix_dir(prefix_id)
        if not p_dir.exists():
            raise WineboxError(f"Target prefix '{prefix_id}' does not exist")

        target_app_dir = p_dir / "prefix" / "drive_c" / "Program Files" / app_id
        if target_app_dir.exists():
            raise WineboxError(f"Application directory already exists: {target_app_dir}")

        # Stage clone
        stage_dir = self.repo.staging_dir / f"app_{uuid.uuid4().hex}"
        try:
            FilesystemAdapter.copy_directory(resolved_src, stage_dir)

            # Audit symlinks in staged copy
            escaping = PrefixAuditor.scan_escaping_symlinks(stage_dir)
            if escaping:
                raise PrefixAuditError(
                    f"Portable app contains {len(escaping)} escaping symlinks. Import aborted."
                )

            # Move atomically to prefix Program Files
            FilesystemAdapter.atomic_move(stage_dir, target_app_dir)
        finally:
            FilesystemAdapter.remove_tree(stage_dir)

        # Full relative exe path from prefix
        full_rel_exe = f"drive_c/Program Files/{app_id}/{exe_rel_path.lstrip('/')}"

        app = Application(
            id=app_id,
            name=name,
            prefix_id=prefix_id,
            exe_path=full_rel_exe,
            runner_id=runner_id,
            policy=policy or SecurityPolicy(),
        )
        self.repo.save_app(app)
        return app

    def import_prefix(
        self,
        source_dir: Path,
        prefix_id: str,
        name: Optional[str] = None,
        runner_id: str = "system-wine",
    ) -> Prefix:
        """Imports external Wine prefix via staging, sanitizes drive mappings, and audits (ADR-010)."""
        resolved_src = source_dir.resolve()
        if not resolved_src.exists() or not resolved_src.is_dir():
            raise WineboxError(f"Source prefix directory not found: {resolved_src}")

        p_dir = self.repo.get_prefix_dir(prefix_id)
        if p_dir.exists():
            raise WineboxError(f"Prefix '{prefix_id}' already exists")

        stage_dir = self.repo.staging_dir / f"prefix_{uuid.uuid4().hex}"
        try:
            FilesystemAdapter.copy_directory(resolved_src, stage_dir)

            # Sanitize drive mappings (Z: host root removal)
            PrefixAuditor.sanitize_dosdevices(stage_dir)

            # Audit prefix
            PrefixAuditor.audit_prefix(stage_dir, check_registry=False)

            # Prepare WineBox prefix structure
            p_dir.mkdir(parents=True, exist_ok=True)
            prefix_target = p_dir / "prefix"
            home_target = p_dir / "home"
            logs_target = p_dir / "logs"

            home_target.mkdir(parents=True, exist_ok=True)
            logs_target.mkdir(parents=True, exist_ok=True)

            FilesystemAdapter.atomic_move(stage_dir, prefix_target)
        finally:
            FilesystemAdapter.remove_tree(stage_dir)

        prefix = Prefix(
            id=prefix_id,
            name=name or prefix_id,
            runner_id=runner_id,
            origin=PrefixOrigin.IMPORTED,
            status=PrefixStatus.READY,
        )
        self.repo.save_prefix(prefix)
        return prefix

