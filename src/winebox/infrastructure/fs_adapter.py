"""Filesystem adapter for safe directory copy, atomic moves, and staging."""

import os
import shutil
from pathlib import Path
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
