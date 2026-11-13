"""Snapshot synchronization (metadata.json) and legacy TOML migration helpers (ADR-020)."""

import json
import tomllib
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from winebox.domain.models import Application, AppStatus, Prefix, PrefixOrigin, PrefixStatus

if TYPE_CHECKING:
    from winebox.infrastructure.sqlite_repository import SqliteRepository


def write_prefix_snapshot(repo: "SqliteRepository", prefix_id: str) -> None:
    """Writes a localized metadata.json snapshot inside prefixes/<id>/ for disaster recovery."""
    p_dir = repo.get_prefix_dir(prefix_id)
    if not p_dir.exists():
        return

    try:
        prefix = repo.load_prefix(prefix_id)
        with repo.get_connection() as conn:
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
        pass


def import_legacy_toml_if_needed(repo: "SqliteRepository") -> None:
    """Auto-imports existing legacy TOML prefixes and applications into SQLite."""
    with repo.get_connection() as conn:
        prefix_count = conn.execute("SELECT COUNT(*) FROM prefixes").fetchone()[0]
        if prefix_count > 0:
            return

    for p_dir in sorted(repo.prefixes_dir.iterdir()):
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
                        created_at=datetime.fromisoformat(
                            p_info.get("created_at", datetime.now(timezone.utc).isoformat())
                        ),
                    )
                    repo.save_prefix(prefix)
                except Exception:
                    pass

    if repo.apps_dir.exists():
        for app_file in sorted(repo.apps_dir.glob("*.toml")):
            try:
                with open(app_file, "rb") as f:
                    data = tomllib.load(f)
                app_info = data.get("application", {})
                pol_info = data.get("policy", {})
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
                repo.save_app(app)
            except Exception:
                pass
