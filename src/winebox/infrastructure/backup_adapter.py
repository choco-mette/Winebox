"""Backup and restore adapter for WineBox prefixes (ADR-027)."""

import io
import json
import os
import shutil
import subprocess
import tarfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from winebox.common.exceptions import WineboxError


class BackupAdapter:
    """Creates and safely extracts compressed prefix snapshots (.tar.zst or .tar.gz)."""

    SUPPORTED_SUFFIXES = (".tar.zst", ".tzst", ".tar.gz", ".tgz", ".tar.xz")

    @staticmethod
    def has_zstd() -> bool:
        return shutil.which("zstd") is not None

    @classmethod
    def default_extension(cls) -> str:
        return ".tar.zst" if cls.has_zstd() else ".tar.gz"

    @staticmethod
    def _validate_tarinfo(member: tarfile.TarInfo, resolved_dest: Path) -> None:
        raw_name = member.name
        if not raw_name:
            return
        member_path = Path(raw_name)
        if member_path.is_absolute() or raw_name.startswith("/") or ".." in member_path.parts:
            raise WineboxError(f"Unsafe archive member path: '{raw_name}'")

        target = (resolved_dest / member_path).resolve()
        if target != resolved_dest and not target.is_relative_to(resolved_dest):
            raise WineboxError(f"Archive path escapes destination: '{raw_name}'")

        if member.issym() or member.islnk():
            link_target = Path(member.linkname)
            if link_target.is_absolute() or member.linkname.startswith("/"):
                raise WineboxError(f"Unsafe absolute symlink inside archive: '{raw_name}' -> '{member.linkname}'")
            base_dir = resolved_dest if member.islnk() else target.parent
            link_resolved = (base_dir / link_target).resolve()
            if link_resolved != resolved_dest and not link_resolved.is_relative_to(resolved_dest):
                raise WineboxError(f"Escaping symlink inside archive: '{raw_name}' -> '{member.linkname}'")

    @staticmethod
    def _exclude_lock_filter(tarinfo: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
        if Path(tarinfo.name).name == "prefix.lock":
            return None
        return tarinfo

    @classmethod
    def _populate_tar(cls, tf: tarfile.TarFile, prefix_dir: Path, manifest: Dict[str, Any]) -> None:
        manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
        info = tarfile.TarInfo(name="manifest.json")
        info.size = len(manifest_bytes)
        info.mode = 0o644
        tf.addfile(info, io.BytesIO(manifest_bytes))

        for item_name in ("prefix", "home", "prefix.toml"):
            item_path = prefix_dir / item_name
            if item_path.exists():
                tf.add(item_path, arcname=item_name, filter=cls._exclude_lock_filter)

    @classmethod
    def create_archive(cls, prefix_dir: Path, output_path: Path, manifest: Dict[str, Any]) -> Path:
        """Creates an atomic .tar.zst (or .tar.gz fallback) snapshot of prefix_dir."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = output_path.with_name(f".{output_path.name}.tmp")
        use_zstd = output_path.name.endswith((".tar.zst", ".tzst"))

        if use_zstd and not cls.has_zstd():
            raise WineboxError("Cannot create .tar.zst archive: 'zstd' binary not found on host.")

        try:
            if use_zstd:
                proc = subprocess.Popen(
                    ["zstd", "-T0", "-3", "-f", "-o", str(tmp_path), "-"],
                    stdin=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                assert proc.stdin is not None
                try:
                    with tarfile.open(fileobj=proc.stdin, mode="w|") as tf:
                        cls._populate_tar(tf, prefix_dir, manifest)
                    proc.stdin.close()
                    stderr_bytes = proc.stderr.read() if proc.stderr else b""
                    if proc.stderr:
                        proc.stderr.close()
                    rc = proc.wait()
                    if rc != 0:
                        err = stderr_bytes.decode("utf-8", errors="ignore").strip()
                        raise WineboxError(f"zstd compression failed: {err}")
                except Exception:
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait()
                    raise
            else:
                with tarfile.open(tmp_path, mode="w:gz") as tf:
                    cls._populate_tar(tf, prefix_dir, manifest)

            os.replace(tmp_path, output_path)
            return output_path
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    @classmethod
    @contextmanager
    def _open_tar_stream(cls, archive_path: Path) -> Iterator[tarfile.TarFile]:
        if archive_path.name.endswith((".tar.zst", ".tzst")):
            if not cls.has_zstd():
                raise WineboxError("Cannot read .tar.zst archive: 'zstd' binary not found on host.")
            proc = subprocess.Popen(
                ["zstd", "-dc", str(archive_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            assert proc.stdout is not None
            try:
                with tarfile.open(fileobj=proc.stdout, mode="r|") as tf:
                    yield tf
            finally:
                proc.stdout.close()
                stderr_bytes = proc.stderr.read() if proc.stderr else b""
                if proc.stderr:
                    proc.stderr.close()
                rc = proc.wait()
                if rc != 0:
                    err = stderr_bytes.decode("utf-8", errors="ignore").strip()
                    raise WineboxError(f"Failed to decompress '{archive_path.name}': {err}")
        else:
            with tarfile.open(archive_path, mode="r:*") as tf:
                yield tf

    @classmethod
    def validate_and_read_manifest(cls, archive_path: Path, dest_dir: Path) -> Optional[Dict[str, Any]]:
        """Validates all archive members against path traversal/escaping symlinks and reads manifest.json."""
        if not archive_path.is_file():
            raise WineboxError(f"Backup archive not found: {archive_path}")

        resolved_dest = dest_dir.resolve()
        manifest: Optional[Dict[str, Any]] = None
        try:
            with cls._open_tar_stream(archive_path) as tf:
                for member in tf:
                    cls._validate_tarinfo(member, resolved_dest)
                    if member.name == "manifest.json" and member.isfile():
                        extracted = tf.extractfile(member)
                        if extracted is not None:
                            manifest = json.loads(extracted.read().decode("utf-8"))
        except (tarfile.TarError, json.JSONDecodeError, UnicodeDecodeError) as e:
            raise WineboxError(f"Invalid backup archive '{archive_path.name}': {e}") from e
        return manifest

    @classmethod
    def extract_archive_safely(cls, archive_path: Path, dest_dir: Path) -> Optional[Dict[str, Any]]:
        """Validates archive members first, then extracts safely into dest_dir."""
        resolved_dest = dest_dir.resolve()
        resolved_dest.mkdir(parents=True, exist_ok=True)
        manifest = cls.validate_and_read_manifest(archive_path, resolved_dest)
        try:
            with cls._open_tar_stream(archive_path) as tf:
                tf.extractall(path=resolved_dest)
        except tarfile.TarError as e:
            raise WineboxError(f"Failed to extract backup archive '{archive_path.name}': {e}") from e
        return manifest

    @classmethod
    def list_backups(cls, backups_dir: Path) -> List[Dict[str, Any]]:
        """Lists backup archives inside backups_dir ordered newest-first."""
        if not backups_dir.exists() or not backups_dir.is_dir():
            return []
        items: List[Dict[str, Any]] = []
        for entry in backups_dir.iterdir():
            if entry.is_file() and entry.name.endswith(cls.SUPPORTED_SUFFIXES):
                stat = entry.stat()
                items.append(
                    {
                        "name": entry.name,
                        "path": entry,
                        "size_bytes": stat.st_size,
                        "mtime": stat.st_mtime,
                    }
                )
        items.sort(key=lambda x: x["mtime"], reverse=True)
        return items
