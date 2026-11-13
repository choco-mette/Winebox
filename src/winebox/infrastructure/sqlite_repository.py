"""SQLite configuration repository implementing ADR-020."""

import json
import os
import sqlite3
import tomllib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Generator, List, Optional
from winebox.common.exceptions import ResourceNotFoundError, WineboxError
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
    SecurityProfile,
)


class SqliteRepository:
    """Manages centralized SQLite configuration storage with WAL mode and local snapshots."""

    SCHEMA_VERSION = 1

    DEFAULT_PROFILES = [
        SecurityProfile(
            id="paranoid",
            name="Paranoid (Ultra-Isolated)",
            is_builtin=True,
            display=False,
            audio=False,
            network=False,
            gpu=False,
            description="Headless CLI execution with all hardware and network disabled.",
        ),
        SecurityProfile(
            id="zero-trust",
            name="Zero-Trust (Offline)",
            is_builtin=True,
            display=True,
            audio=False,
            network=False,
            gpu=False,
            description="Display GUI enabled. Audio, network, and GPU blocked.",
        ),
        SecurityProfile(
            id="balanced",
            name="Balanced (Standard Desktop)",
            is_builtin=True,
            display=True,
            audio=True,
            network=False,
            gpu=False,
            description="Display and audio enabled. Network blocked, CPU rendering.",
        ),
        SecurityProfile(
            id="permissive",
            name="Permissive (Full Hardware / Gaming)",
            is_builtin=True,
            display=True,
            audio=True,
            network=True,
            gpu=True,
            description="Display, audio, network, and GPU DRI acceleration enabled.",
        ),
    ]

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

        self.prefixes_dir = self.data_root / "prefixes"
        self.runners_dir = self.data_root / "runners"
        self.staging_dir = self.data_root / "staging"
        self.apps_dir = self.data_root / "applications"

        for d in (self.prefixes_dir, self.runners_dir, self.staging_dir, self.apps_dir, self.config_root):
            d.mkdir(parents=True, exist_ok=True)

        self.db_path = self.data_root / "winebox.db"
        self._init_database()
        self._auto_import_legacy_toml()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_database(self) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS security_profiles (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    is_builtin INTEGER NOT NULL DEFAULT 0,
                    display INTEGER NOT NULL DEFAULT 1,
                    audio INTEGER NOT NULL DEFAULT 1,
                    network INTEGER NOT NULL DEFAULT 1,
                    gpu INTEGER NOT NULL DEFAULT 1,
                    description TEXT DEFAULT ''
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS prefixes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    runner_id TEXT NOT NULL DEFAULT 'system-wine',
                    default_profile_id TEXT NOT NULL REFERENCES security_profiles(id) ON DELETE RESTRICT,
                    origin TEXT NOT NULL DEFAULT 'created',
                    status TEXT NOT NULL DEFAULT 'ready',
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    prefix_id TEXT NOT NULL REFERENCES prefixes(id) ON DELETE CASCADE,
                    exe_path TEXT NOT NULL,
                    runner_id TEXT NOT NULL DEFAULT 'system-wine',
                    profile_id TEXT NOT NULL REFERENCES security_profiles(id) ON DELETE RESTRICT,
                    default_args TEXT DEFAULT '[]',
                    last_run_at TEXT,
                    last_exit_code INTEGER,
                    status TEXT NOT NULL DEFAULT 'ready',
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_host_mounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                    host_path TEXT NOT NULL,
                    sandbox_path TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT 'ro'
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_env_vars (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runners (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    wine_bin TEXT NOT NULL,
                    wineserver_bin TEXT,
                    is_system INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION};")

            # Seed default profiles if empty
            cursor = conn.execute("SELECT COUNT(*) FROM security_profiles")
            if cursor.fetchone()[0] == 0:
                for p in self.DEFAULT_PROFILES:
                    conn.execute(
                        """
                        INSERT INTO security_profiles (id, name, is_builtin, display, audio, network, gpu, description)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (p.id, p.name, 1 if p.is_builtin else 0, int(p.display), int(p.audio), int(p.network), int(p.gpu), p.description),
                    )

    def _auto_import_legacy_toml(self) -> None:
        """Auto-imports existing legacy TOML prefixes and applications into SQLite."""
        with self.get_connection() as conn:
            prefix_count = conn.execute("SELECT COUNT(*) FROM prefixes").fetchone()[0]
            if prefix_count > 0:
                return

        # Scan prefixes
        for p_dir in sorted(self.prefixes_dir.iterdir()):
            if p_dir.is_dir():
                conf = p_dir / "config.toml"
                if conf.exists():
                    try:
                        with open(conf, "rb") as f:
                            data = tomllib.load(f)
                        p_info = data.get("prefix", {})
                        prefix = Prefix(
                            id=p_info.get("id", p_dir.name),
                            name=p_info.get("name", p_dir.name),
                            runner_id=data.get("runner", {}).get("id", "system-wine"),
                            origin=PrefixOrigin(p_info.get("origin", "created")),
                            status=PrefixStatus(p_info.get("status", "ready")),
                            created_at=datetime.fromisoformat(p_info.get("created_at", datetime.now(timezone.utc).isoformat())),
                        )
                        self.save_prefix(prefix)
                    except Exception:
                        pass

        # Scan apps
        if self.apps_dir.exists():
            for app_file in sorted(self.apps_dir.glob("*.toml")):
                try:
                    with open(app_file, "rb") as f:
                        data = tomllib.load(f)
                    app_info = data.get("application", {})
                    pol_info = data.get("policy", {})
                    # Map legacy boolean policy to best matching profile
                    profile_id = "permissive" if pol_info.get("network", True) else "balanced"
                    app = Application(
                        id=app_info.get("id", app_file.stem),
                        name=app_info.get("name", app_file.stem),
                        prefix_id=app_info.get("prefix_id", "default"),
                        exe_path=app_info.get("exe_path", ""),
                        runner_id=app_info.get("runner_id", "system-wine"),
                        profile_id=profile_id,
                        arguments=data.get("arguments", {}).get("default_args", []),
                        status=AppStatus(app_info.get("status", "ready")),
                    )
                    self.save_app(app)
                except Exception:
                    pass

    # ---------------- Security Profile CRUD ----------------
    def save_profile(self, profile: SecurityProfile) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO security_profiles (id, name, is_builtin, display, audio, network, gpu, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    display = excluded.display,
                    audio = excluded.audio,
                    network = excluded.network,
                    gpu = excluded.gpu,
                    description = excluded.description;
                """,
                (
                    profile.id,
                    profile.name,
                    1 if profile.is_builtin else 0,
                    int(profile.display),
                    int(profile.audio),
                    int(profile.network),
                    int(profile.gpu),
                    profile.description,
                ),
            )

    def load_profile(self, profile_id: str) -> SecurityProfile:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM security_profiles WHERE id = ?", (profile_id,)).fetchone()
            if not row:
                raise ResourceNotFoundError(f"Security Profile '{profile_id}' not found")
            return SecurityProfile(
                id=row["id"],
                name=row["name"],
                is_builtin=bool(row["is_builtin"]),
                display=bool(row["display"]),
                audio=bool(row["audio"]),
                network=bool(row["network"]),
                gpu=bool(row["gpu"]),
                description=row["description"] or "",
            )

    def list_profiles(self) -> List[SecurityProfile]:
        profiles = []
        with self.get_connection() as conn:
            for row in conn.execute("SELECT * FROM security_profiles ORDER BY is_builtin DESC, id ASC").fetchall():
                profiles.append(
                    SecurityProfile(
                        id=row["id"],
                        name=row["name"],
                        is_builtin=bool(row["is_builtin"]),
                        display=bool(row["display"]),
                        audio=bool(row["audio"]),
                        network=bool(row["network"]),
                        gpu=bool(row["gpu"]),
                        description=row["description"] or "",
                    )
                )
        return profiles

    def delete_profile(self, profile_id: str) -> None:
        prof = self.load_profile(profile_id)
        if prof.is_builtin:
            raise WineboxError(f"Cannot delete built-in security profile '{profile_id}'")

        try:
            with self.get_connection() as conn:
                conn.execute("DELETE FROM security_profiles WHERE id = ?", (profile_id,))
        except sqlite3.IntegrityError as e:
            raise WineboxError(
                f"Cannot delete profile '{profile_id}': it is currently used by active prefixes or applications"
            ) from e

    # ---------------- Prefix CRUD ----------------
    def get_prefix_dir(self, prefix_id: str) -> Path:
        return self.prefixes_dir / prefix_id

    def save_prefix(self, prefix: Prefix) -> None:
        p_dir = self.get_prefix_dir(prefix.id)
        p_dir.mkdir(parents=True, exist_ok=True)

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO prefixes (id, name, runner_id, default_profile_id, origin, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    runner_id = excluded.runner_id,
                    default_profile_id = excluded.default_profile_id,
                    status = excluded.status;
                """,
                (
                    prefix.id,
                    prefix.name,
                    prefix.runner_id,
                    prefix.default_profile_id,
                    prefix.origin.value,
                    prefix.status.value,
                    prefix.created_at.isoformat(),
                ),
            )
        self.sync_prefix_snapshot(prefix.id)

    def load_prefix(self, prefix_id: str) -> Prefix:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM prefixes WHERE id = ?", (prefix_id,)).fetchone()
            if not row:
                raise ResourceNotFoundError(f"Prefix '{prefix_id}' not found")
            return Prefix(
                id=row["id"],
                name=row["name"],
                runner_id=row["runner_id"],
                default_profile_id=row["default_profile_id"],
                origin=PrefixOrigin(row["origin"]),
                status=PrefixStatus(row["status"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )

    def list_prefixes(self) -> List[Prefix]:
        prefixes = []
        with self.get_connection() as conn:
            for row in conn.execute("SELECT * FROM prefixes ORDER BY id ASC").fetchall():
                prefixes.append(
                    Prefix(
                        id=row["id"],
                        name=row["name"],
                        runner_id=row["runner_id"],
                        default_profile_id=row["default_profile_id"],
                        origin=PrefixOrigin(row["origin"]),
                        status=PrefixStatus(row["status"]),
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                )
        return prefixes

    def delete_prefix(self, prefix_id: str) -> None:
        p_dir = self.get_prefix_dir(prefix_id)
        with self.get_connection() as conn:
            conn.execute("DELETE FROM prefixes WHERE id = ?", (prefix_id,))

        if p_dir.exists():
            import shutil
            shutil.rmtree(p_dir)

    # ---------------- Application CRUD ----------------
    def save_app(self, app: Application) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO applications (id, name, prefix_id, exe_path, runner_id, profile_id, default_args, last_run_at, last_exit_code, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    prefix_id = excluded.prefix_id,
                    exe_path = excluded.exe_path,
                    runner_id = excluded.runner_id,
                    profile_id = excluded.profile_id,
                    default_args = excluded.default_args,
                    last_run_at = excluded.last_run_at,
                    last_exit_code = excluded.last_exit_code,
                    status = excluded.status;
                """,
                (
                    app.id,
                    app.name,
                    app.prefix_id,
                    app.exe_path,
                    app.runner_id,
                    app.profile_id,
                    json.dumps(app.arguments),
                    app.last_run_at.isoformat() if app.last_run_at else None,
                    app.last_exit_code,
                    app.status.value,
                    app.created_at.isoformat(),
                ),
            )

            # Update mounts & env vars
            conn.execute("DELETE FROM app_host_mounts WHERE app_id = ?", (app.id,))
            for m in app.policy.host_mounts:
                conn.execute(
                    "INSERT INTO app_host_mounts (app_id, host_path, sandbox_path, mode) VALUES (?, ?, ?, ?)",
                    (app.id, str(m.host_path), str(m.sandbox_path), m.mode.value),
                )

            conn.execute("DELETE FROM app_env_vars WHERE app_id = ?", (app.id,))
            for k, v in app.policy.env_vars.items():
                conn.execute(
                    "INSERT INTO app_env_vars (app_id, key, value) VALUES (?, ?, ?)",
                    (app.id, k, v),
                )

        self.sync_prefix_snapshot(app.prefix_id)

    def update_app_last_run(self, app_id: str, exit_code: int) -> None:
        now_str = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE applications SET last_run_at = ?, last_exit_code = ? WHERE id = ?",
                (now_str, exit_code, app_id),
            )

    def load_app(self, app_id: str) -> Application:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
            if not row:
                raise ResourceNotFoundError(f"Application '{app_id}' not found")

            # Load profile
            prof = self.load_profile(row["profile_id"])

            # Load mounts
            mounts = []
            for m_row in conn.execute("SELECT * FROM app_host_mounts WHERE app_id = ?", (app_id,)).fetchall():
                mounts.append(
                    HostMount(
                        host_path=Path(m_row["host_path"]),
                        sandbox_path=Path(m_row["sandbox_path"]),
                        mode=MountMode(m_row["mode"]),
                    )
                )

            # Load env vars
            env_vars = {}
            for e_row in conn.execute("SELECT * FROM app_env_vars WHERE app_id = ?", (app_id,)).fetchall():
                env_vars[e_row["key"]] = e_row["value"]

            policy = prof.to_policy(host_mounts=mounts, env_vars=env_vars)
            last_run = datetime.fromisoformat(row["last_run_at"]) if row["last_run_at"] else None

            return Application(
                id=row["id"],
                name=row["name"],
                prefix_id=row["prefix_id"],
                exe_path=row["exe_path"],
                runner_id=row["runner_id"],
                profile_id=row["profile_id"],
                arguments=json.loads(row["default_args"] or "[]"),
                policy=policy,
                status=AppStatus(row["status"]),
                last_run_at=last_run,
                last_exit_code=row["last_exit_code"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )

    def list_apps(self) -> List[Application]:
        apps = []
        with self.get_connection() as conn:
            for row in conn.execute("SELECT id FROM applications ORDER BY id ASC").fetchall():
                try:
                    apps.append(self.load_app(row["id"]))
                except Exception:
                    pass
        return apps

    def delete_app(self, app_id: str) -> None:
        app = self.load_app(app_id)
        with self.get_connection() as conn:
            conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        self.sync_prefix_snapshot(app.prefix_id)

    # ---------------- Runner CRUD ----------------
    def save_runner(self, runner: Runner) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO runners (id, name, wine_bin, wineserver_bin, is_system, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    wine_bin = excluded.wine_bin,
                    wineserver_bin = excluded.wineserver_bin,
                    is_system = excluded.is_system;
                """,
                (
                    runner.id,
                    runner.name,
                    str(runner.wine_bin),
                    str(runner.wineserver_bin) if runner.wineserver_bin else None,
                    1 if runner.is_system else 0,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

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

        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM runners WHERE id = ?", (runner_id,)).fetchone()
            if not row:
                raise ResourceNotFoundError(f"Runner '{runner_id}' not found")
            return Runner(
                id=row["id"],
                name=row["name"],
                wine_bin=Path(row["wine_bin"]),
                wineserver_bin=Path(row["wineserver_bin"]) if row["wineserver_bin"] else None,
                is_system=bool(row["is_system"]),
            )

    def list_runners(self) -> List[Runner]:
        runners = [self.load_runner("system-wine")]
        with self.get_connection() as conn:
            for row in conn.execute("SELECT id FROM runners WHERE id != 'system-wine' ORDER BY id ASC").fetchall():
                try:
                    runners.append(self.load_runner(row["id"]))
                except Exception:
                    pass
        return runners

    # ---------------- Snapshot Synchronization ----------------
    def sync_prefix_snapshot(self, prefix_id: str) -> None:
        """Writes a localized metadata.json snapshot inside prefixes/<id>/ for disaster recovery."""
        p_dir = self.get_prefix_dir(prefix_id)
        if not p_dir.exists():
            return

        try:
            prefix = self.load_prefix(prefix_id)
            with self.get_connection() as conn:
                app_rows = conn.execute(
                    "SELECT id, name, exe_path, profile_id FROM applications WHERE prefix_id = ?",
                    (prefix_id,),
                ).fetchall()

            apps_data = [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "exe_path": r["exe_path"],
                    "profile_id": r["profile_id"],
                }
                for r in app_rows
            ]

            snapshot = {
                "prefix": {
                    "id": prefix.id,
                    "name": prefix.name,
                    "runner_id": prefix.runner_id,
                    "default_profile_id": prefix.default_profile_id,
                    "origin": prefix.origin.value,
                    "created_at": prefix.created_at.isoformat(),
                },
                "applications": apps_data,
                "synced_at": datetime.now(timezone.utc).isoformat(),
            }

            snap_file = p_dir / "metadata.json"
            snap_file.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        except Exception:
            # Snapshot sync failure should never crash core operations
            pass
