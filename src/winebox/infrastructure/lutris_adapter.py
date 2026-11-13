"""Lutris adapter for generating official Lutris installer YAML scripts and invoking lutris --install."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional
from winebox.common.exceptions import WineboxError
from winebox.domain.models import Application


class LutrisAdapter:
    """Generates Lutris-compatible YAML installer scripts and invokes Lutris CLI."""

    @staticmethod
    def find_lutris_binary() -> Optional[Path]:
        """Finds the host lutris executable (/usr/games/lutris or in PATH)."""
        found = shutil.which("lutris")
        if found:
            return Path(found).resolve()
        fallback = Path("/usr/games/lutris")
        if fallback.exists():
            return fallback
        return None

    @staticmethod
    def resolve_winebox_executable() -> Path:
        """Resolves absolute path to the winebox CLI executable (including inside .venv)."""
        venv_candidate = Path(sys.executable).resolve().parent / "winebox"
        if venv_candidate.exists():
            return venv_candidate
        argv_candidate = Path(sys.argv[0]).resolve()
        if argv_candidate.exists() and argv_candidate.name == "winebox":
            return argv_candidate
        which_candidate = shutil.which("winebox")
        if which_candidate:
            return Path(which_candidate).resolve()
        return venv_candidate

    @classmethod
    def generate_installer_yaml(cls, app: Application, dest_dir: Path) -> Path:
        """Creates an official Lutris installer YAML file for a WineBox application."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        winebox_bin = cls.resolve_winebox_executable()
        yaml_path = dest_dir / f"{app.id}-lutris.yml"

        content = (
            f"name: {json.dumps(app.name)}\n"
            f"game_slug: {json.dumps(app.id)}\n"
            f"slug: {json.dumps(f'{app.id}-winebox')}\n"
            f"version: \"WineBox Sandbox\"\n"
            f"runner: linux\n"
            f"script:\n"
            f"  game:\n"
            f"    exe: {json.dumps(str(winebox_bin))}\n"
            f"    args: {json.dumps(f'app run {app.id}')}\n"
            f"  system:\n"
            f"    disable_runtime: true\n"
        )
        yaml_path.write_text(content, encoding="utf-8")
        return yaml_path

    @classmethod
    def launch_installer(cls, yaml_path: Path) -> None:
        """Launches 'lutris --install <yaml_path>' in a detached session."""
        lutris_bin = cls.find_lutris_binary()
        if not lutris_bin:
            raise WineboxError(
                f"Lutris tidak ditemukan di sistem. File YAML tetap disimpan di: {yaml_path}"
            )

        clean_env = os.environ.copy()
        clean_env.pop("PYTHONPATH", None)
        clean_env.pop("VIRTUAL_ENV", None)

        subprocess.Popen(
            [str(lutris_bin), "--install", str(yaml_path.resolve())],
            env=clean_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
