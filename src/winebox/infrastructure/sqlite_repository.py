"""SQLite configuration repository implementing ADR-020."""

import json
import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, List, Optional
from winebox.common.exceptions import ResourceNotFoundError, WineboxError
from winebox.domain.models import (
    AppGroup,
    Application,
    AppStatus,
    HostMount,
    MountMode,
    Prefix,
    PrefixOrigin,
    PrefixStatus,
    Runner,
    SecurityProfile,
    ShortcutSettings,
)
from winebox.infrastructure.db_schema import DEFAULT_PROFILES, SCHEMA_VERSION, init_database_schema
from winebox.infrastructure.db_sync import import_legacy_toml_if_needed, write_prefix_snapshot


class SqliteRepository:
    """Manages centralized SQLite configuration storage with WAL mode and local snapshots."""

    SCHEMA_VERSION = SCHEMA_VERSION
    DEFAULT_PROFILES = DEFAULT_PROFILES

    def __init__(self, data_root: Optional[Path] = None, config_root: Optional[Path] = None) -> None:
        xdg_data = os.environ.get("XDG_DATA_HOME")
        self.data_root = data_root.resolve() if data_root else (Path(xdg_data) if xdg_data else Path.home() / ".local" / "share") / "winebox"

        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        self.config_root = config_root.resolve() if config_root else (Path(xdg_config) if xdg_config else Path.home() / ".config") / "winebox"

        self.prefixes_dir = self.data_root / "prefixes"
        self.runners_dir = self.data_root / "runners"
        self.staging_dir = self.data_root / "staging"
        self.apps_dir = self.data_root / "applications"

        for d in (self.prefixes_dir, self.runners_dir, self.staging_dir, self.apps_dir, self.config_root):
            d.mkdir(parents=True, exist_ok=True)

        self.db_path = self.data_root / "winebox.db"
        with self.get_connection() as conn:
            init_database_schema(conn)
        import_legacy_toml_if_needed(self)

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

    # ---------------- Security Profile CRUD ----------------
    def save_profile(self, profile: SecurityProfile) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO security_profiles (id, name, is_builtin, display, audio, network, gpu, gamepad, hidraw, mic, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name, display = excluded.display, audio = excluded.audio,
                    network = excluded.network, gpu = excluded.gpu, gamepad = excluded.gamepad,
                    hidraw = excluded.hidraw, mic = excluded.mic, description = excluded.description;
                """,
                (
                    profile.id, profile.name, int(profile.is_builtin), int(profile.display),
                    int(profile.audio), int(profile.network), int(profile.gpu),
                    int(profile.gamepad), int(profile.hidraw), int(profile.mic), profile.description,
                ),
            )

    @staticmethod
    def _row_to_profile(row: sqlite3.Row) -> SecurityProfile:
        return SecurityProfile(
            id=row["id"], name=row["name"], is_builtin=bool(row["is_builtin"]),
            display=bool(row["display"]), audio=bool(row["audio"]),
            network=bool(row["network"]), gpu=bool(row["gpu"]),
            gamepad=bool(row["gamepad"]), hidraw=bool(row["hidraw"]), mic=bool(row["mic"]),
            description=row["description"] or "",
        )

    def load_profile(self, profile_id: str) -> SecurityProfile:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM security_profiles WHERE id = ?", (profile_id,)).fetchone()
            if not row:
                raise ResourceNotFoundError(f"Security Profile '{profile_id}' not found")
            return self._row_to_profile(row)

    def list_profiles(self) -> List[SecurityProfile]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM security_profiles ORDER BY is_builtin DESC, id ASC").fetchall()
            return [self._row_to_profile(r) for r in rows]

    def delete_profile(self, profile_id: str) -> None:
        prof = self.load_profile(profile_id)
        if prof.is_builtin:
            raise WineboxError(f"Cannot delete built-in security profile '{profile_id}'")
        try:
            with self.get_connection() as conn:
                conn.execute("DELETE FROM security_profiles WHERE id = ?", (profile_id,))
        except sqlite3.IntegrityError as e:
            raise WineboxError(f"Cannot delete profile '{profile_id}': it is currently used by active prefixes or applications") from e

    # ---------------- Prefix CRUD ----------------
    def get_prefix_dir(self, prefix_id: str) -> Path:
        return self.prefixes_dir / prefix_id

    def save_prefix(self, prefix: Prefix) -> None:
        self.get_prefix_dir(prefix.id).mkdir(parents=True, exist_ok=True)
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO prefixes (id, name, runner_id, default_profile_id, origin, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name, runner_id = excluded.runner_id,
                    default_profile_id = excluded.default_profile_id, status = excluded.status;
                """,
                (prefix.id, prefix.name, prefix.runner_id, prefix.default_profile_id, prefix.origin.value, prefix.status.value, prefix.created_at.isoformat()),
            )
        self.sync_prefix_snapshot(prefix.id)

    @staticmethod
    def _row_to_prefix(row: sqlite3.Row) -> Prefix:
        return Prefix(
            id=row["id"], name=row["name"], runner_id=row["runner_id"],
            default_profile_id=row["default_profile_id"],
            origin=PrefixOrigin(row["origin"]), status=PrefixStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def load_prefix(self, prefix_id: str) -> Prefix:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM prefixes WHERE id = ?", (prefix_id,)).fetchone()
            if not row:
                raise ResourceNotFoundError(f"Prefix '{prefix_id}' not found")
            return self._row_to_prefix(row)

    def list_prefixes(self) -> List[Prefix]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM prefixes ORDER BY id ASC").fetchall()
            return [self._row_to_prefix(r) for r in rows]

    def delete_prefix(self, prefix_id: str) -> None:
        p_dir = self.get_prefix_dir(prefix_id)
        with self.get_connection() as conn:
            conn.execute("DELETE FROM prefixes WHERE id = ?", (prefix_id,))
        if p_dir.exists():
            shutil.rmtree(p_dir)

    # ---------------- Application CRUD ----------------
    def save_app(self, app: Application) -> None:
        shortcut_json = json.dumps(
            {
                "menu_enabled": app.shortcut.menu_enabled,
                "desktop_enabled": app.shortcut.desktop_enabled,
                "icon": app.shortcut.icon,
                "categories": app.shortcut.categories,
                "comment": app.shortcut.comment,
                "terminal": app.shortcut.terminal,
                "startup_wm_class": app.shortcut.startup_wm_class,
            }
        )
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO applications (id, name, prefix_id, exe_path, runner_id, profile_id, default_args, shortcut_config, last_run_at, last_exit_code, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name, prefix_id = excluded.prefix_id, exe_path = excluded.exe_path,
                    runner_id = excluded.runner_id, profile_id = excluded.profile_id,
                    default_args = excluded.default_args, shortcut_config = excluded.shortcut_config,
                    last_run_at = excluded.last_run_at, last_exit_code = excluded.last_exit_code,
                    status = excluded.status;
                """,
                (app.id, app.name, app.prefix_id, app.exe_path, app.runner_id, app.profile_id, json.dumps(app.arguments), shortcut_json, app.last_run_at.isoformat() if app.last_run_at else None, app.last_exit_code, app.status.value, app.created_at.isoformat()),
            )
            conn.execute("DELETE FROM app_host_mounts WHERE app_id = ?", (app.id,))
            for m in app.policy.host_mounts:
                conn.execute(
                    "INSERT INTO app_host_mounts (app_id, host_path, sandbox_path, mode) VALUES (?, ?, ?, ?)",
                    (app.id, str(m.host_path), str(m.sandbox_path), m.mode.value),
                )
            conn.execute("DELETE FROM app_env_vars WHERE app_id = ?", (app.id,))
            for k, v in app.policy.env_vars.items():
                conn.execute("INSERT INTO app_env_vars (app_id, key, value) VALUES (?, ?, ?)", (app.id, k, v))
            conn.execute("DELETE FROM app_groups WHERE app_id = ?", (app.id,))
            for gid in getattr(app, "groups", []):
                conn.execute("INSERT OR IGNORE INTO app_groups (app_id, group_id) VALUES (?, ?)", (app.id, gid))
        self.sync_prefix_snapshot(app.prefix_id)

    def update_app_last_run(self, app_id: str, exit_code: int) -> None:
        now_str = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute("UPDATE applications SET last_run_at = ?, last_exit_code = ? WHERE id = ?", (now_str, exit_code, app_id))

    def load_app(self, app_id: str) -> Application:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
            if not row:
                raise ResourceNotFoundError(f"Application '{app_id}' not found")
            prof = self.load_profile(row["profile_id"])
            mounts = [
                HostMount(host_path=Path(m["host_path"]), sandbox_path=Path(m["sandbox_path"]), mode=MountMode(m["mode"]))
                for m in conn.execute("SELECT * FROM app_host_mounts WHERE app_id = ?", (app_id,)).fetchall()
            ]
            env_vars = {e["key"]: e["value"] for e in conn.execute("SELECT * FROM app_env_vars WHERE app_id = ?", (app_id,)).fetchall()}
            policy = prof.to_policy(host_mounts=mounts, env_vars=env_vars)
            g_rows = conn.execute("SELECT group_id FROM app_groups WHERE app_id = ?", (app_id,)).fetchall()
            assigned_groups = [g["group_id"] for g in g_rows]
            raw_sc = json.loads(row["shortcut_config"] or "{}") if "shortcut_config" in row.keys() else {}
            shortcut = ShortcutSettings(
                menu_enabled=bool(raw_sc.get("menu_enabled", False)),
                desktop_enabled=bool(raw_sc.get("desktop_enabled", False)),
                icon=str(raw_sc.get("icon", "")),
                categories=str(raw_sc.get("categories", "Game;Utility;")),
                comment=str(raw_sc.get("comment", "")),
                terminal=bool(raw_sc.get("terminal", False)),
                startup_wm_class=str(raw_sc.get("startup_wm_class", "")),
            )
            return Application(
                id=row["id"], name=row["name"], prefix_id=row["prefix_id"],
                exe_path=row["exe_path"], runner_id=row["runner_id"], profile_id=row["profile_id"],
                arguments=json.loads(row["default_args"] or "[]"), policy=policy,
                shortcut=shortcut,
                groups=assigned_groups,
                status=AppStatus(row["status"]),
                last_run_at=datetime.fromisoformat(row["last_run_at"]) if row["last_run_at"] else None,
                last_exit_code=row["last_exit_code"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )

    def list_apps(self) -> List[Application]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT id FROM applications ORDER BY id ASC").fetchall()
        apps = []
        for r in rows:
            try:
                apps.append(self.load_app(r["id"]))
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
                    name = excluded.name, wine_bin = excluded.wine_bin,
                    wineserver_bin = excluded.wineserver_bin, is_system = excluded.is_system;
                """,
                (runner.id, runner.name, str(runner.wine_bin), str(runner.wineserver_bin) if runner.wineserver_bin else None, int(runner.is_system), datetime.now(timezone.utc).isoformat()),
            )

    def load_runner(self, runner_id: str) -> Runner:
        if runner_id == "system-wine":
            wine_path = shutil.which("wine") or "/usr/bin/wine"
            wineserver_path = shutil.which("wineserver")
            return Runner(
                id="system-wine", name="System Wine", wine_bin=Path(wine_path),
                wineserver_bin=Path(wineserver_path) if wineserver_path else None, is_system=True,
            )
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM runners WHERE id = ?", (runner_id,)).fetchone()
            if not row:
                raise ResourceNotFoundError(f"Runner '{runner_id}' not found")
            return Runner(
                id=row["id"], name=row["name"], wine_bin=Path(row["wine_bin"]),
                wineserver_bin=Path(row["wineserver_bin"]) if row["wineserver_bin"] else None,
                is_system=bool(row["is_system"]),
            )

    def list_runners(self) -> List[Runner]:
        runners = [self.load_runner("system-wine")]
        with self.get_connection() as conn:
            rows = conn.execute("SELECT id FROM runners WHERE id != 'system-wine' ORDER BY id ASC").fetchall()
        for r in rows:
            try:
                runners.append(self.load_runner(r["id"]))
            except Exception:
                pass
        return runners

    def sync_prefix_snapshot(self, prefix_id: str) -> None:
        write_prefix_snapshot(self, prefix_id)

    def delete_runner(self, runner_id: str) -> None:
        if runner_id == "system-wine":
            raise WineboxError("Cannot delete built-in 'system-wine' runner")
        with self.get_connection() as conn:
            pfx_used = conn.execute("SELECT COUNT(*) FROM prefixes WHERE runner_id = ?", (runner_id,)).fetchone()[0]
            app_used = conn.execute("SELECT COUNT(*) FROM applications WHERE runner_id = ?", (runner_id,)).fetchone()[0]
            if pfx_used > 0 or app_used > 0:
                raise WineboxError(
                    f"Runner '{runner_id}' is currently in use by {pfx_used} prefix(es) and {app_used} app(s)."
                )
            cur = conn.execute("DELETE FROM runners WHERE id = ?", (runner_id,))
            if cur.rowcount == 0:
                raise ResourceNotFoundError(f"Runner '{runner_id}' not found")

    # ---------------- Application Groups CRUD ----------------
    def save_group(self, group: AppGroup) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO groups (id, name, icon, sort_order, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    icon = excluded.icon,
                    sort_order = excluded.sort_order;
                """,
                (group.id, group.name, group.icon, group.sort_order, group.created_at.isoformat()),
            )

    def load_group(self, group_id: str) -> AppGroup:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
            if not row:
                raise ResourceNotFoundError(f"Group '{group_id}' not found")
            return AppGroup(
                id=row["id"],
                name=row["name"],
                icon=row["icon"] or "",
                sort_order=row["sort_order"] or 0,
                created_at=datetime.fromisoformat(row["created_at"]),
            )

    def list_groups(self) -> List[AppGroup]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM groups ORDER BY sort_order ASC, name ASC").fetchall()
            return [
                AppGroup(
                    id=r["id"],
                    name=r["name"],
                    icon=r["icon"] or "",
                    sort_order=r["sort_order"] or 0,
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
                for r in rows
            ]

    def delete_group(self, group_id: str) -> None:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM app_groups WHERE group_id = ?", (group_id,))
            cur = conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
            if cur.rowcount == 0:
                raise ResourceNotFoundError(f"Group '{group_id}' not found")

    def set_app_groups(self, app_id: str, group_ids: List[str]) -> None:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM app_groups WHERE app_id = ?", (app_id,))
            for gid in group_ids:
                conn.execute("INSERT OR IGNORE INTO app_groups (app_id, group_id) VALUES (?, ?)", (app_id, gid))

    def get_app_group_ids(self, app_id: str) -> List[str]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT group_id FROM app_groups WHERE app_id = ?", (app_id,)).fetchall()
            return [r["group_id"] for r in rows]
