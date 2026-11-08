# CLI Specification

Dokumen ini mendefinisikan pohon perintah antarmuka CLI WineBox.

## 1. Desain Perintah Typer

WineBox menggunakan antarmuka hierarkis:

```text
winebox
├── app
│   ├── list               # Menampilkan tabel semua aplikasi terdaftar
│   ├── info <app_id>      # Menampilkan detail konfigurasi & izin aplikasi
│   ├── run <app_id>       # Menjalankan aplikasi Windows di sandbox
│   ├── register           # Mendaftarkan file exe manual dari prefix
│   └── remove <app_id>    # Menghapus registrasi aplikasi
│
├── install <installer>    # Wizard instalasi interaktif berkas exe/msi
│
├── import
│   ├── app <dir>          # Import folder aplikasi portable
│   └── prefix <dir>       # Import folder Wine Prefix eksternal
│
├── prefix
│   ├── list               # Daftar semua prefix terdaftar
│   ├── create <id>        # Membuat prefix baru
│   ├── info <id>          # Detail prefix
│   ├── audit <id>         # Memindai keamanan prefix
│   └── remove <id>        # Menghapus prefix
│
├── runner
│   ├── list               # Menampilkan daftar runner Wine
│   ├── register           # Mendaftarkan custom Wine runner
│   └── info <id>          # Detail runner
│
└── system
    ├── doctor             # Diagnosa dependensi host (bwrap, wine, userns)
    └── version            # Informasi versi WineBox
```

---

## 2. Contoh Tampilan `winebox system doctor`

```text
WineBox System Doctor
============================================================
[PASS] Linux Kernel (Linux 6.x >= 5.4)
[PASS] Unprivileged User Namespaces (enabled)
[PASS] Bubblewrap binary (/usr/bin/bwrap)
[PASS] Wine binary (/usr/bin/wine)
[PASS] X11 Display Server (:0 detected)
[PASS] PulseAudio / PipeWire socket (/run/user/1000/pulse/native)
[PASS] Direct Rendering Infrastructure (/dev/dri)

Status: Sistem Anda 100% siap menjalankan WineBox!
```

