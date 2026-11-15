# ADR-026: Runner Manager Terintegrasi dengan Rootless Shared Ecosystem Symlinks

## Status
Accepted

## Konteks
Wine bawaan distro Linux (*system Wine*) sering kali tertinggal atau tidak memiliki patch khusus yang dibutuhkan game Windows modern (seperti *Media Foundation*, *fsync/esync*, atau perbaikan *DXVK/VKD3D*). Saat ini WineBox hanya mendukung pendaftaran runner custom secara manual via `winebox runner register` setelah pengguna mengunduh dan mengekstrak arsip sendiri.

Selain itu, pengguna Linux gaming umumnya menggunakan lebih dari satu aplikasi (Lutris, Steam, Heroic, Bottles). Memasang runner di path sistem global seperti `/opt` atau `/usr/local` memerlukan hak akses `root` (`sudo`), melanggar prinsip rootless XDG WineBox (ADR-015), serta berisiko bentrok dengan package manager OS. Sebaliknya, ekosistem desktop Linux sudah memiliki direktori standar per-user untuk berbagi runner tanpa `root`:
- `~/.local/share/lutris/runners/wine/` (untuk Wine-Builds / Wine-GE)
- `~/.local/share/Steam/compatibilitytools.d/` (untuk GE-Proton, dibaca oleh Steam, Heroic, dan Bottles)

## Keputusan

### 1. Penyimpanan Utama Rootless di `~/.local/share/winebox/runners/`
Seluruh runner yang diunduh oleh WineBox tetap disimpan secara rootless di `$XDG_DATA_HOME/winebox/runners/<runner_id>/`, dan arsip tarball di-cache di `$XDG_DATA_HOME/winebox/cache/runners/`. Eksekusi di Bubblewrap tetap me-mount direktori runner secara read-only (`--ro-bind`) ke `/app/runner`.

### 2. Dukungan Multi-Source & Auto-Deteksi Layout `files/`
`RunnerAdapter` mendukung pengambilan daftar rilis dan tarball dari repositori resmi melalui GitHub Releases API (menggunakan `urllib.request` standar tanpa dependensi pihak ketiga tambahan):
- `wine-builds` (`Kron4ek/Wine-Builds` — Wine-Staging / Wine-TKG)
- `ge-proton` (`GloriousEggroll/proton-ge-custom`)
*(Legacy `wine-ge-custom` yang sudah EOL tetap dapat dipakai jika terpasang di Lutris lewat `winebox runner scan`.)*

Untuk layout GE-Proton yang menempatkan biner di dalam subdirektori `files/bin/wine`, detektor binary otomatis mengarahkan `wine_bin` ke `files/bin/wine` sehingga `runner.wine_bin.parent.parent` otomatis memetakan `files/` ke `/app/runner` di dalam Bubblewrap tanpa mengubah `WineAdapter`.

### 3. Ekstraksi Arsip Aman (*Anti-Path-Traversal Guard*)
Proses ekstraksi `.tar.xz` / `.tar.gz` wajib memvalidasi seluruh entri tar sebelum menulis ke disk untuk menolak jalur absolut (`/etc/...`), traversal (`..`), maupun symlink yang mengarah ke luar folder target.

### 4. Berbagi Ekosistem via Symlink (`--share`) & Auto-Scan (`runner scan`)
- **Share ke Aplikasi Lain:** Pengguna dapat mengaktifkan opsi `--share` saat instalasi atau menjalankan `winebox runner share <id>` untuk membuat *symbolic link* dari folder runner WineBox ke `~/.local/share/lutris/runners/wine/` atau `~/.local/share/Steam/compatibilitytools.d/`. Dengan 1 salinan fisik, runner langsung terbaca di WineBox, Lutris, Steam, dan Heroic tanpa `sudo`.
- **Auto-Scan Runner Eksisting:** Perintah `winebox runner scan` memindai direktori Lutris dan Steam milik pengguna untuk mendeteksi dan mendaftarkan runner yang sudah ada ke SQLite WineBox tanpa perlu mengunduh ulang.

### 5. Manajemen Siklus Hidup Aman (`runner remove`)
`winebox runner remove <id>` menolak penghapusan jika runner masih dipakai oleh prefix atau aplikasi terdaftar (dan menolak penghapusan `system-wine`), serta membersihkan symlink share dan direktori runner saat dihapus.

## Konsekuensi

### Positif
- Pengalaman instalasi runner modern 1 perintah (`winebox runner install`) atau via TUI selector.
- Tetap 100% rootless (tanpa `sudo`) dan aman di dalam sandbox Bubblewrap `--ro-bind`.
- Hemat ruang penyimpanan karena satu runner fisik dapat dipakai bersama oleh WineBox, Steam, Lutris, dan Heroic melalui symlink standar XDG.

### Negatif / Mitigasi
- Beberapa game yang memakai *GE-Proton* penuh terkadang bergantung pada *Steam Runtime* atau `umu-launcher` jika tidak hanya mengandalkan `files/bin/wine` (mitigasi: `wine-builds` Kron4ek disediakan sebagai opsi utama yang 100% standalone untuk prefix Wine standar, sementara `ge-proton` tetap didukung penuh untuk kompatibilitas Proton-Wine).
