# Configuration Specification

Dokumen ini mendefinisikan arsitektur penyimpanan konfigurasi, skema database SQLite, dan manajemen log WineBox (mengacu pada [ADR-015](file:///home/choco/Project/www/Winebox/docs/03-decisions/adr/ADR-015-xdg-storage-layout.md) dan [ADR-020](file:///home/choco/Project/www/Winebox/docs/03-decisions/adr/ADR-020-sqlite-configuration-and-rotating-logs.md)).

---

## 1. Tata Letak Penyimpanan (XDG Base Directory)

WineBox beroperasi dalam mode rootless murni:
- **Database Konfigurasi Terpusat:** `$XDG_DATA_HOME/winebox/winebox.db` (default: `~/.local/share/winebox/winebox.db`)
- **Direktori Lingkungan Prefix:** `$XDG_DATA_HOME/winebox/prefixes/<prefix-id>/`
  - `prefix/`: Filesystem Wine (`drive_c/`, registry).
  - `home/`: Virtual HOME pengguna Linux privat.
  - `logs/execution.log`: File log eksekusi terotasi otomatis.
  - `metadata.json`: Snapshot lokal untuk disaster recovery & portabilitas prefix.
  - `prefix.lock`: Kernel lock konkurensi single-instance.
- **Direktori Staging Sementara:** `$XDG_DATA_HOME/winebox/staging/`
- **Konfigurasi Global & Preset Ekspor:** `$XDG_CONFIG_HOME/winebox/config.toml`

---

## 2. Skema Database SQLite (`winebox.db`)

SQLite dijalankan dengan mode `PRAGMA journal_mode=WAL` dan `PRAGMA foreign_keys=ON`.

### Tabel `security_profiles`
Menyimpan preset profil keamanan (bawaan sistem dan kustom pengguna).
```sql
CREATE TABLE security_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    is_builtin INTEGER NOT NULL DEFAULT 0,
    display INTEGER NOT NULL DEFAULT 1,
    audio INTEGER NOT NULL DEFAULT 1,
    network INTEGER NOT NULL DEFAULT 1,
    gpu INTEGER NOT NULL DEFAULT 1,
    description TEXT DEFAULT ''
);
```

#### Preset Bawaan (Default Seed):
- `paranoid`: `display=0, audio=0, network=0, gpu=0` (Headless/CLI test)
- `zero-trust`: `display=1, audio=0, network=0, gpu=0` (Offline tools, dokumen)
- `balanced`: `display=1, audio=1, network=0, gpu=0` (Multimedia offline)
- `permissive`: `display=1, audio=1, network=1, gpu=1` (Gaming, online out-of-the-box)

---

### Tabel `prefixes`
```sql
CREATE TABLE prefixes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    runner_id TEXT NOT NULL DEFAULT 'system-wine',
    default_profile_id TEXT NOT NULL REFERENCES security_profiles(id) ON DELETE RESTRICT,
    origin TEXT NOT NULL DEFAULT 'created', -- 'created' | 'imported'
    status TEXT NOT NULL DEFAULT 'ready',
    created_at TEXT NOT NULL
);
```

---

### Tabel `applications`
```sql
CREATE TABLE applications (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    prefix_id TEXT NOT NULL REFERENCES prefixes(id) ON DELETE CASCADE,
    exe_path TEXT NOT NULL,
    runner_id TEXT NOT NULL DEFAULT 'system-wine',
    profile_id TEXT NOT NULL REFERENCES security_profiles(id) ON DELETE RESTRICT,
    default_args TEXT DEFAULT '[]', -- JSON string of arguments
    last_run_at TEXT,
    last_exit_code INTEGER,
    status TEXT NOT NULL DEFAULT 'ready',
    created_at TEXT NOT NULL
);
```

---

### Tabel `app_host_mounts`
```sql
CREATE TABLE app_host_mounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    host_path TEXT NOT NULL,
    sandbox_path TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'ro' -- 'ro' | 'rw'
);
```

---

### Tabel `app_env_vars`
```sql
CREATE TABLE app_env_vars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT NOT NULL
);
```

---

### Tabel `runners`
```sql
CREATE TABLE runners (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    wine_bin TEXT NOT NULL,
    wineserver_bin TEXT,
    is_system INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
```

---

## 3. Snapshot Metadata Lokal (`prefixes/<id>/metadata.json`)

Setiap kali data prefix atau aplikasi diperbarui di SQLite, WineBox mengekspor snapshot JSON sederhana ke dalam folder prefix:
```json
{
  "prefix": {
    "id": "creative",
    "name": "Creative Environment",
    "runner_id": "system-wine",
    "default_profile_id": "balanced"
  },
  "applications": [
    {
      "id": "fl-studio",
      "name": "FL Studio",
      "exe_path": "drive_c/Program Files/FL Studio/FL64.exe",
      "profile_id": "permissive"
    }
  ],
  "synced_at": "2026-11-13T21:40:00Z"
}
```
*Tujuan:* Jika database `winebox.db` terhapus atau folder prefix dipindahkan ke komputer lain, perintah `winebox prefix import-local <dir>` atau auto-restore dapat memulihkan seluruh registrasi aplikasi secara otomatis.

---

## 4. Spesifikasi Log File Terotasi

Output log Wine dialirkan ke:
`~/.local/share/winebox/prefixes/<id>/logs/execution.log`

- **Mekanisme:** `logging.handlers.RotatingFileHandler`
- **Maksimal Ukuran:** 5 MB (`maxBytes = 5 * 1024 * 1024`)
- **Cadangan Rotasi:** 3 file (`backupCount = 3`: `execution.log`, `execution.log.1`, `execution.log.2`)
- **Format:** `[YYYY-MM-DD HH:MM:SS] [LEVEL] [APP_ID] <message>`
