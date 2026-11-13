"""Log manager for automatic rotating file logs per prefix (ADR-020)."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Optional


class LogManager:
    """Manages rotating file logs for WineBox prefix execution (5MB maxBytes, 3 backups)."""

    MAX_BYTES = 5 * 1024 * 1024  # 5 MB
    BACKUP_COUNT = 3

    def __init__(self, prefixes_dir: Path) -> None:
        self.prefixes_dir = prefixes_dir.resolve()

    def get_log_file(self, prefix_id: str) -> Path:
        log_dir = self.prefixes_dir / prefix_id / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / "execution.log"

    def get_logger(self, prefix_id: str) -> logging.Logger:
        logger_name = f"winebox.prefix.{prefix_id}"
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)

        # Avoid duplicate handlers if logger is reused
        if not logger.handlers:
            log_file = self.get_log_file(prefix_id)
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
            logger.addHandler(handler)

        return logger

    def log_execution(self, prefix_id: str, app_id: str, stdout: str, stderr: str, exit_code: int) -> None:
        logger = self.get_logger(prefix_id)
        logger.info(f"--- Application '{app_id}' Started ---")
        if stdout:
            for line in stdout.strip().splitlines():
                logger.info(f"[STDOUT] {line}")
        if stderr:
            for line in stderr.strip().splitlines():
                logger.warning(f"[STDERR] {line}")
        logger.info(f"--- Application '{app_id}' Finished with Exit Code {exit_code} ---")

    def read_logs(self, prefix_id: str, max_lines: int = 50) -> List[str]:
        log_file = self.get_log_file(prefix_id)
        if not log_file.exists():
            return []

        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                return [line.rstrip() for line in lines[-max_lines:]]
        except Exception:
            return []
