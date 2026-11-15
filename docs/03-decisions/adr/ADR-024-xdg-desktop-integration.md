# ADR-024: Integrasi XDG Desktop Entry (.desktop) dengan Opsi Interaktif dan Manajemen Siklus Hidup

## Status
Accepted

## Konteks
Aplikasi dan game yang dipasang melalui WineBox saat ini hanya dapat dijalankan melalui terminal (`winebox app run <app_id>`) atau jika pengguna memilih ekspor ke Lutris (ADR-022).

Pada sistem desktop Linux (GNOME, KDE Plasma, XFCE, Cinnamon, Cosmic, mau pun application launcher seperti Rofi/Wofi), standar peluncur aplikasi yang diakui secara universal adalah berkas **XDG Desktop Entry (`.desktop`)** yang ditempatkan di `$XDG_DATA_HOME/applications/` (biasanya `~/.local/share/applications/`).

Ketiadaan peluncur desktop native membuat pengguna awam atau pengguna desktop harian merasa canggung karena aplikasi Windows yang telah dipasang tidak langsung tampak pada daftar menu aplikasi sistem operasi. Di sisi lain, tidak semua aplikasi (misalnya command-line tool Windows atau helper utilitas) membutuhkan shortcut di menu aplikasi, sehingga pembuatan `.desktop` harus bersifat opsional dan dapat dikonfigurasi per aplikasi.

## Keputusan

### 1. Format dan Penempatan Berkas `.desktop`
WineBox akan membuat berkas desktop entry di direktori standar XDG pengguna:
- **Lokasi**: `~/.local/share/applications/winebox-<app_id>.desktop`
- **Spesifikasi**: Sesuai dengan *Freedesktop.org Desktop Entry Specification*.
- **Isi Berkas**:
  ```ini
  [Desktop Entry]
  Type=Application
  Name=<Application Display Name>
  Exec=winebox app run <app_id>
  Icon=<Icon Path atau 'wine'>
  Terminal=false
  Categories=Game;Utility;
  StartupNotify=true
  Comment=Run <Application Display Name> in Winebox sandbox
  Actions=Configure;

  [Desktop Action Configure]
  Name=WineBox App Info
  Exec=winebox app info <app_id>
  ```

### 2. Opsi Interaktif pada Wizard `winebox add`
Setelah pemilihan aplikasi dan integrasi Lutris, wizard `winebox add` akan menampilkan prompt konfirmasi interaktif:
- Opsi: `Create Desktop Shortcut (.desktop)? [Y/n]` (default: Yes).
- Jika pengguna memilih `yes`, berkas `.desktop` akan dibuat seketika dan lokasinya dilaporkan pada panel ringkasan akhir.

### 3. Perintah CLI Mandiri (`winebox app desktop`)
Menyediakan perintah CLI mandiri di bawah namespace `app`:
- `winebox app desktop <app_id>`: Membuat atau memperbarui berkas `.desktop` untuk aplikasi terdaftar.
- `winebox app desktop <app_id> --icon <path>`: Menentukan path ikon khusus (`.png` / `.svg` / `.ico`).
- `winebox app desktop <app_id> --categories <cats>`: Menyesuaikan kategori XDG (default: `Game;Utility;`).
- `winebox app desktop <app_id> --remove`: Menghapus berkas `.desktop` aplikasi tersebut.

### 4. Sinkronisasi Siklus Hidup Aplikasi (Auto-Cleanup)
Ketika aplikasi dihapus dari WineBox melalui `winebox app remove <app_id>`, sistem akan secara otomatis memeriksa dan menghapus berkas `winebox-<app_id>.desktop` terkait agar tidak meninggalkan pintasan rusak (*dead shortcut*) di menu aplikasi host.

## Konsekuensi

### Positif
- Aksesibilitas instan: Pengguna dapat langsung mencari dan membuka aplikasi/game dari menu aplikasi Linux atau dock OS dengan 1 klik.
- Fleksibel: Pengguna bebas memilih apakah aplikasi yang dipasang membutuhkan `.desktop` atau tidak.
- Bersih: Tidak meninggalkan berkas sampah saat aplikasi di-remove.
- Kompatibel 100% dengan standar Freedesktop.org tanpa memerlukan hak akses root.

### Negatif / Mitigasi
- Standar ikon bawaan menggunakan generic `wine` atau `applications-games` jika pengguna tidak menyertakan ikon custom (mitigasi: didukung opsi `--icon` di CLI dan pencarian ikon otomatis di direktori aplikasi jika tersedia).
