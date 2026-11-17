"""Prefix snapshot backup and restore service (ADR-027)."""

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from winebox.application.prefix.runtime import PrefixRuntimeService
from winebox.common.exceptions import ResourceNotFoundError, WineboxError
from winebox.domain.models import Prefix, PrefixOrigin, PrefixStatus
from winebox.infrastructure.backup_adapter import BackupAdapter
from winebox.infrastructure.fs_adapter import FilesystemAdapter
from winebox.infrastructure.log_manager import LogManager
from winebox.infrastructure.process_manager import prefix_lock
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.security.auditor import PrefixAuditor


class PrefixBackupService:
    """Manages portable compressed snapshots (.tar.zst / .tar.gz) for Wine prefixes."""

    def __init__(self, repo: Optional[SqliteRepository] = None) -> None:
        self.repo = repo or SqliteRepository()
        self.log_manager = LogManager(prefixes_dir=self.repo.prefixes_dir)

    def list_backups(self) -> List[Dict[str, Any]]:
        return BackupAdapter.list_backups(self.repo.data_root / "backups")

    def backup_prefix(self, prefix_id: str, output_path: Optional[Path] = None) -> Path:
        """Creates a compressed snapshot archive of a prefix and its isolated home."""
        prefix = self.repo.load_prefix(prefix_id)
        p_dir = self.repo.get_prefix_dir(prefix.id)
        PrefixRuntimeService.ensure_prefix_idle(p_dir, prefix.id)

        if output_path is None:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            output_path = self.repo.data_root / "backups" / f"{prefix.id}_{ts}{BackupAdapter.default_extension()}"

        manifest = {
            "format_version": 1,
            "prefix_id": prefix.id,
            "name": prefix.name,
            "runner_id": prefix.runner_id,
            "default_profile_id": prefix.default_profile_id,
            "origin": prefix.origin.value,
            "created_at": prefix.created_at.isoformat(),
            "backed_up_at": datetime.now(timezone.utc).isoformat(),
        }

        self.log_manager.log_event(prefix.id, f"Creating backup snapshot...", level="INFO", category="BACKUP")
        try:
            with prefix_lock(p_dir):
                result_path = BackupAdapter.create_archive(p_dir, output_path, manifest)
                size_str = f"{result_path.stat().st_size} bytes"
                self.log_manager.log_event(
                    prefix.id,
                    f"Backup saved successfully: '{result_path.name}' ({size_str})",
                    level="INFO",
                    category="BACKUP",
                )
                return result_path
        except Exception as e:
            self.log_manager.log_event(prefix.id, f"Backup failed: {e}", level="ERROR", category="BACKUP")
            raise

    def restore_prefix(
        self,
        archive_path: Path,
        target_prefix_id: Optional[str] = None,
        force: bool = False,
    ) -> Prefix:
        """Safely validates, extracts, sanitizes, and registers a prefix from a backup archive."""
        raw_id = target_prefix_id or archive_path.name.split("_")[0].split(".")[0]
        final_id = raw_id.strip().lower().replace(" ", "-")
        staged_dir = self.repo.staging_dir / f"restore-{uuid.uuid4().hex[:8]}"
        try:
            manifest = BackupAdapter.extract_archive_safely(archive_path, staged_dir)
            if not (staged_dir / "prefix").is_dir():
                raise WineboxError(f"Invalid backup archive '{archive_path.name}': missing 'prefix/' directory.")

            (staged_dir / "home").mkdir(parents=True, exist_ok=True)
            PrefixAuditor.sanitize_dosdevices(staged_dir / "prefix")

            raw_id = target_prefix_id or (manifest or {}).get("prefix_id") or archive_path.name.split("_")[0].split(".")[0]
            final_id = raw_id.strip().lower().replace(" ", "-")
            if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", final_id):
                raise WineboxError(
                    f"Invalid target prefix ID '{raw_id}': use lowercase letters, digits, '-' or '_' only."
                )
            prefixes_root = self.repo.prefixes_dir.resolve()
            dest_dir = self.repo.get_prefix_dir(final_id).resolve()
            if dest_dir == prefixes_root or not dest_dir.is_relative_to(prefixes_root):
                raise WineboxError(f"Invalid target prefix path for ID '{final_id}'.")

            prefix_already_exists = dest_dir.exists() and (
                (dest_dir / "prefix").is_dir() or any(p for p in dest_dir.iterdir() if p.name != "logs")
            )

            if prefix_already_exists:
                if not force:
                    raise WineboxError(
                        f"Prefix '{final_id}' already exists. Use --force to overwrite or --id to restore under a new ID."
                    )
                PrefixRuntimeService.ensure_prefix_idle(dest_dir, final_id)
                backup_old = self.repo.staging_dir / f"old-{final_id}-{uuid.uuid4().hex[:6]}"
                FilesystemAdapter.atomic_move(dest_dir, backup_old)
                try:
                    FilesystemAdapter.atomic_move(staged_dir, dest_dir)
                except Exception:
                    if not dest_dir.exists() and backup_old.exists():
                        FilesystemAdapter.atomic_move(backup_old, dest_dir)
                    raise
                FilesystemAdapter.remove_tree(backup_old)
            else:
                if dest_dir.exists():
                    FilesystemAdapter.remove_tree(dest_dir)
                FilesystemAdapter.atomic_move(staged_dir, dest_dir)
        except Exception as e:
            if final_id and self.repo.get_prefix_dir(final_id).exists():
                self.log_manager.log_event(final_id, f"Restore failed: {e}", level="ERROR", category="RESTORE")
            FilesystemAdapter.remove_tree(staged_dir)
            raise

        runner_id = (manifest or {}).get("runner_id", "system-wine")
        try:
            self.repo.load_runner(runner_id)
        except ResourceNotFoundError:
            runner_id = "system-wine"

        profile_id = (manifest or {}).get("default_profile_id", "permissive")
        try:
            self.repo.load_profile(profile_id)
        except ResourceNotFoundError:
            profile_id = "permissive"

        name = (manifest or {}).get("name") or final_id
        restored = Prefix(
            id=final_id,
            name=name if not target_prefix_id else final_id,
            runner_id=runner_id,
            default_profile_id=profile_id,
            origin=PrefixOrigin.IMPORTED if target_prefix_id else PrefixOrigin.CREATED,
            status=PrefixStatus.READY,
        )
        self.repo.save_prefix(restored)
        self.log_manager.log_event(
            restored.id,
            f"Restore completed successfully into prefix '{restored.id}'",
            level="INFO",
            category="RESTORE",
        )
        return restored
