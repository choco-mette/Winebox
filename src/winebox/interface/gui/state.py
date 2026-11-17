"""Shared GUI service container, async worker helper, and safe prefix file listing."""

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional
from winebox.application.app_service import AppService
from winebox.application.desktop_service import DesktopService
from winebox.application.execution_service import ExecutionService
from winebox.application.group_service import GroupService
from winebox.application.import_service import ImportService
from winebox.application.install_service import InstallService
from winebox.application.prefix import (
    PrefixBackupService,
    PrefixLifecycleService,
    PrefixRuntimeService,
)
from winebox.application.profile_service import ProfileService
from winebox.application.runner_service import RunnerService
from winebox.application.winetricks_service import WinetricksService
from winebox.common.exceptions import WineboxError
from winebox.infrastructure.sqlite_repository import SqliteRepository


@dataclass(frozen=True)
class PrefixFileEntry:
    """Represents a single filesystem entry inside a WineBox prefix."""

    name: str
    rel_path: str
    full_path: Path
    is_dir: bool
    is_symlink: bool
    size_bytes: int


class ServiceContainer:
    """Holds shared repository and application services for the GUI session."""

    def __init__(self, repo: Optional[SqliteRepository] = None) -> None:
        self.repo = repo or SqliteRepository()
        self.app_svc = AppService(repo=self.repo)
        self.exec_svc = ExecutionService(repo=self.repo)
        self.import_svc = ImportService(repo=self.repo)
        self.install_svc = InstallService(repo=self.repo)
        self.desktop_svc = DesktopService(repo=self.repo)
        self.prefix_lifecycle = PrefixLifecycleService(repo=self.repo)
        self.prefix_runtime = PrefixRuntimeService(repo=self.repo)
        self.prefix_backup = PrefixBackupService(repo=self.repo)
        self.runner_svc = RunnerService(repo=self.repo)
        self.profile_svc = ProfileService(repo=self.repo)
        self.winetricks_svc = WinetricksService(repo=self.repo)
        self.group_svc = GroupService(repo=self.repo)


def format_size(size_bytes: int) -> str:
    """Formats byte sizes for human-readable file manager columns."""
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024.0 or unit == "GB":
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{size_bytes} B"


def list_prefix_directory(root_dir: Path, rel_path: str = "") -> List[PrefixFileEntry]:
    """Safely lists a directory inside root_dir without following symlinks outside root."""
    resolved_root = root_dir.resolve()
    if rel_path.startswith("/") or Path(rel_path).is_absolute():
        raise WineboxError(f"Unsafe relative path: '{rel_path}'")
    cleaned_rel = rel_path.strip("/")
    rel_obj = Path(cleaned_rel) if cleaned_rel else Path(".")
    if ".." in rel_obj.parts:
        raise WineboxError(f"Unsafe relative path: '{rel_path}'")

    target_dir = (resolved_root / rel_obj).resolve()
    if target_dir != resolved_root and not target_dir.is_relative_to(resolved_root):
        raise WineboxError(f"Path escapes prefix root: '{rel_path}'")
    if not target_dir.exists() or not target_dir.is_dir():
        return []

    entries: List[PrefixFileEntry] = []
    with os.scandir(target_dir) as it:
        for entry in it:
            is_link = entry.is_symlink()
            is_dir = False if is_link else entry.is_dir(follow_symlinks=False)
            size = 0
            if not is_dir and not is_link:
                try:
                    size = entry.stat(follow_symlinks=False).st_size
                except OSError:
                    size = 0
            child_rel = f"{cleaned_rel}/{entry.name}" if cleaned_rel else entry.name
            entries.append(
                PrefixFileEntry(
                    name=entry.name,
                    rel_path=child_rel,
                    full_path=Path(entry.path),
                    is_dir=is_dir,
                    is_symlink=is_link,
                    size_bytes=size,
                )
            )

    entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
    return entries


def run_async(
    fn: Callable[[], Any],
    on_success: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
) -> threading.Thread:
    """Runs blocking I/O on a daemon thread and delivers callbacks on the GLib main loop."""
    from gi.repository import GLib

    def _worker() -> None:
        try:
            result = fn()
        except Exception as exc:
            if on_error:
                GLib.idle_add(lambda e=exc: (on_error(e), False)[1])
        else:
            if on_success:
                GLib.idle_add(lambda r=result: (on_success(r), False)[1])

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return thread
