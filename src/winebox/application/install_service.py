"""Installation service for executing Windows installers in sandbox."""

from pathlib import Path
from typing import List, Optional
from winebox.common.exceptions import WineboxError
from winebox.domain.models import HostMount, MountMode, SecurityPolicy
from winebox.infrastructure.bwrap_adapter import BwrapAdapter
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.infrastructure.process_manager import prefix_lock
from winebox.infrastructure.wine_adapter import WineAdapter
from winebox.security.auditor import PrefixAuditor
from winebox.security.mount_builder import MountBuilder


class InstallService:
    """Manages sandboxed execution of Windows installers (.exe and .msi)."""

    def __init__(
        self,
        repo: Optional[SqliteRepository] = None,
        bwrap_adapter: Optional[BwrapAdapter] = None,
    ) -> None:
        self.repo = repo or SqliteRepository()
        self.bwrap_adapter = bwrap_adapter or BwrapAdapter()

    def scan_for_executables(self, prefix_inner: Path) -> List[str]:
        """Scans drive_c for recently installed .exe files."""
        drive_c = prefix_inner / "drive_c"
        candidates = []
        if not drive_c.exists():
            return candidates

        for exe in drive_c.rglob("*.exe"):
            try:
                rel = exe.relative_to(prefix_inner)
                # Ignore system executables in windows/
                if "windows" not in rel.parts[1].lower():
                    candidates.append(str(rel))
            except ValueError:
                pass
        return sorted(candidates)

    def run_installer(
        self,
        installer_path: Path,
        prefix_id: str,
        runner_id: str = "system-wine",
        policy: Optional[SecurityPolicy] = None,
    ) -> List[str]:
        """Executes installer in sandbox with installer mounted read-only."""
        resolved_installer = installer_path.resolve()
        if not resolved_installer.exists():
            raise WineboxError(f"Installer not found: {resolved_installer}")

        prefix = self.repo.load_prefix(prefix_id)
        runner = self.repo.load_runner(runner_id)

        p_dir = self.repo.get_prefix_dir(prefix.id)
        prefix_inner = p_dir / "prefix"
        home_inner = p_dir / "home"

        installer_dir = resolved_installer.parent
        sandbox_installer_dir = Path("/mnt/installer")
        sandbox_installer_file = sandbox_installer_dir / resolved_installer.name

        installer_mount = HostMount(
            host_path=installer_dir,
            sandbox_path=sandbox_installer_dir,
            mode=MountMode.RO,
        )

        installer_policy = policy or SecurityPolicy(network=True)
        # Add installer dir read-only mount
        installer_policy.host_mounts.append(installer_mount)

        with prefix_lock(p_dir):
            builder = MountBuilder(
                prefix_path=prefix_inner,
                isolated_home_path=home_inner,
                policy=installer_policy,
                custom_runner_dir=runner.wine_bin.parent.parent if not runner.is_system else None,
            )
            bwrap_args = builder.build_bwrap_args()
            installer_cmd = WineAdapter.build_installer_cmd(
                installer_path=str(sandbox_installer_file),
                runner=runner,
            )

            try:
                self.bwrap_adapter.execute_in_sandbox(
                    bwrap_args=bwrap_args,
                    command_inside=installer_cmd,
                    inherit_stdio=True,
                )
            finally:
                # Sanitize prefix after installer completes
                PrefixAuditor.sanitize_dosdevices(prefix_inner)

            # Find newly installed executables
            return self.scan_for_executables(prefix_inner)

