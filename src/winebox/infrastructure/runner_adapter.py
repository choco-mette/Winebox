"""Runner hub adapter for fetching, safely extracting, and sharing Wine/Proton builds (ADR-026)."""

import json
import os
import platform
import re
import shutil
import tarfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from winebox.common.exceptions import WineboxError
from winebox.infrastructure.fs_adapter import FilesystemAdapter


RUNNER_SOURCES: Dict[str, Dict[str, str]] = {
    "wine-builds": {
        "repo": "Kron4ek/Wine-Builds",
        "kind": "wine",
        "ext": ".tar.xz",
        "description": "Kron4ek Wine-Builds (Staging / TKG, standalone Wine)",
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
        """Selects the architecture-appropriate archive asset from a GitHub release."""
        candidates = [
            a for a in assets
            if str(a.get("name", "")).endswith(ext)
            and not str(a.get("name", "")).endswith((".sha256sum", ".sha512sum", ".asc"))
        ]
        if not candidates:
            return None

        arch = platform.machine().lower()
        is_arm = arch in ("aarch64", "arm64")

        if is_arm:
            arm_candidates = [a for a in candidates if "aarch64" in str(a.get("name", "")).lower() or "arm64" in str(a.get("name", "")).lower()]
            return arm_candidates[0] if arm_candidates else None

        x86_candidates = [
            a for a in candidates
            if "aarch64" not in str(a.get("name", "")).lower()
            and "arm64" not in str(a.get("name", "")).lower()
        ]
        if not x86_candidates:
            return None

        if source_key == "wine-builds":
            # Prefer staging-tkg-amd64 or staging-amd64 over wow64/x86 builds
            for preferred in ("staging-tkg-amd64", "staging-amd64", "amd64"):
                for a in x86_candidates:
                    if preferred in str(a.get("name", "")).lower():
                        return a
        return x86_candidates[0]

    @staticmethod
    def download_tarball(
        url: str,
        cache_dir: Path,
        filename: str,
        on_progress: Optional[Callable[[int, Optional[int]], None]] = None,
    ) -> Path:
        """Downloads runner tarball into cache_dir atomically using a .part file."""
        if not url.startswith("https://"):
            raise WineboxError(f"Refusing non-HTTPS runner download URL: '{url}'")

        cache_dir.mkdir(parents=True, exist_ok=True)
        dest_file = cache_dir / filename
        if dest_file.exists() and dest_file.stat().st_size > 0:
            if on_progress:
                size = dest_file.stat().st_size
                on_progress(size, size)
            return dest_file

        part_file = cache_dir / f"{filename}.part"
        req = urllib.request.Request(url, headers={"User-Agent": "WineBox-RunnerManager/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp, open(part_file, "wb") as out:
                content_length = resp.headers.get("Content-Length")
                total_bytes = int(content_length) if content_length and content_length.isdigit() else None
                downloaded = 0
                while True:
                    chunk = resp.read(256 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    downloaded += len(chunk)
                    if on_progress:
                        on_progress(downloaded, total_bytes)
            os.replace(part_file, dest_file)
            return dest_file
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            part_file.unlink(missing_ok=True)
            raise WineboxError(f"Failed to download runner '{filename}': {e}") from e

    @staticmethod
    def safe_extract_tar(
        archive_path: Path,
        dest_dir: Path,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """Safely extracts a .tar.xz / .tar.gz archive after validating against path traversal."""
        if not archive_path.exists():
            raise WineboxError(f"Archive not found: {archive_path}")

        resolved_dest = dest_dir.resolve()
        resolved_dest.mkdir(parents=True, exist_ok=True)

        try:
            with tarfile.open(archive_path, "r:*") as tf:
                members = tf.getmembers()
                for m in members:
                    FilesystemAdapter.validate_tar_member(m, resolved_dest)

                total = len(members)
                if on_progress and total > 0:
                    on_progress(0, total)
                    batch_size = 50
                    for idx in range(0, total, batch_size):
                        batch = members[idx : idx + batch_size]
                        FilesystemAdapter.extract_tar_members(tf, resolved_dest, members=batch)
                        on_progress(min(idx + len(batch), total), total)
                else:
                    FilesystemAdapter.extract_tar_members(tf, resolved_dest, members=members)
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
            for prefix in (base, base / "files", base / "dist"):
                wine_bin = prefix / "bin" / "wine"
                if wine_bin.exists():
                    wineserver_bin = prefix / "bin" / "wineserver"
                    return wine_bin, (wineserver_bin if wineserver_bin.exists() else None)

        raise WineboxError(f"Could not find 'bin/wine', 'files/bin/wine', or 'dist/bin/wine' inside '{runner_root}'")

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
    def _get_steam_scan_dirs(cls, xdg_data_home: Optional[Path] = None) -> List[Path]:
        """Collects Steam compatibilitytools.d and steamapps/common directories (native, Debian, Flatpak, extra libraries)."""
        steam_roots: List[Path] = [cls.get_xdg_data_home(xdg_data_home) / "Steam"]
        if xdg_data_home is None:
            home = Path.home()
            steam_roots.extend(
                [
                    home / ".steam" / "root",
                    home / ".steam" / "steam",
                    home / ".steam" / "debian-installation",
                    home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
                ]
            )

        scan_dirs: List[Path] = []
        seen_roots: set[Path] = set()
        seen_dirs: set[Path] = set()

        def _add_dir(path: Path) -> None:
            if path.exists() and path.is_dir():
                resolved = path.resolve()
                if resolved not in seen_dirs:
                    seen_dirs.add(resolved)
                    scan_dirs.append(resolved)

        for root in steam_roots:
            if not root.exists():
                continue
            resolved_root = root.resolve()
            if resolved_root in seen_roots:
                continue
            seen_roots.add(resolved_root)

            _add_dir(resolved_root / "compatibilitytools.d")
            _add_dir(resolved_root / "steamapps" / "common")

            vdf = resolved_root / "steamapps" / "libraryfolders.vdf"
            if vdf.is_file():
                try:
                    content = vdf.read_text(encoding="utf-8", errors="ignore")
                    for match in re.finditer(r'"path"\s+"([^"]+)"', content):
                        _add_dir(Path(match.group(1)) / "steamapps" / "common")
                except OSError:
                    pass

        return scan_dirs

    @classmethod
    def scan_external_runners(cls, xdg_data_home: Optional[Path] = None) -> List[Dict[str, Any]]:
        """Scans user Lutris and Steam directories (including steamapps/common Proton) for Wine/Proton runners."""
        found: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()
        seen_bins: set[Path] = set()

        scan_targets: List[Tuple[str, Path]] = [
            ("wine", cls.get_shared_target_dir("wine", xdg_data_home=xdg_data_home))
        ]
        for steam_dir in cls._get_steam_scan_dirs(xdg_data_home=xdg_data_home):
            scan_targets.append(("proton", steam_dir))

        for kind, scan_dir in scan_targets:
            if not scan_dir.exists() or not scan_dir.is_dir():
                continue
            for entry in sorted(scan_dir.iterdir()):
                if not entry.is_dir():
                    continue
                try:
                    wine_bin, wineserver_bin = cls.detect_wine_binaries(entry)
                except WineboxError:
                    continue

                runner_id = re.sub(r"[^a-z0-9]+", "-", entry.name.lower()).strip("-")
                if not runner_id or runner_id in seen_ids or wine_bin in seen_bins:
                    continue
                seen_ids.add(runner_id)
                seen_bins.add(wine_bin)
                found.append(
                    {
                        "id": runner_id,
                        "name": entry.name,
                        "kind": kind,
                        "wine_bin": wine_bin,
                        "wineserver_bin": wineserver_bin,
                    }
                )
        return found
