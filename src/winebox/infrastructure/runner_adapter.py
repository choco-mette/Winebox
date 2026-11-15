"""Runner hub adapter for fetching, safely extracting, and sharing Wine/Proton builds (ADR-026)."""

import json
import os
import shutil
import tarfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from winebox.common.exceptions import WineboxError


RUNNER_SOURCES: Dict[str, Dict[str, str]] = {
    "wine-builds": {
        "repo": "Kron4ek/Wine-Builds",
        "kind": "wine",
        "ext": ".tar.xz",
        "description": "Kron4ek Wine-Builds (Staging / TKG, standalone Wine)",
    },
    "wine-ge": {
        "repo": "GloriousEggroll/wine-ge-custom",
        "kind": "wine",
        "ext": ".tar.xz",
        "description": "Wine-GE Custom (Legacy GloriousEggroll standalone Wine)",
    },
    "ge-proton": {
        "repo": "GloriousEggroll/proton-ge-custom",
        "kind": "proton",
        "ext": ".tar.gz",
        "description": "GE-Proton (GloriousEggroll Proton builds with files/bin/wine)",
    },
}


class RunnerAdapter:
    """Handles GitHub release discovery, safe tar extraction, binary detection, and ecosystem symlinks."""

    @staticmethod
    def get_sources() -> Dict[str, Dict[str, str]]:
        return RUNNER_SOURCES

    @staticmethod
    def get_xdg_data_home(xdg_data_home: Optional[Path] = None) -> Path:
        if xdg_data_home:
            return xdg_data_home
        env_xdg = os.environ.get("XDG_DATA_HOME")
        if env_xdg:
            return Path(env_xdg)
        return Path.home() / ".local" / "share"

    @classmethod
    def get_shared_target_dir(cls, kind: str, xdg_data_home: Optional[Path] = None) -> Path:
        base = cls.get_xdg_data_home(xdg_data_home)
        if kind == "proton":
            return base / "Steam" / "compatibilitytools.d"
        return base / "lutris" / "runners" / "wine"

    @classmethod
    def fetch_releases(cls, source_key: str, limit: int = 10) -> List[Dict[str, str]]:
        """Query GitHub Releases API for downloadable runner tarballs."""
        if source_key not in RUNNER_SOURCES:
            raise WineboxError(
                f"Unknown runner source '{source_key}'. Available: {', '.join(RUNNER_SOURCES.keys())}"
            )

        cfg = RUNNER_SOURCES[source_key]
        url = f"https://api.github.com/repos/{cfg['repo']}/releases?per_page={limit}"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "WineBox-RunnerManager/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            raise WineboxError(f"Failed to fetch releases from '{cfg['repo']}': {e}") from e

        releases: List[Dict[str, str]] = []
        ext = cfg["ext"]
        for rel in data:
            tag = str(rel.get("tag_name") or "").strip()
            assets = rel.get("assets") or []
            chosen_asset = cls._pick_asset(assets, source_key, ext)
            if tag and chosen_asset:
                releases.append(
                    {
                        "source": source_key,
                        "kind": cfg["kind"],
                        "version": tag,
                        "filename": str(chosen_asset["name"]),
                        "url": str(chosen_asset["browser_download_url"]),
                    }
                )
        return releases

    @staticmethod
    def _pick_asset(assets: List[Dict[str, Any]], source_key: str, ext: str) -> Optional[Dict[str, Any]]:
        """Selects the preferred x86_64/amd64 archive asset from a GitHub release."""
        candidates = [
            a for a in assets
            if str(a.get("name", "")).endswith(ext)
            and not str(a.get("name", "")).endswith((".sha256sum", ".sha512sum", ".asc"))
        ]
        if not candidates:
            return None

        if source_key == "wine-builds":
            # Prefer staging-tkg-amd64 or staging-amd64 over wow64/x86 builds
            for preferred in ("staging-tkg-amd64", "staging-amd64", "amd64"):
                for a in candidates:
                    if preferred in str(a.get("name", "")).lower():
                        return a
        return candidates[0]

    @staticmethod
    def download_tarball(url: str, cache_dir: Path, filename: str) -> Path:
        """Downloads runner tarball into cache_dir atomically using a .part file."""
        cache_dir.mkdir(parents=True, exist_ok=True)
        dest_file = cache_dir / filename
        if dest_file.exists() and dest_file.stat().st_size > 0:
            return dest_file

        part_file = cache_dir / f"{filename}.part"
        req = urllib.request.Request(url, headers={"User-Agent": "WineBox-RunnerManager/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp, open(part_file, "wb") as out:
                shutil.copyfileobj(resp, out, length=1024 * 1024)
            os.replace(part_file, dest_file)
            return dest_file
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            part_file.unlink(missing_ok=True)
            raise WineboxError(f"Failed to download runner '{filename}': {e}") from e

    @staticmethod
    def safe_extract_tar(archive_path: Path, dest_dir: Path) -> Path:
        """Safely extracts a .tar.xz / .tar.gz archive after validating against path traversal."""
        if not archive_path.exists():
            raise WineboxError(f"Archive not found: {archive_path}")

        resolved_dest = dest_dir.resolve()
        resolved_dest.mkdir(parents=True, exist_ok=True)

        try:
            with tarfile.open(archive_path, "r:*") as tf:
                members = tf.getmembers()
                for m in members:
                    member_path = Path(m.name)
                    if member_path.is_absolute() or ".." in member_path.parts:
                        raise WineboxError(f"Unsafe archive entry path detected: '{m.name}'")
                    target = (resolved_dest / member_path).resolve()
                    if target != resolved_dest and not target.is_relative_to(resolved_dest):
                        raise WineboxError(f"Archive entry escapes destination: '{m.name}'")
                    if m.issym() or m.islnk():
                        link_target = Path(m.linkname)
                        if link_target.is_absolute():
                            raise WineboxError(f"Unsafe absolute symlink inside archive: '{m.name}' -> '{m.linkname}'")
                        link_resolved = (target.parent / link_target).resolve()
                        if link_resolved != resolved_dest and not link_resolved.is_relative_to(resolved_dest):
                            raise WineboxError(
                                f"Escaping symlink inside archive: '{m.name}' -> '{m.linkname}'"
                            )
                tf.extractall(path=resolved_dest, members=members)
        except tarfile.TarError as e:
            raise WineboxError(f"Failed to extract archive '{archive_path.name}': {e}") from e

        return resolved_dest

    @classmethod
    def detect_wine_binaries(cls, runner_root: Path) -> Tuple[Path, Optional[Path]]:
        """Detects wine and wineserver binaries in standard Wine or GE-Proton layouts."""
        resolved_root = runner_root.resolve()
        candidates = [resolved_root]
        if resolved_root.is_dir():
            subdirs = [d for d in resolved_root.iterdir() if d.is_dir()]
            if len(subdirs) == 1:
                candidates.append(subdirs[0])

        for base in candidates:
            for prefix in (base, base / "files"):
                wine_bin = prefix / "bin" / "wine"
                if wine_bin.exists():
                    wineserver_bin = prefix / "bin" / "wineserver"
                    return wine_bin, (wineserver_bin if wineserver_bin.exists() else None)

        raise WineboxError(f"Could not find 'bin/wine' or 'files/bin/wine' inside '{runner_root}'")

    @classmethod
    def create_shared_symlink(
        cls,
        runner_dir: Path,
        kind: str,
        xdg_data_home: Optional[Path] = None,
    ) -> Path:
        """Creates a rootless symlink in Lutris or Steam compatibilitytools.d."""
        target_parent = cls.get_shared_target_dir(kind, xdg_data_home=xdg_data_home)
        target_parent.mkdir(parents=True, exist_ok=True)
        link_path = target_parent / runner_dir.name
        if link_path.is_symlink() or link_path.exists():
            if link_path.is_symlink() and link_path.resolve() == runner_dir.resolve():
                return link_path
            raise WineboxError(f"Shared runner path already exists: {link_path}")
        link_path.symlink_to(runner_dir.resolve())
        return link_path

    @classmethod
    def remove_shared_symlinks(
        cls,
        runner_id: str,
        xdg_data_home: Optional[Path] = None,
    ) -> None:
        """Removes any shared symlinks pointing to the given runner_id."""
        for kind in ("wine", "proton"):
            link_path = cls.get_shared_target_dir(kind, xdg_data_home=xdg_data_home) / runner_id
            if link_path.is_symlink():
                link_path.unlink(missing_ok=True)

    @classmethod
    def scan_external_runners(cls, xdg_data_home: Optional[Path] = None) -> List[Dict[str, Any]]:
        """Scans user Lutris and Steam directories for existing Wine/Proton runners."""
        found: List[Dict[str, Any]] = []
        for kind in ("wine", "proton"):
            scan_dir = cls.get_shared_target_dir(kind, xdg_data_home=xdg_data_home)
            if not scan_dir.exists() or not scan_dir.is_dir():
                continue
            for entry in sorted(scan_dir.iterdir()):
                if not entry.is_dir():
                    continue
                try:
                    wine_bin, wineserver_bin = cls.detect_wine_binaries(entry)
                    found.append(
                        {
                            "id": entry.name.lower().replace(" ", "-"),
                            "name": entry.name,
                            "kind": kind,
                            "wine_bin": wine_bin,
                            "wineserver_bin": wineserver_bin,
                        }
                    )
                except WineboxError:
                    continue
        return found
