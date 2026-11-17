"""Log manager for automatic rotating file logs per prefix (ADR-020)."""

import logging
from collections import deque
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Optional


class LogManager:
    """Manages rotating file logs for WineBox prefix execution (100MB maxBytes, 3 backups)."""

    MAX_BYTES = 100 * 1024 * 1024  # 100 MB
    BACKUP_COUNT = 3

    def __init__(self, prefixes_dir: Path) -> None:
        self.prefixes_dir = prefixes_dir.resolve()

    def get_log_file(self, prefix_id: str, create_dir: bool = True) -> Path:
        log_dir = self.prefixes_dir / prefix_id / "logs"
        if create_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / "execution.log"

    def _rotate_if_needed(
        self,
        log_file: Path,
        max_bytes: Optional[int] = None,
        backup_count: Optional[int] = None,
    ) -> None:
        """Rotates log file if it exceeds max_bytes."""
        threshold = max_bytes if max_bytes is not None else self.MAX_BYTES
        count = backup_count if backup_count is not None else self.BACKUP_COUNT
        try:
            if not log_file.exists() or log_file.stat().st_size < threshold or count <= 0:
                return
            for i in range(count - 1, 0, -1):
                sfn = log_file.with_name(f"{log_file.name}.{i}")
                dfn = log_file.with_name(f"{log_file.name}.{i + 1}")
                if sfn.exists():
                    sfn.replace(dfn)
            dfn = log_file.with_name(f"{log_file.name}.1")
            log_file.replace(dfn)
        except OSError:
            pass

    def log_event(
        self,
        prefix_id: str,
        message: str,
        level: str = "INFO",
        category: str = "EVENT",
    ) -> None:
        """Appends a single structured event line to prefix execution.log."""
        log_file = self.get_log_file(prefix_id, create_dir=True)
        self._rotate_if_needed(log_file)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cat_tag = f"[{category.upper()}] " if category else ""
        line = f"[{now_str}] [{level.upper()}] {cat_tag}{message}\n"
        try:
            with open(log_file, "a", encoding="utf-8", errors="replace") as f:
                f.write(line)
        except OSError:
            pass

    def clear_logs(self, prefix_id: str) -> None:
        """Clears execution.log and removes backup files for the prefix."""
        log_file = self.get_log_file(prefix_id, create_dir=False)
        if log_file.exists():
            try:
                log_file.unlink(missing_ok=True)
            except OSError:
                pass
        for i in range(1, self.BACKUP_COUNT + 1):
            bk = log_file.with_name(f"{log_file.name}.{i}")
            if bk.exists():
                try:
                    bk.unlink(missing_ok=True)
                except OSError:
                    pass

    def _create_handler(self, log_file: Path) -> RotatingFileHandler:
        handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=self.MAX_BYTES,
            backupCount=self.BACKUP_COUNT,
            encoding="utf-8",
        )
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        return handler

    def log_execution(self, prefix_id: str, app_id: str, stdout: str, stderr: str, exit_code: int) -> None:
        log_file = self.get_log_file(prefix_id, create_dir=True)
        logger_name = f"winebox.prefix.{self.prefixes_dir}.{prefix_id}"
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        handler = self._create_handler(log_file)
        logger.addHandler(handler)
        try:
            logger.info(f"--- Application '{app_id}' Started ---")
            if stdout:
                for line in stdout.strip().splitlines():
                    logger.info(f"[STDOUT] {line}")
            if stderr:
                for line in stderr.strip().splitlines():
                    logger.warning(f"[STDERR] {line}")
            logger.info(f"--- Application '{app_id}' Finished with Exit Code {exit_code} ---")
        finally:
            handler.flush()
            handler.close()
            logger.removeHandler(handler)

    def read_logs(self, prefix_id: str, max_lines: int = 50) -> List[str]:
        log_file = self.get_log_file(prefix_id, create_dir=False)
        if not log_file.exists():
            return []

        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                tail = deque(f, maxlen=max_lines)
                return [line.rstrip() for line in tail]
        except OSError:
            return []
