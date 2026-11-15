"""Winetricks adapter for locating host binary and constructing command lines."""

import shutil
from pathlib import Path
from typing import List, Optional
from winebox.common.exceptions import WineboxError
from winebox.domain.models import Runner


class WinetricksAdapter:
    """Manages discovery and invocation of Winetricks in Bubblewrap."""

    @staticmethod
    def find_winetricks_binary() -> Optional[Path]:
        """Finds the host winetricks executable."""
        found = shutil.which("winetricks")
        if found:
            return Path(found).resolve()
        for candidate in ["/usr/local/bin/winetricks", "/usr/bin/winetricks", "/usr/games/winetricks"]:
            p = Path(candidate)
            if p.exists():
                return p
        return None

    @classmethod
    def build_winetricks_cmd(
        cls,
        verbs: List[str],
        runner: Optional[Runner] = None,
        unattended: bool = True,
    ) -> List[str]:
        """Builds command array to execute winetricks inside sandbox."""
        bin_path = cls.find_winetricks_binary()
        if not bin_path:
            raise WineboxError(
                "Winetricks binary not found on host. Please install it with: sudo apt install winetricks"
            )

        cmd = [str(bin_path)]
        if unattended and verbs and "gui" not in verbs:
            cmd.append("-q")

        if verbs:
            clean_verbs = [v for v in verbs if v != "gui"]
            cmd.extend(clean_verbs)

        return cmd
