"""Database schema DDL and built-in security profile seeds for SQLite (ADR-020)."""

import sqlite3
from winebox.domain.models import SecurityProfile

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

SCHEMA_DDL = [
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
    """,
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
    """,
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
    """,
    """
    CREATE TABLE IF NOT EXISTS app_host_mounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
        host_path TEXT NOT NULL,
        sandbox_path TEXT NOT NULL,
        mode TEXT NOT NULL DEFAULT 'ro'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS app_env_vars (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
        key TEXT NOT NULL,
        value TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS runners (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        wine_bin TEXT NOT NULL,
        wineserver_bin TEXT,
        is_system INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    """,
]


def init_database_schema(conn: sqlite3.Connection) -> None:
    """Initializes SQLite tables and seeds built-in security profiles if empty."""
    for ddl in SCHEMA_DDL:
        conn.execute(ddl)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION};")

    cursor = conn.execute("SELECT COUNT(*) FROM security_profiles")
    if cursor.fetchone()[0] == 0:
        for p in DEFAULT_PROFILES:
            conn.execute(
                """
                INSERT INTO security_profiles (id, name, is_builtin, display, audio, network, gpu, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (p.id, p.name, int(p.is_builtin), int(p.display), int(p.audio), int(p.network), int(p.gpu), p.description),
            )

