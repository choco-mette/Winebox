"""Process manager and prefix concurrency locking."""

import fcntl
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, List, Optional
from winebox.common.exceptions import ExecutionError, PrefixLockError


class PrefixLock:
    """Manages kernel-level single-instance file lock for a Wine prefix."""

    def __init__(self, prefix_root: Path) -> None:
        self.lock_file = prefix_root / "prefix.lock"
        self._fd: Optional[int] = None

    def acquire(self) -> None:
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._fd = os.open(str(self.lock_file), os.O_CREAT | os.O_RDWR, 0o644)
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Write current PID into lock file for information
            os.ftruncate(self._fd, 0)
            os.write(self._fd, f"{os.getpid()}\n".encode())
        except (BlockingIOError, OSError) as e:
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None
            raise PrefixLockError(
                f"Prefix at '{self.lock_file.parent.name}' is currently in use by another application. "
                "Only one instance per prefix may run simultaneously."
            ) from e

    def release(self) -> None:
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except OSError:
                pass
            finally:
                self._fd = None


@contextmanager
def prefix_lock(prefix_root: Path) -> Generator[PrefixLock, None, None]:
    """Context manager for acquiring and releasing a prefix file lock."""
    lock = PrefixLock(prefix_root)
    lock.acquire()
    try:
        yield lock
    finally:
        lock.release()


class ProcessManager:
    """Supervises and executes subprocesses."""

    @staticmethod
    def run_process(
        command: List[str],
        cwd: Optional[Path] = None,
        env: Optional[dict] = None,
        inherit_stdio: bool = True,
        timeout: Optional[float] = None,
    ) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                env=env,
                stdin=None if inherit_stdio else subprocess.PIPE,
                stdout=None if inherit_stdio else subprocess.PIPE,
                stderr=None if inherit_stdio else subprocess.PIPE,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise ExecutionError(f"Process timed out after {timeout} seconds") from e
        except Exception as e:
            raise ExecutionError(f"Failed to execute process: {e}") from e
