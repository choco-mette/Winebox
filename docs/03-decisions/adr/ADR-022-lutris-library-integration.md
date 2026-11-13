# ADR-022: Integrasi Ekspor dan Sinkronisasi Aplikasi WineBox ke Lutris Library

## Status
Accepted

## Konteks
WineBox berfokus pada orkestrasi eksekusi aplikasi Windows yang aman di dalam sandbox Bubblewrap melalui antarmuka CLI (ADR-002, ADR-004). Namun, banyak pengguna Linux menggunakan **Lutris** sebagai antarmuka grafis (GUI) terpusat untuk mengelola koleksi permainan, menampilkan sampul (*cover art*), serta mencatat waktu bermain (*play time tracking*).

Jika pengguna menjalankan permainan secara langsung menggunakan runner Wine bawaan Lutris, permainan tersebut berjalan tanpa isolasi sandbox Bubblewrap dan tanpa kebijakan keamanan terpusat milik WineBox (ADR-020). Di sisi lain, mendaftarkan setiap permainan WineBox ke dalam GUI Lutris secara manual melalui formulir konfigurasi Lutris sangat memakan waktu dan rawan kesalahan pengetikan path.

## Keputusan

### 1. Lutris sebagai Frontend Peluncur, WineBox sebagai Mesin Sandbox Eksekusi
Menghubungkan WineBox ke Lutris dengan menjadikan Lutris sebagai antarmuka katalog visual (GUI launcher), sementara seluruh siklus hidup eksekusi, kunci konkurensi (`prefix.lock`), penegakan `SecurityProfile`, dan pencatatan log tetap dikendalikan 100% oleh WineBox melalui perintah `winebox app run <app_id>`.

### 2. Injeksi Langsung ke Database SQLite Lutris (`pga.db`) dan Konfigurasi YAML
Menyediakan komponen `LutrisAdapter` (`src/winebox/infrastructure/lutris_adapter.py`) yang secara otomatis mendeteksi instalasi Lutris pengguna dan menuliskan konfigurasi permainan tanpa ketergantungan pustaka eksternal:
- **File Konfigurasi YAML** (`~/.local/share/lutris/games/winebox-<app_id>-<timestamp>.yml` dan `~/.config/lutris/games/`):
  Mengonfigurasi `game.exe` ke path biner `winebox` dengan `game.args: app run <app_id>` serta `system.disable_runtime: true` agar runtime LD_LIBRARY_PATH internal Lutris tidak mengganggu proses `bwrap`.
- **Database SQLite Lutris** (`~/.local/share/lutris/pga.db`, tabel `games`):
  Menyisipkan atau memperbarui baris permainan dengan `runner = 'linux'`, `installed = 1`, `name`, `slug`, dan `configpath` yang merujuk ke berkas YAML tersebut.

### 3. Sinkronisasi Siklus Hidup Proses untuk Pelacakan Waktu Bermain (*Play Time*)
Karena `WineAdapter.build_run_cmd` mempertahankan proses utama sandbox tetap hidup menggunakan `wineserver -w` hingga seluruh proses anak permainan ditutup, Lutris dapat mendeteksi status aktif permainan secara akurat (tombol **Play** berubah menjadi **Stop** selama permainan berjalan, dan durasi bermain tercatat dengan presisi di Lutris).

### 4. Antarmuka CLI Terintegrasi (`winebox lutris` dan `winebox add`)
- Menambahkan opsi interaktif TUI pada akhir wizard `winebox add`: menanyakan apakah aplikasi/game yang baru ditambahkan ingin langsung didaftarkan ke Lutris Library.
- Menyediakan grup perintah `winebox lutris`:
  - `winebox lutris sync`: Memilih dan menyinkronkan aplikasi WineBox yang sudah terdaftar ke dalam Lutris Library.
  - `winebox lutris remove <app_id>`: Menghapus entri shortcut permainan WineBox dari database dan berkas YAML Lutris tanpa menghapus data permainan di WineBox.

## Konsekuensi

### Positif
- Pengguna mendapatkan kenyamanan antarmuka grafis Lutris tanpa mengorbankan isolasi keamanan Bubblewrap WineBox.
- Pendaftaran ke Lutris berlangsung instan dan otomatis tanpa perlu mengisi formulir manual di GUI Lutris.
- Pelacakan waktu bermain (*Play Time*) di Lutris berfungsi penuh berkat sinkronisasi `wineserver -w`.

### Negatif / Mitigasi
- Jika aplikasi GUI Lutris sedang terbuka saat database `pga.db` dimodifikasi dari luar, Lutris mungkin memerlukan muat ulang (*restart* aplikasi Lutris) agar daftar permainan baru terlihat di layar (mitigasi: menampilkan pesan informasi kepada pengguna untuk memuat ulang Lutris jika sedang berjalan).
- Skema tabel `games` pada `pga.db` dapat bervariasi antar versi Lutris (mitigasi: melakukan introspeksi kolom `PRAGMA table_info(games)` sebelum menjalankan query `INSERT`/`UPDATE`).
