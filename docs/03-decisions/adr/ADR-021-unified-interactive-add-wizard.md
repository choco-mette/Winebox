# ADR-021: Wizard Penambahan Aplikasi Terpadu (winebox add) dengan Deteksi Interaktif Executable dan Profil Keamanan

## Status
Accepted

## Konteks
Sebelumnya, penambahan aplikasi Windows ke dalam WineBox terbagi ke dalam alur yang terpisah dan memerlukan banyak parameter manual:
1. Pemasangan dari installer menggunakan perintah `winebox install <file>` yang terbatas pada berkas `.exe` atau `.msi`.
2. Penambahan folder aplikasi/game pre-installed (portable) menggunakan perintah `winebox import app <source_dir> --prefix <prefix> --id <id> --name <name> --exe <exe> [--profile <profile>]` yang menuntut pengguna menghafal banyak argumen baris perintah.
3. Pengguna sering kesulitan menentukan path relatif berkas executable (`.exe`) utama di dalam struktur folder game yang kompleks (misalnya game dengan ratusan file di subfolder `bin/` atau `Game/`), sehingga harus meneliti direktori secara manual sebelum menjalankan perintah import.
4. Diperlukan alur pemilihan profil keamanan (Security Profile) yang interaktif dari database SQLite (ADR-020) di mana pengguna dapat memilih tingkat izin isolasi, dengan profil `permissive` (GPU, Audio, Network aktif) sebagai pilihan default yang direkomendasikan untuk aplikasi permainan (game).

## Keputusan

### 1. Perintah Terpadu Satu Pintu: `winebox add`
Menyediakan perintah wizard terpadu `winebox add` di antarmuka baris perintah (CLI) yang memandu pengguna langkah demi langkah. Perintah `winebox install` tetap dipertahankan dan didelegasikan ke wizard ini.

### 2. Deteksi dan Pemilihan Jenis Sumber Interaktif
Wizard menanyakan jenis sumber instalasi:
- `[1] Folder Game / Aplikasi Pre-installed (Portable)`: Menjalankan staging direktori, audit symlink, dan pemindahan ke `drive_c/Program Files/<app_id>`.
- `[2] Berkas Installer Windows (.exe / .msi)`: Menjalankan eksekusi installer di dalam sandbox Bubblewrap terisolasi dengan akses read-only ke installer di host.

### 3. Otomatisasi Normalisasi Nama dan ID Aplikasi
Mengurangi redundansi input dengan meminta satu kali `Nama Aplikasi` (display name). Sistem secara otomatis menghasilkan `id` aplikasi yang valid melalui proses slugifikasi (*kebab-case*, huruf kecil, mengganti spasi dan karakter khusus dengan tanda minus `-`).

### 4. Pemindaian dan Seleksi Interaktif Berkas Executable (`.exe`)
Sistem secara otomatis memindai seluruh berkas `.exe` di dalam direktori aplikasi:
- Menampilkan daftar berkas executable bernomor di terminal interaktif.
- Memprioritaskan file `.exe` di root direktori dan menyortir uninstaller (`unins*.exe`) ke posisi bawah.
- Pengguna cukup memilih nomor (misal `1` atau menekan Enter untuk pilihan rekomendasi teratas) tanpa perlu mengetikkan path berkas.
- Menyediakan opsi fallback `[0]` untuk mengetikkan path executable secara manual jika diperlukan.

### 5. Seleksi Profil Keamanan Dinamis Berbasis SQLite
Wizard membaca daftar profil keamanan yang tersedia di database SQLite:
- Menampilkan pilihan profil: `permissive`, `balanced`, `zero-trust`, `paranoid`, serta profil kustom pengguna.
- Menjadikan `permissive` sebagai rekomendasi default (menekan Enter langsung memilih `permissive`), memastikan game langsung mendapatkan akses GPU DRI, Audio Pulse/PipeWire, dan Jaringan tanpa konfigurasi tambahan.

### 6. Fleksibilitas Pemilihan dan Pembuatan Prefix
Wizard menampilkan daftar Wine Prefix yang ada saat ini, serta opsi `[Create New Prefix]`. Jika pengguna memilih membuat prefix baru, wizard otomatis menginisialisasi prefix dengan profil keamanan yang dipilih.

## Konsekuensi

### Positif
- Pengalaman pengguna (UX) terminal menjadi sangat intuitif, cepat, dan minim gesekan (*frictionless*).
- Menghilangkan beban pengguna dalam mencari path `.exe` di dalam direktori yang dalam atau rumit.
- Redundansi input ID dan Name dihilangkan.
- Integrasi mulus dengan model profil keamanan SQLite (ADR-020).

### Negatif / Mitigasi
- Wizard interaktif bergantung pada TTY terminal (mitigasi: perintah `winebox import app` dan flag opsional pada `winebox add` tetap mendukung mode non-interaktif untuk kebutuhan skrip otomatisasi).
- Folder dengan puluhan ribu subdirektori dapat memperlambat proses pemindaian `.exe` (mitigasi: batas kedalaman pencarian atau pemindaian rekursif terarah).
