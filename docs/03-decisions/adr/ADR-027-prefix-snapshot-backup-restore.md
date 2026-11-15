# ADR-027: Prefix Snapshot & Backup (`winebox prefix backup / restore`)

- **Status:** Accepted
- **Date:** 2026-11-15
- **Deciders:** WineBox Maintainers

## Context
Pengguna sering melakukan eksperimen pada Wine Prefix (memasang mod, menjalankan `winetricks`, atau mengganti versi runner) yang berisiko merusak registry (`user.reg`, `system.reg`) atau berkas aplikasi/savegame di dalam `home/` terisolasi.

## Decision
1. **Format Arsip Portabel (`.tar.zst` + Fallback `.tar.gz`):**
   - WineBox mengemas `prefix/`, `home/`, `prefix.toml` (jika ada), dan `manifest.json` ke dalam arsip `.tar.zst` menggunakan `tar -I "zstd -T0 -3"` bila `zstd` tersedia di host, atau fallback ke `.tar.gz` via Python stdlib `tarfile`.
   - `prefix.lock` dikecualikan agar hasil restore tidak mewarisi lock file lama.
2. **Running Prefix Guard:**
   - Baik `backup` maupun `restore` (saat menimpa prefix dengan `--force`) menolak berjalan apabila `prefix.lock` aktif atau terdapat proses prefix berjalan.
3. **Validasi Arsip & Atomic Staging Restore:**
   - Sebelum ekstraksi pada `restore`, seluruh member arsip diperiksa terhadap *path traversal* (`..`), path absolut, serta symlink keluar root arsip.
   - Ekstraksi dilakukan ke direktori staging, disanitasi oleh `PrefixAuditor.sanitize_dosdevices`, lalu dipindahkan secara atomik ke `prefixes/<target_id>` dan didaftarkan ulang di `SqliteRepository`.

## Consequences
- Backup menyimpan state prefix dan savegame dalam satu berkas portabel tanpa dependensi Python eksternal.
- Proses restore aman terhadap arsip berbahaya maupun kegagalan di tengah ekstraksi.
