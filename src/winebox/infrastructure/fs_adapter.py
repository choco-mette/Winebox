"""Filesystem adapter for safe directory copy, atomic moves, and staging."""

import os
import shutil
import tarfile
from pathlib import Path
from typing import Iterable, Optional
from winebox.common.exceptions import WineboxError


class FilesystemAdapter:
    """Handles low-level filesystem operations with atomic guarantees and staging."""

    @staticmethod
    def ensure_dir(path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def copy_directory(src: Path, dest: Path) -> None:
        """Copies an entire directory tree. Dest must not exist yet."""
        if not src.exists():
            raise WineboxError(f"Source directory does not exist: {src}")
        if dest.exists():
            raise WineboxError(f"Destination already exists: {dest}")

        shutil.copytree(src, dest, symlinks=True)

    @staticmethod
    def atomic_move(src: Path, dest: Path) -> None:
        """Atomically moves src to dest using os.replace or atomic rename."""
        if not src.exists():
            raise WineboxError(f"Source path does not exist for atomic move: {src}")

        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(src, dest)
        except OSError as e:
            # If across different filesystems, copy and delete
            shutil.copytree(src, dest, symlinks=True)
            shutil.rmtree(src)

    @staticmethod
    def remove_tree(path: Path) -> None:
        """Safely removes a file or directory tree."""
        if not path.exists():
            return
        if path.is_file() or path.is_symlink():
            path.unlink()
        else:
            shutil.rmtree(path)

    @staticmethod
    def validate_tar_member(member: tarfile.TarInfo, resolved_dest: Path) -> None:
        """Validates a TarInfo member against path traversal, absolute paths, and escaping symlinks."""
        raw_name = member.name
        if not raw_name:
            return
        member_path = Path(raw_name)
        if member_path.is_absolute() or raw_name.startswith("/") or ".." in member_path.parts:
            raise WineboxError(f"Unsafe archive member path: '{raw_name}'")

        target = (resolved_dest / member_path).resolve()
        if target != resolved_dest and not target.is_relative_to(resolved_dest):
            raise WineboxError(f"Archive member escapes destination: '{raw_name}'")

        if member.issym() or member.islnk():
            link_target = Path(member.linkname)
            if link_target.is_absolute() or member.linkname.startswith("/"):
                raise WineboxError(f"Unsafe absolute symlink inside archive: '{raw_name}' -> '{member.linkname}'")
            base_dir = resolved_dest if member.islnk() else target.parent
            link_resolved = (base_dir / link_target).resolve()
            if link_resolved != resolved_dest and not link_resolved.is_relative_to(resolved_dest):
                raise WineboxError(f"Escaping symlink inside archive: '{raw_name}' -> '{member.linkname}'")

    @staticmethod
    def extract_tar_members(
        tf: tarfile.TarFile,
        resolved_dest: Path,
        members: Optional[Iterable[tarfile.TarInfo]] = None,
    ) -> None:
        """Extracts tar members with Python 3.14+ filter='tar' when supported."""
        kwargs = {"filter": "tar"} if hasattr(tarfile, "tar_filter") else {}
        if members is not None:
            tf.extractall(path=resolved_dest, members=members, **kwargs)
        else:
            tf.extractall(path=resolved_dest, **kwargs)

