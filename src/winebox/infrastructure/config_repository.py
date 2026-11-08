"""Configuration and storage repository implementing XDG Base Directory layout."""

import os
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from winebox.common.exceptions import ResourceNotFoundError
from winebox.domain.models import (
    Application,
    AppStatus,
    HostMount,
    MountMode,
    Prefix,
    PrefixOrigin,
    PrefixStatus,
    Runner,
    SecurityPolicy,
)


class ConfigRepository:
    """Manages reading and writing TOML configuration files in XDG directories."""

    def __init__(self, data_root: Optional[Path] = None, config_root: Optional[Path] = None) -> None:
        if data_root:
            self.data_root = data_root.resolve()
        else:
            xdg_data = os.environ.get("XDG_DATA_HOME")
            self.data_root = (Path(xdg_data) if xdg_data else Path.home() / ".local" / "share") / "winebox"

        if config_root:
            self.config_root = config_root.resolve()
        else:
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            self.config_root = (Path(xdg_config) if xdg_config else Path.home() / ".config") / "winebox"

        self.apps_dir = self.data_root / "applications"
        self.prefixes_dir = self.data_root / "prefixes"
        self.runners_dir = self.data_root / "runners"
        self.staging_dir = self.data_root / "staging"

        # Ensure directory structure exists
        for d in (self.apps_dir, self.prefixes_dir, self.runners_dir, self.staging_dir, self.config_root):
            d.mkdir(parents=True, exist_ok=True)

    # ---------------- Application CRUD ----------------
    def save_app(self, app: Application) -> None:
        file_path = self.apps_dir / f"{app.id}.toml"
        content = [
            "[application]",
            f'id = "{app.id}"',
            f'name = "{app.name}"',
            f'prefix_id = "{app.prefix_id}"',
            f'exe_path = "{app.exe_path}"',
            f'runner_id = "{app.runner_id}"',
            f'status = "{app.status.value}"',
            f'created_at = "{app.created_at.isoformat()}"',
            "",
            "[arguments]",
            f"default_args = {app.arguments!r}",
            "",
            "[policy]",
            f"display = {str(app.policy.display).lower()}",
            f"audio = {str(app.policy.audio).lower()}",
            f"network = {str(app.policy.network).lower()}",
            f"gpu = {str(app.policy.gpu).lower()}",
            "",
            "[environment]",
        ]
        for k, v in app.policy.env_vars.items():
            content.append(f'{k} = "{v}"')

        for mount in app.policy.host_mounts:
            content.extend([
                "",
                "[[policy.host_mounts]]",
                f'host_path = "{mount.host_path}"',
                f'sandbox_path = "{mount.sandbox_path}"',
                f'mode = "{mount.mode.value}"',
            ])

        file_path.write_text("\n".join(content) + "\n", encoding="utf-8")

    def load_app(self, app_id: str) -> Application:
        file_path = self.apps_dir / f"{app_id}.toml"
        if not file_path.exists():
            raise ResourceNotFoundError(f"Application '{app_id}' not found")

        with open(file_path, "rb") as f:
            data = tomllib.load(f)

        app_info = data.get("application", {})
        policy_info = data.get("policy", {})

        mounts = []
        for m in policy_info.get("host_mounts", []):
            mounts.append(
                HostMount(
                    host_path=Path(m["host_path"]),
                    sandbox_path=Path(m["sandbox_path"]),
                    mode=MountMode(m.get("mode", "ro")),
                )
            )

        policy = SecurityPolicy(
            display=policy_info.get("display", True),
            audio=policy_info.get("audio", True),
            network=policy_info.get("network", True),
            gpu=policy_info.get("gpu", True),
            host_mounts=mounts,
            env_vars=data.get("environment", {}),
        )

        created_str = app_info.get("created_at")
        created_at = datetime.fromisoformat(created_str) if created_str else datetime.now(timezone.utc)

        return Application(
            id=app_info.get("id", app_id),
            name=app_info.get("name", app_id),
            prefix_id=app_info.get("prefix_id", "default"),
            exe_path=app_info.get("exe_path", ""),
            runner_id=app_info.get("runner_id", "system-wine"),
            arguments=data.get("arguments", {}).get("default_args", []),
            policy=policy,
            status=AppStatus(app_info.get("status", "ready")),
            created_at=created_at,
        )

    def list_apps(self) -> List[Application]:
        apps = []
        for f in sorted(self.apps_dir.glob("*.toml")):
            try:
                apps.append(self.load_app(f.stem))
            except Exception:
                pass
        return apps

    def delete_app(self, app_id: str) -> None:
        file_path = self.apps_dir / f"{app_id}.toml"
        if not file_path.exists():
            raise ResourceNotFoundError(f"Application '{app_id}' not found")
        file_path.unlink()

    # ---------------- Prefix CRUD ----------------
    def get_prefix_dir(self, prefix_id: str) -> Path:
        return self.prefixes_dir / prefix_id

    def save_prefix(self, prefix: Prefix) -> None:
        p_dir = self.get_prefix_dir(prefix.id)
        p_dir.mkdir(parents=True, exist_ok=True)
        file_path = p_dir / "config.toml"
        content = [
            "[prefix]",
            f'id = "{prefix.id}"',
            f'name = "{prefix.name}"',
            f'origin = "{prefix.origin.value}"',
            f'status = "{prefix.status.value}"',
            f'created_at = "{prefix.created_at.isoformat()}"',
            "",
            "[runner]",
            f'id = "{prefix.runner_id}"',
        ]
        file_path.write_text("\n".join(content) + "\n", encoding="utf-8")

    def load_prefix(self, prefix_id: str) -> Prefix:
        file_path = self.get_prefix_dir(prefix_id) / "config.toml"
        if not file_path.exists():
            raise ResourceNotFoundError(f"Prefix '{prefix_id}' not found")

        with open(file_path, "rb") as f:
            data = tomllib.load(f)

        p_info = data.get("prefix", {})
        created_str = p_info.get("created_at")
        created_at = datetime.fromisoformat(created_str) if created_str else datetime.now(timezone.utc)

        return Prefix(
            id=p_info.get("id", prefix_id),
            name=p_info.get("name", prefix_id),
            runner_id=data.get("runner", {}).get("id", "system-wine"),
            origin=PrefixOrigin(p_info.get("origin", "created")),
            status=PrefixStatus(p_info.get("status", "ready")),
            created_at=created_at,
        )

    def list_prefixes(self) -> List[Prefix]:
        prefixes = []
        for d in sorted(self.prefixes_dir.iterdir()):
            if d.is_dir() and (d / "config.toml").exists():
                try:
                    prefixes.append(self.load_prefix(d.name))
                except Exception:
                    pass
        return prefixes

    def delete_prefix(self, prefix_id: str) -> None:
        p_dir = self.get_prefix_dir(prefix_id)
        if not p_dir.exists():
            raise ResourceNotFoundError(f"Prefix '{prefix_id}' not found")
        import shutil
        shutil.rmtree(p_dir)

    # ---------------- Runner CRUD ----------------
    def save_runner(self, runner: Runner) -> None:
        file_path = self.runners_dir / f"{runner.id}.toml"
        content = [
            "[runner]",
            f'id = "{runner.id}"',
            f'name = "{runner.name}"',
            f"is_system = {str(runner.is_system).lower()}",
            f'wine_bin = "{runner.wine_bin}"',
        ]
        if runner.wineserver_bin:
            content.append(f'wineserver_bin = "{runner.wineserver_bin}"')

        file_path.write_text("\n".join(content) + "\n", encoding="utf-8")

    def load_runner(self, runner_id: str) -> Runner:
        if runner_id == "system-wine":
            import shutil
            wine_path = shutil.which("wine") or "/usr/bin/wine"
            wineserver_path = shutil.which("wineserver")
            return Runner(
                id="system-wine",
                name="System Wine",
                wine_bin=Path(wine_path),
                wineserver_bin=Path(wineserver_path) if wineserver_path else None,
                is_system=True,
            )

        file_path = self.runners_dir / f"{runner_id}.toml"
        if not file_path.exists():
            raise ResourceNotFoundError(f"Runner '{runner_id}' not found")

        with open(file_path, "rb") as f:
            data = tomllib.load(f)

        r_info = data.get("runner", {})
        wineserver = r_info.get("wineserver_bin")
        return Runner(
            id=r_info.get("id", runner_id),
            name=r_info.get("name", runner_id),
            wine_bin=Path(r_info.get("wine_bin", "/usr/bin/wine")),
            wineserver_bin=Path(wineserver) if wineserver else None,
            is_system=r_info.get("is_system", False),
        )

    def list_runners(self) -> List[Runner]:
        runners = [self.load_runner("system-wine")]
        for f in sorted(self.runners_dir.glob("*.toml")):
            try:
                runners.append(self.load_runner(f.stem))
            except Exception:
                pass
        return runners

