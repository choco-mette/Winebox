"""In-app update service querying GitHub Releases with ETag caching and dual-mode installation (ADR-020)."""

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from winebox import __version__ as CURRENT_VERSION
from winebox.common.exceptions import WineboxError

GITHUB_REPO = "choco-mette/Winebox"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
COOLDOWN_SECONDS = 900  # 15 minutes


@dataclass
class UpdateInfo:
    """Represents release update status and distribution assets."""

    current_version: str
    latest_version: str
    has_update: bool
    release_title: str
    release_notes: str
    html_url: str
    assets: List[Dict[str, str]]
    matching_asset: Optional[Dict[str, str]]
    is_git_install: bool
    distro_family: str


def parse_semver(v_str: str) -> Tuple[int, ...]:
    cleaned = re.sub(r"^[^\d]*", "", v_str.strip())
    parts = []
    for p in cleaned.split("."):
        digits = re.match(r"^\d+", p)
        parts.append(int(digits.group(0)) if digits else 0)
    return tuple(parts)


def is_newer_version(current: str, latest: str) -> bool:
    curr_t = parse_semver(current)
    late_t = parse_semver(latest)
    # Pad to equal length
    max_len = max(len(curr_t), len(late_t))
    curr_pad = curr_t + (0,) * (max_len - len(curr_t))
    late_pad = late_t + (0,) * (max_len - len(late_t))
    return late_pad > curr_pad


class UpdateService:
    """Checks for application updates and orchestrates git pull or package downloads."""

    def __init__(self, data_root: Optional[Path] = None, project_root: Optional[Path] = None) -> None:
        self.data_root = (
            data_root
            or Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "winebox"
        )
        self.cache_dir = self.data_root / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "update_cache.json"
        self.project_root = project_root or Path(__file__).resolve().parent.parent.parent

    def detect_distro_family(self) -> str:
        """Detect Linux distribution family from /etc/os-release."""
        os_release = Path("/etc/os-release")
        if not os_release.is_file():
            return "other"
        try:
            content = os_release.read_text(encoding="utf-8", errors="ignore").lower()
            if any(k in content for k in ("id=debian", "id_like=debian", "id=ubuntu", "id_like=ubuntu")):
                return "debian"
            if any(k in content for k in ("id=fedora", "id_like=fedora", "id=rhel", "id_like=rhel")):
                return "fedora"
            if any(k in content for k in ("id=arch", "id_like=arch", "id=manjaro")):
                return "arch"
        except OSError:
            pass
        return "other"

    def is_git_checkout(self) -> bool:
        """Check if Winebox is running directly from a git working tree."""
        return (self.project_root / ".git").is_dir()

    def find_matching_asset(
        self, assets: List[Dict[str, str]], distro_family: str
    ) -> Optional[Dict[str, str]]:
        """Select the preferred release asset for the user's distribution."""
        ext_map = {
            "debian": ".deb",
            "fedora": ".rpm",
            "arch": ".pkg.tar.zst",
        }
        target_ext = ext_map.get(distro_family)
        if target_ext:
            for a in assets:
                name = a.get("name", "").lower()
                if name.endswith(target_ext):
                    return a

        # Fallback to portable tarball if available
        for a in assets:
            name = a.get("name", "").lower()
            if name.endswith(".tar.gz") and "linux" in name:
                return a
        return assets[0] if assets else None

    def check_update(self, force: bool = False) -> Optional[UpdateInfo]:
        """Check for updates using ETag conditional caching to prevent rate-limit waste."""
        now = time.time()
        cached_data: Dict = {}
        etag: Optional[str] = None
        last_checked = 0.0

        if self.cache_file.is_file():
            try:
                cached_data = json.loads(self.cache_file.read_text(encoding="utf-8"))
                etag = cached_data.get("etag")
                last_checked = float(cached_data.get("last_checked", 0.0))
            except (json.JSONDecodeError, OSError):
                cached_data = {}

        # If within cooldown and not forced, use cached response
        if not force and (now - last_checked) < COOLDOWN_SECONDS and "release" in cached_data:
            return self._build_update_info(cached_data["release"])

        headers = {
            "User-Agent": f"WineBox/{CURRENT_VERSION} (Linux)",
            "Accept": "application/vnd.github.v3+json",
        }
        if etag and not force:
            headers["If-None-Match"] = etag

        req = urllib.request.Request(GITHUB_API_URL, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                new_etag = resp.headers.get("ETag")
                raw_json = resp.read().decode("utf-8")
                release_obj = json.loads(raw_json)

                # Update cache
                self.cache_file.write_text(
                    json.dumps(
                        {
                            "etag": new_etag,
                            "last_checked": now,
                            "release": release_obj,
                        }
                    ),
                    encoding="utf-8",
                )
                return self._build_update_info(release_obj)
        except urllib.error.HTTPError as e:
            if e.code == 304:
                # 304 Not Modified: release hasn't changed, refresh timestamp
                if "release" in cached_data:
                    cached_data["last_checked"] = now
                    try:
                        self.cache_file.write_text(json.dumps(cached_data), encoding="utf-8")
                    except OSError:
                        pass
                    return self._build_update_info(cached_data["release"])
                return None
            return None
        except (urllib.error.URLError, TimeoutError, OSError):
            # Network offline / timeout
            if "release" in cached_data:
                return self._build_update_info(cached_data["release"])
            return None

    def _build_update_info(self, release_dict: Dict) -> UpdateInfo:
        tag_name = release_dict.get("tag_name", "").lstrip("v")
        has_update = is_newer_version(CURRENT_VERSION, tag_name)
        assets_raw = release_dict.get("assets", [])
        assets_clean = [
            {
                "name": a.get("name", ""),
                "size": a.get("size", 0),
                "browser_download_url": a.get("browser_download_url", ""),
            }
            for a in assets_raw
        ]
        distro = self.detect_distro_family()
        matching = self.find_matching_asset(assets_clean, distro)
        is_git = self.is_git_checkout()

        return UpdateInfo(
            current_version=CURRENT_VERSION,
            latest_version=tag_name,
            has_update=has_update,
            release_title=release_dict.get("name", f"Release v{tag_name}"),
            release_notes=release_dict.get("body", "No changelog provided."),
            html_url=release_dict.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest"),
            assets=assets_clean,
            matching_asset=matching,
            is_git_install=is_git,
            distro_family=distro,
        )

    def perform_git_update(self) -> str:
        """Executes git pull --ff-only in the project repository."""
        if not self.is_git_checkout():
            raise WineboxError("Winebox is not running from a git repository checkout.")
        try:
            res = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=30.0,
            )
            if res.returncode != 0:
                raise WineboxError(f"Git pull failed: {res.stderr.strip() or res.stdout.strip()}")
            return res.stdout.strip() or "Updated successfully."
        except Exception as e:
            if not isinstance(e, WineboxError):
                raise WineboxError(f"Failed to execute git update: {e}")
            raise

    def download_package(
        self,
        asset_url: str,
        filename: str,
        dest_dir: Optional[Path] = None,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """Download release package asset to user's Downloads directory."""
        target_dir = dest_dir or (Path.home() / "Downloads")
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / filename

        req = urllib.request.Request(
            asset_url,
            headers={"User-Agent": f"WineBox/{CURRENT_VERSION} (Linux)"},
        )
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            block_size = 65536
            with open(target_file, "wb") as f:
                while True:
                    chunk = resp.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total_size)
        return target_file
