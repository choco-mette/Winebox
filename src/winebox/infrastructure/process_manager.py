"""Process manager and prefix concurrency locking."""

import fcntl
import os
import signal
import subprocess
import time
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

    @classmethod
    def is_locked(cls, prefix_root: Path) -> bool:
        """Check if prefix.lock is currently locked by any running process."""
        lock_file = prefix_root / "prefix.lock"
        if not lock_file.exists():
            return False
        fd: Optional[int] = None
        try:
            fd = os.open(str(lock_file), os.O_RDWR)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        except (BlockingIOError, OSError):
            return True
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass

    @classmethod
    def read_locked_pid(cls, prefix_root: Path) -> Optional[int]:
        """Read the PID recorded inside prefix.lock, if any."""
        lock_file = prefix_root / "prefix.lock"
        if not lock_file.exists():
            return None
        try:
            text = lock_file.read_text(encoding="utf-8").strip()
            if text:
                return int(text.splitlines()[0].strip())
        except (OSError, ValueError):
            pass
        return None


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
    """Supervises, queries, and terminates processes."""

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

    @staticmethod
    def is_pid_alive(pid: int) -> bool:
        """Check if a process with the given PID is currently alive on the host."""
        if pid <= 0:
            return False
        try:
            # First try waitpid non-blocking in case it's a child of current process
            try:
                wpid, _ = os.waitpid(pid, os.WNOHANG)
                if wpid == pid:
                    return False
            except (ChildProcessError, OSError):
                pass

            os.kill(pid, 0)

            # Check if it is a zombie in /proc
            status_file = Path(f"/proc/{pid}/status")
            if status_file.exists():
                for line in status_file.read_text(errors="ignore").splitlines():
                    if line.startswith("State:"):
                        if "Z" in line:  # Zombie
                            return False
                        break

            return True
        except OSError:
            return False

    @classmethod
    def kill_pid(cls, pid: int, timeout: float = 1.0, force: bool = False) -> bool:
        """Terminate a process, trying SIGTERM first (unless force=True) then SIGKILL."""
        if not cls.is_pid_alive(pid):
            return True

        if not force:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                return True
            except PermissionError:
                return False
            except OSError:
                return False

            deadline = time.time() + timeout
            while time.time() < deadline:
                if not cls.is_pid_alive(pid):
                    return True
                time.sleep(0.05)

        # Force kill
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        except OSError:
            return False

        deadline = time.time() + 1.0
        while time.time() < deadline:
            if not cls.is_pid_alive(pid):
                return True
            time.sleep(0.05)

        return not cls.is_pid_alive(pid)

    @classmethod
    def find_processes_by_prefix(cls, prefix_path: Path) -> List[int]:
        """Find any processes on host whose commandline references the prefix path."""
        prefix_str = str(prefix_path.resolve())
        pids: List[int] = []
        my_pid = os.getpid()

        proc_dir = Path("/proc")
        if not proc_dir.exists():
            return pids

        try:
            entries = list(proc_dir.iterdir())
        except OSError:
            return pids

        for entry in entries:
            if not entry.is_dir() or not entry.name.isdigit():
                continue
            pid = int(entry.name)
            if pid == my_pid:
                continue

            try:
                cmdline_file = entry / "cmdline"
                if not cmdline_file.exists():
                    continue
                content = cmdline_file.read_bytes().replace(b"\x00", b" ").decode("utf-8", errors="ignore")
                if prefix_str in content:
                    pids.append(pid)
            except (OSError, UnicodeDecodeError):
                continue

        return pids
