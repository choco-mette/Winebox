"""Wine runner application service."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from winebox.common.exceptions import WineboxError
from winebox.domain.models import Runner
from winebox.infrastructure.fs_adapter import FilesystemAdapter
from winebox.infrastructure.runner_adapter import RunnerAdapter
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.interface.tui.utils import slugify


class RunnerService:
    """Manages system, external, and Winebox-managed Wine/Proton runners."""

    def __init__(self, repo: Optional[SqliteRepository] = None) -> None:
        self.repo = repo or SqliteRepository()

    def list_runners(self) -> List[Runner]:
        return self.repo.list_runners()

    def get_runner(self, runner_id: str) -> Runner:
        return self.repo.load_runner(runner_id)

    def register_custom_runner(
        self,
        runner_id: str,
        name: str,
        wine_bin: Path,
        wineserver_bin: Optional[Path] = None,
    ) -> Runner:
        resolved_wine = wine_bin.resolve()
        resolved_wineserver = wineserver_bin.resolve() if wineserver_bin else None

        runner = Runner(
            id=runner_id,
            name=name,
            wine_bin=resolved_wine,
            wineserver_bin=resolved_wineserver,
            is_system=False,
        )
        self.repo.save_runner(runner)
        return runner

    @staticmethod
    def list_sources() -> Dict[str, Dict[str, str]]:
        return RunnerAdapter.get_sources()

    @staticmethod
    def fetch_available_releases(source_key: str, limit: int = 10) -> List[Dict[str, str]]:
        return RunnerAdapter.fetch_releases(source_key, limit=limit)

    def install_runner(
        self,
        source_key: str,
        version: Optional[str] = None,
        share: bool = False,
        xdg_data_home: Optional[Path] = None,
    ) -> Tuple[Runner, Optional[Path]]:
        releases = self.fetch_available_releases(source_key, limit=50)
        if not releases:
            raise WineboxError(f"No downloadable releases found for source '{source_key}'.")

        if version:
            release = next((r for r in releases if r["version"] == version), None)
            if not release:
                raise WineboxError(f"Version '{version}' not found for source '{source_key}'.")
        else:
            release = releases[0]

        raw_ver = release["version"]
        base_slug = raw_ver if source_key in raw_ver.lower() else f"{source_key}-{raw_ver}"
        runner_id = slugify(base_slug)
        dest_dir = self.repo.runners_dir / runner_id
        if dest_dir.exists():
            raise WineboxError(f"Runner '{runner_id}' is already installed at {dest_dir}.")

        cache_dir = self.repo.data_root / "cache" / "runners"
        archive_path = RunnerAdapter.download_tarball(release["url"], cache_dir, release["filename"])

        try:
            RunnerAdapter.safe_extract_tar(archive_path, dest_dir)
            wine_bin, wineserver_bin = RunnerAdapter.detect_wine_binaries(dest_dir)
        except Exception:
            FilesystemAdapter.remove_tree(dest_dir)
            raise

        runner = self.register_custom_runner(
            runner_id=runner_id,
            name=f"{source_key} {raw_ver}",
            wine_bin=wine_bin,
            wineserver_bin=wineserver_bin,
        )

        shared_link: Optional[Path] = None
        if share:
            shared_link = RunnerAdapter.create_shared_symlink(
                dest_dir, release["kind"], xdg_data_home=xdg_data_home
            )
        return runner, shared_link

    def share_runner(self, runner_id: str, xdg_data_home: Optional[Path] = None) -> Path:
        runner = self.get_runner(runner_id)
        if runner.is_system:
            raise WineboxError("Cannot share the system Wine runner.")

        parent_dir = runner.wine_bin.parent.parent
        if parent_dir.name in ("files", "dist"):
            kind = "proton"
            runner_dir = parent_dir.parent
        else:
            kind = "wine"
            runner_dir = parent_dir

        return RunnerAdapter.create_shared_symlink(runner_dir, kind, xdg_data_home=xdg_data_home)

    def scan_external_runners(self, xdg_data_home: Optional[Path] = None) -> List[Runner]:
        existing_ids = {r.id for r in self.list_runners()}
        discovered = RunnerAdapter.scan_external_runners(xdg_data_home=xdg_data_home)
        added: List[Runner] = []
        for item in discovered:
            if item["id"] in existing_ids:
                continue
            runner = self.register_custom_runner(
                runner_id=item["id"],
                name=item["name"],
                wine_bin=item["wine_bin"],
                wineserver_bin=item["wineserver_bin"],
            )
            existing_ids.add(runner.id)
            added.append(runner)
        return added

    def remove_runner(
        self,
        runner_id: str,
        delete_files: bool = True,
        xdg_data_home: Optional[Path] = None,
    ) -> None:
        self.get_runner(runner_id)
        self.repo.delete_runner(runner_id)
        RunnerAdapter.remove_shared_symlinks(runner_id, xdg_data_home=xdg_data_home)

        if delete_files:
            runners_root = self.repo.runners_dir.resolve()
            runner_dir = (runners_root / runner_id).resolve()
            if runner_dir.exists() and runner_dir != runners_root and runner_dir.is_relative_to(runners_root):
                FilesystemAdapter.remove_tree(runner_dir)
