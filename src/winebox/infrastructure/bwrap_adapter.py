"""Bubblewrap adapter for executing sandboxed processes."""

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional
from winebox.common.exceptions import ExecutionError, SystemDependencyError
from winebox.infrastructure.process_manager import ProcessManager


class BwrapAdapter:
    """Manages Bubblewrap sandbox execution and host environment readiness."""

    def __init__(self, bwrap_bin: Optional[Path] = None) -> None:
        self.bwrap_bin = bwrap_bin or Path(shutil.which("bwrap") or "/usr/bin/bwrap")

    def verify_ready(self) -> None:
        """Runs a fast dummy container check to ensure userns and bwrap function."""
        if not self.bwrap_bin.exists():
            raise SystemDependencyError(
                f"Bubblewrap binary not found at '{self.bwrap_bin}'. Run 'winebox system doctor'."
            )

        try:
            res = subprocess.run(
                [str(self.bwrap_bin), "--unshare-user", "--ro-bind", "/", "/", "true"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode != 0:
                raise SystemDependencyError(
                    f"Bubblewrap pre-flight failed with code {res.returncode}: {res.stderr.strip()}. "
                    "Ensure unprivileged user namespaces are enabled. Run 'winebox system doctor'."
                )
        except Exception as e:
            raise SystemDependencyError(f"Bubblewrap pre-flight error: {e}") from e

    def execute_in_sandbox(
        self,
        bwrap_args: List[str],
        command_inside: List[str],
        inherit_stdio: bool = True,
        timeout: Optional[float] = None,
    ) -> subprocess.CompletedProcess:
        """Executes a command inside the Bubblewrap sandbox."""
        self.verify_ready()

        full_command = list(bwrap_args)
        full_command.extend(command_inside)

        return ProcessManager.run_process(
            command=full_command,
            inherit_stdio=inherit_stdio,
            timeout=timeout,
        )
