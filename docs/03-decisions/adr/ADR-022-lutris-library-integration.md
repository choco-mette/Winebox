# ADR-022: Integrasi Ekspor Aplikasi WineBox ke Lutris Library Melalui Official Installer Script (`lutris --install`)

## Status
Accepted

## Konteks
WineBox berfokus pada orkestrasi eksekusi aplikasi Windows yang aman di dalam sandbox Bubblewrap melalui antarmuka CLI (ADR-002, ADR-004). Banyak pengguna Linux menggunakan **Lutris** sebagai antarmuka grafis (GUI) terpusat untuk mengelola koleksi permainan, menampilkan sampul (*cover art*), serta mencatat waktu bermain (*play time tracking*).

Jika WineBox memodifikasi database internal SQLite Lutris (`~/.local/share/lutris/pga.db`) secara langsung dari luar, terdapat risiko:
1. *Race condition* atau *database lock* jika jendela GUI Lutris sedang terbuka.
2. Ketidakcocokan skema kolom atau tipe data antar versi Lutris yang dapat menyebabkan aplikasi Lutris mengalami *crash* (`TypeError` / `KeyError`) saat memuat daftar permainan.

Sebaliknya, Lutris menyediakan jalur antarmuka baris perintah resmi (`lutris --install <script.yml>` atau `lutris -i <script.yml>`) yang menerima berkas *Lutris Installer Script YAML* lokal dan menyerahkan proses validasi serta penulisan database sepenuhnya kepada proses internal Lutris sendiri.

## Keputusan

### 1. Lutris sebagai Frontend Peluncur, WineBox sebagai Mesin Sandbox Eksekusi
Menghubungkan WineBox ke Lutris dengan menjadikan Lutris sebagai antarmuka katalog visual (GUI launcher), sementara seluruh siklus hidup eksekusi, kunci konkurensi (`prefix.lock`), penegakan `SecurityProfile`, dan pencatatan log tetap dikendalikan 100% oleh WineBox melalui perintah `winebox app run <app_id>`.

### 2. Pembuatan Lutris Installer Script YAML Resmi & Eksekusi `lutris -i`
Menyediakan komponen `LutrisAdapter` (`src/winebox/infrastructure/lutris_adapter.py`) dan `LutrisService` (`src/winebox/application/lutris_service.py`) yang menghasilkan berkas installer YAML standar Lutris di `~/.local/share/winebox/lutris/<app_id>-lutris.yml`:
```yaml
name: "<App Display Name>"
game_slug: "<app_id>"
slug: "<app_id>-winebox"
version: "WineBox Sandbox"
runner: linux
script:
  game:
    exe: "/path/to/winebox"
    args: "app run <app_id>"
  system:
    disable_runtime: true
```
- Karena bagian `script` tidak mendefinisikan langkah pengunduhan `installer`, properti internal Lutris `creates_game_folder` bernilai `False` sehingga Lutris langsung mendaftarkan shortcut tanpa menyalin ulang data permainan.
- Pengaturan `system.disable_runtime: true` memastikan *Lutris Runtime* tidak mengintervensi variabel lingkungan `LD_LIBRARY_PATH` milik Bubblewrap (`bwrap`).
- WineBox kemudian memanggil biner `lutris --install <path_yml>` agar Lutris menyimpan sendiri entri permainan ke dalam database `pga.db` secara aman.

### 3. Sinkronisasi Siklus Hidup Proses untuk Pelacakan Waktu Bermain (*Play Time*)
Karena `WineAdapter.build_run_cmd` mempertahankan proses utama sandbox tetap hidup menggunakan `wineserver -w` hingga seluruh proses anak permainan ditutup, Lutris dapat mendeteksi status aktif permainan secara akurat (tombol **Play** berubah menjadi **Stop** selama permainan berjalan, dan durasi bermain tercatat dengan presisi di Lutris).

### 4. Antarmuka CLI Terintegrasi (`winebox lutris` dan `winebox add`)
- Menambahkan opsi interaktif TUI pada akhir wizard `winebox add`: menanyakan apakah aplikasi/game yang baru ditambahkan ingin langsung didaftarkan ke Lutris Library (`lutris -i`).
- Menyediakan perintah `winebox lutris add [app_id]`: memilih aplikasi WineBox yang sudah ada (via TUI interaktif `↑/↓`, `Space`, `Enter` jika `app_id` tidak disebutkan) untuk didaftarkan ke Lutris melalui `lutris --install`.

## Konsekuensi

### Positif
- **0% risiko korupsi database atau crash pada Lutris**, karena Lutris sendiri yang memvalidasi dan menulis ke `pga.db`.
- Tetap kompatibel meskipun Lutris sedang terbuka di layar pengguna.
- Pengguna mendapatkan kenyamanan antarmuka grafis Lutris sekaligus isolasi keamanan penuh Bubblewrap WineBox.
- Pelacakan waktu bermain (*Play Time*) di Lutris berfungsi penuh berkat sinkronisasi `wineserver -w`.

### Negatif / Mitigasi
- Memerlukan konfirmasi 1 kali klik tombol **Install** pada jendela dialog Lutris yang terbuka saat `lutris -i` dijalankan (ini adalah perilaku standar keamanan Lutris).
- Memerlukan paket `lutris` terpasang di sistem host (diverifikasi otomatis oleh `LutrisAdapter` menggunakan `shutil.which("lutris")` atau lokasi standar `/usr/games/lutris`).
