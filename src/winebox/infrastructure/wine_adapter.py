"""Wine adapter for constructing commandlines for Wine operations inside the sandbox."""

from pathlib import Path
from typing import List, Optional
from winebox.domain.models import Runner


class WineAdapter:
    """Constructs command arrays to be invoked inside the Bubblewrap sandbox."""

    @staticmethod
    def get_wine_cmd(runner: Optional[Runner] = None) -> str:
        if runner and not runner.is_system:
            return "/app/runner/bin/wine"
        return "wine"

    @staticmethod
    def get_wineserver_cmd(runner: Optional[Runner] = None) -> str:
        if runner and not runner.is_system:
            return "/app/runner/bin/wineserver"
        return "wineserver"

    @classmethod
    def build_wineboot_cmd(cls, runner: Optional[Runner] = None) -> List[str]:
        return [cls.get_wine_cmd(runner), "wineboot", "-u"]

    @classmethod
    def build_run_cmd(
        cls,
        exe_path: str,
        args: Optional[List[str]] = None,
        runner: Optional[Runner] = None,
    ) -> List[str]:
        cmd = [cls.get_wine_cmd(runner), exe_path]
        if args:
            cmd.extend(args)
        return cmd

    @classmethod
    def build_installer_cmd(
        cls,
        installer_path: str,
        runner: Optional[Runner] = None,
    ) -> List[str]:
        if installer_path.lower().endswith(".msi"):
            return [cls.get_wine_cmd(runner), "msiexec", "/i", installer_path]
        return [cls.get_wine_cmd(runner), installer_path]

    @classmethod
    def build_wineserver_kill_cmd(cls, runner: Optional[Runner] = None) -> List[str]:
        return [cls.get_wineserver_cmd(runner), "-k"]

