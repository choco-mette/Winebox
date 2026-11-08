# Prefix Specification

Dokumen ini mendefinisikan struktur dan manajemen Wine Prefix pada WineBox.

## 1. Struktur Direktori Prefix

Setiap Wine Prefix disimpan di `$XDG_DATA_HOME/winebox/prefixes/<prefix-id>/`:

```text
prefixes/<prefix-id>/
├── config.toml       # Metadata dan konfigurasi prefix
├── prefix/           # Direktori aktual WINEPREFIX
│   ├── drive_c/      # Filesystem C: Windows
│   ├── dosdevices/   # Pemetaan drive Wine (c:, com, dll.)
│   ├── system.reg    # Registry sistem Windows
│   ├── user.reg      # Registry user Windows
│   └── userdef.reg   # Registry default
├── home/             # Virtual HOME Linux yang diisolasi
│   ├── .cache/
│   ├── .config/
│   └── .local/
├── logs/             # Catatan eksekusi aplikasi
└── prefix.lock       # File lock pengunci konkurensi (ADR-016)
```

---

## 2. Format Konfigurasi Prefix (`config.toml`)

```toml
[prefix]
id = "creative"
name = "Creative Studio Suite"
origin = "created"         # "created" | "imported"
status = "ready"           # "ready" | "staging" | "corrupted"
created_at = "2026-11-08T19:30:00Z"

[runner]
id = "system-wine"

[environment]
home_isolated = true
win_version = "win10"
arch = "win64"             # "win32" | "win64"
```

---

## 3. Konkurensi & Penguncian File (`prefix.lock`)

Untuk mencegah korupsi registry akibat beberapa instance Wine yang berebut daemon `wineserver`:
1. Saat aplikasi hendak dijalankan, `ProcessManager` membuka berkas `prefixes/<id>/prefix.lock`.
2. Menerapkan penguncian non-blocking menggunakan `fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)`.
3. Jika proses lain sedang memegang lock, lemparkan `PrefixLockError` yang menginformasikan bahwa prefix sedang digunakan.
4. Lock otomatis terlepas ketika proses aplikasi berakhir atau ditutup paksa oleh OS.

---

## 4. Audit & Sanitasi Prefix

`PrefixAuditor` melakukan pengecekan berikut sebelum eksekusi atau setelah import:
- **Dosdevices:** Memeriksa folder `dosdevices/`. Menjamin tidak ada symlink yang mengarah langsung ke `/` atau `$HOME` host.
- **Symlink Check:** Memastikan semua symlink di dalam `drive_c/` tidak menyelesaikan path di luar `prefixes/<prefix-id>/`.
- **Registry Check:** Memastikan file `system.reg` dan `user.reg` dapat dibaca dan valid secara struktural.

