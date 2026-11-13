# Panduan Lengkap dan Penjelasan Proyek WineBox

Dokumen ini menjelaskan secara menyeluruh tentang apa itu **WineBox**, bagaimana cara kerjanya, status progress pengembangan yang sudah selesai, serta panduan praktis seluruh perintah (*commands*) dari awal hingga akhir.

---

## 1. Apa itu WineBox?

### Masalah Utama yang Diselesaikan
Di Linux, kita biasa menjalankan software Windows menggunakan **Wine**. Namun, Wine bawaan memiliki risiko keamanan yang besar:
1. **Akses File Tanpa Batas:** Secara default, aplikasi Windows yang berjalan di Wine dapat membaca seluruh isi folder pengguna host (`/home/user/`), termasuk berkas sensitif seperti SSH keys (`~/.ssh`), riwayat browser, cookies, dan dokumen pribadi.
2. **Drive `Z:` yang Berbahaya:** Wine secara default memetakan drive `Z:` ke direktori root host (`/`). Jika aplikasi Windows terkena malware, malware tersebut bisa merusak file Linux Anda.
3. **Pencemaran Direktori:** Wine sering membuat folder dan file konfigurasi acak di `$HOME` Anda.

### Solusi WineBox
**WineBox adalah orchestrator keamanan** yang menggabungkan **Wine** dengan **Bubblewrap (`bwrap`)**.

Bubblewrap bertindak seperti "kandang kaca" (sandbox berbasis Linux Namespaces). Di dalam kandang ini:
- **Aplikasi Windows DIBERI akses perangkat keras:** Layar (Display X11/Wayland), Suara (Audio PulseAudio/PipeWire), Akselerasi 3D (GPU `/dev/dri`), dan Jaringan (Internet).
- **Aplikasi Windows DITOLAK total dari filesystem pribadi host:** Aplikasi tidak bisa melihat folder `/home/user/` Anda. Setiap prefix memiliki folder "Home virtual palsu" sendiri.
- Prinsip utama: **"Hardware Allowed, Host Filesystem Denied"** & **"No Sandbox, No Execution"**.

---

## 2. Rangkuman Progress yang Sudah Selesai Dibuat

Semua fondasi arsitektur, kode inti, repositori konfigurasi, dan antarmuka CLI telah selesai diimplementasikan:

```
Winebox/
├── docs/                        # Dokumentasi Lengkap
│   ├── 01-project/              # Visi & Batasan Cakupan
│   ├── 02-architecture/         # Diagram & Desain Modular
│   ├── 03-decisions/adr/        # 20 Keputusan Arsitektural Resmi (ADR-001 s/d ADR-020)
│   ├── 04-security/             # Threat Model & Analisis Ancaman
│   ├── 05-specifications/       # Spesifikasi Teknis (Sandbox, Prefix, Runner, CLI, Config)
│   ├── 06-development/          # Standar Coding, Setup, & Rilis
│   └── private/                 # Dokumen Panduan & Catatan Privat
│
├── src/winebox/                 # Source Code Python (Modular Layered Architecture)
│   ├── common/                  # System Doctor & Exception Hierarchy
│   ├── domain/                  # Entitas Inti (Application, Prefix, Runner, SecurityProfile)
│   ├── security/                # PolicyValidator, PrefixAuditor, MountBuilder
│   ├── infrastructure/          # BwrapAdapter, WineAdapter, ProcessManager, SqliteRepository, LogManager
│   ├── application/             # Services (Prefix, App, Runner, Install, Import, Profile)
│   └── interface/               # CLI Modern (Typer + Rich)
│
├── tests/                       # Test Suite Otomatis
│   ├── unit/                    # 37 Unit Test (Security, Profiles, Repo, Logging, CLI)
│   └── integration/             # 3 Integration Test (Live Bubblewrap Sandbox di Kernel Host)
│
├── pyproject.toml               # Standar Packaging Modern PEP 621 (Hatchling)
└── README.md                    # Dokumentasi Ringkas Proyek
```

### Fitur-Fitur Inti yang Sudah Aktif:
1. **System Doctor (`winebox system doctor`):** Memeriksa otomatis kesiapan kernel, bwrap, wine, display, audio, dan GPU.
2. **Isolasi Penuh Sandboxed:** Tidak ada proses Wine yang berjalan di luar Bubblewrap.
3. **Isolasi HOME Per Prefix:** Setiap prefix memiliki folder home privat di `prefixes/<id>/home/`.
4. **Sanitasi Drive Z Otomatis:** Symlink `dosdevices/z:` yang mengarah ke root host langsung dinetralkan sebelum eksekusi.
5. **Anti-Korupsi Registry (`prefix.lock`):** Menggunakan kernel lock `fcntl.flock` agar dua aplikasi di prefix yang sama tidak merusak file registry.
6. **Profil Keamanan Interaktif (`winebox profile`):** Pengelolaan level izin hardware (paranoid, zero-trust, balanced, permissive, custom) dengan wizard terminal.
7. **Log File Terotasi Otomatis (`winebox prefix logs`):** Output log berisik Wine dialirkan ke file 5MB dengan 3 cadangan otomatis per prefix (tidak membebani disk).
8. **Snapshot Portabilitas (`metadata.json`):** Setiap prefix memiliki snapshot metadata lokal otomatis untuk pemulihan bencana jika data terhapus.
9. **Normalisasi Jalur Windows:** Mendukung path Windows (`C:\...`) maupun path relatif (`drive_c/...`).
10. **Bantuan Lengkap (`winebox help [topik]`):** Navigasi bantuan ramah pengguna untuk setiap sub-perintah.

---

## 3. Daftar Lengkap Perintah WineBox (Command Cheat Sheet)

| Perintah | Deskripsi |
|---|---|
| **Bantuan & Diagnosa** | |
| `winebox help [topik]` | Menampilkan bantuan umum atau bantuan sub-perintah (`prefix`, `app`, `profile`, dll.). |
| `winebox system doctor` | Memeriksa kesiapan dependensi sistem host (bwrap, wine, userns, GPU, audio, display). |
| `winebox system version` | Menampilkan versi WineBox saat ini. |
| **Manajemen Prefix** | |
| `winebox prefix list` | Menampilkan tabel semua prefix Wine yang terdaftar. |
| `winebox prefix create <id> [--name] [--runner] [--network/--no-network]` | Membuat prefix baru dan menginisialisasi Wine di dalam sandbox. |
| `winebox prefix audit <id>` | Memindai keamanan prefix (cek symlink escaping & mapping drive Z:). |
| `winebox prefix logs <id> [--lines 50]` | Menampilkan baris log eksekusi terakhir dari file terotasi. |
| `winebox prefix remove <id> [--force]` | Menghapus prefix beserta seluruh datanya. |
| **Profil Keamanan (Security Profiles)** | |
| `winebox profile list` | Menampilkan tabel preset profil keamanan (`Display`, `Audio`, `Network`, `GPU`, `Type`). |
| `winebox profile create` | Wizard interaktif terminal untuk membuat profil keamanan baru. |
| `winebox profile edit <id>` | Mengedit izin hardware dari profil keamanan yang sudah ada. |
| `winebox profile remove <id>` | Menghapus profil kustom (ditolak jika sedang digunakan oleh aplikasi/prefix). |
| **Manajemen & Eksekusi Aplikasi** | |
| `winebox app list` | Menampilkan daftar aplikasi terdaftar beserta `Profile` dan status `Last Run`. |
| `winebox app run <app_id> [-- argumen]` | Menjalankan aplikasi Windows di dalam sandbox aman. |
| `winebox app info <app_id>` | Menampilkan detail konfigurasi dan kebijakan keamanan aplikasi. |
| `winebox app register --id <id> --name <nama> --prefix <prefix> --exe <path> [--profile <prof>]` | Mendaftarkan executable yang ada di dalam prefix secara manual. |
| `winebox app remove <app_id>` | Menghapus registrasi aplikasi (tanpa menghapus prefix/data aplikasi). |
| **Instalasi & Import** | |
| `winebox install <installer.exe/msi>` | Wizard interaktif untuk memasang installer Windows ke dalam sandbox. |
| `winebox import app <dir> --prefix <p> --id <i> --name <n> --exe <e>` | Mengimpor folder aplikasi/game portable langsung ke prefix. |
| `winebox import prefix <dir> --id <id> [--name <n>]` | Mengimpor Wine Prefix lama dari luar (cloning, sanitasi, dan audit). |
| **Manajemen Wine Runner** | |
| `winebox runner list` | Menampilkan daftar runner Wine yang tersedia (`system-wine` default). |
| `winebox runner register <id> --name <nama> --wine <path> [--wineserver <path>]` | Mendaftarkan runner Wine kustom (misal: GE-Proton / Lutris runner). |

---

## 4. Panduan Penggunaan Praktis Langkah demi Langkah

Pastikan virtual environment aktif:
```bash
cd /home/choco/Project/www/Winebox
source .venv/bin/activate
```

---

### Langkah 1: Cek Kesiapan Sistem (`doctor`)
Sebelum mulai, pastikan distro Linux Anda memenuhi seluruh prasyarat:
```bash
winebox system doctor
```
*Output: Memeriksa Bubblewrap, User Namespaces, Wine binary, Display X11/Wayland, Audio Pulse/PipeWire, dan GPU DRI.*

---

### Langkah 2: Mengatur Profil Keamanan (`profile`)
Profil keamanan menentukan perangkat keras apa saja yang boleh diakses oleh aplikasi Windows.

```bash
# 1. Melihat profil yang tersedia (bawaan: paranoid, zero-trust, balanced, permissive)
winebox profile list

# 2. Membuat profil kustom baru secara interaktif
winebox profile create
# Terminal akan menanyakan ID, nama, serta konfirmasi izin (Display, Audio, Network, GPU).

# 3. Mengedit profil yang sudah ada
winebox profile edit permissive
```

---

### Langkah 3: Membuat Lingkungan Windows (Prefix)
Prefix adalah "wadah Windows mandiri" yang memiliki registry dan folder `C:` sendiri.

```bash
# Membuat prefix baru bernama 'gaming' (mengizinkan koneksi internet saat wineboot)
winebox prefix create gaming --name "Lingkungan Game"

# Melihat daftar prefix yang sudah dibuat
winebox prefix list

# Menjalankan audit keamanan (memastikan tidak ada symlink berbahaya yang keluar ke host)
winebox prefix audit gaming
```

File prefix disimpan rapi di:
`~/.local/share/winebox/prefixes/gaming/`

---

### Langkah 4: Memasang Aplikasi Windows

#### Opsi A: Menggunakan Installer (`.exe` atau `.msi`)
```bash
winebox install /path/ke/installer.exe
```
Alur wizard interaktif:
1. Meminta Anda memilih prefix tujuan (atau membuat prefix baru langsung).
2. Menanyakan izin internet (apakah installer boleh akses internet).
3. Mengeksekusi installer di dalam sandbox Bubblewrap secara aman (folder installer di host di-mount *Read-Only*).
4. Setelah instalasi selesai, WineBox otomatis memindai file `.exe` yang baru terpasang di `Program Files`.
5. Anda cukup memilih file `.exe` mana yang ingin didaftarkan sebagai shortcut aplikasi.

#### Opsi B: Memasang Aplikasi Portable (Folder Tanpa Installer)
Jika Anda punya folder game atau software portable:
```bash
winebox import app /path/ke/folder_aplikasi \
  --prefix gaming \
  --id notepad-plus \
  --name "Notepad++ Portable" \
  --exe "notepad++.exe"
```
Folder akan diaudit symlink-nya, disalin ke `drive_c/Program Files/notepad-plus/` di dalam prefix, dan didaftarkan otomatis.

---

### Langkah 5: Menjalankan Aplikasi (`run`)
Jalankan aplikasi yang sudah terdaftar kapan saja:
```bash
# Menjalankan aplikasi
winebox app run notepad-plus

# Menjalankan aplikasi dengan argumen baris perintah
winebox app run notepad-plus -- "dokumen.txt"
```

---

### Langkah 6: Memantau Log Eksekusi & Status Aplikasi
WineBox mencatat status eksekusi dan memutar file log secara otomatis:

```bash
# Melihat status lari terakhir semua aplikasi (menampilkan Exit 0 / Exit 1 dan waktu eksekusi)
winebox app list

# Melihat 50 baris terakhir log eksekusi prefix
winebox prefix logs gaming

# Melihat 100 baris log terakhir
winebox prefix logs gaming --lines 100
```

---

### Langkah 7: Mendaftarkan Executable Manual (`register`)
Jika aplikasi sudah ada di dalam prefix dan Anda ingin membuat shortcut baru:
```bash
winebox app register \
  --id cmd \
  --name "Command Prompt" \
  --prefix gaming \
  --exe "drive_c/windows/system32/cmd.exe" \
  --profile permissive
```

---

### Langkah 8: Mengimpor Wine Prefix Lama (`import prefix`)
Jika Anda memiliki prefix Wine lama dari Lutris, Bottles, atau Wine manual:
```bash
winebox import prefix /path/ke/prefix_lama \
  --id imported-daw \
  --name "DAW Studio Lama"
```
WineBox secara otomatis:
- Menetralkan symlink `dosdevices/z:` yang menunjuk ke root host `/`.
- Mengaudit integritas file dan symlink.
- Membangun virtual HOME privat dan file lock `prefix.lock`.

---

## 5. Lokasi Penyimpanan Data di Komputer Anda

WineBox beroperasi dalam mode **Rootless** (tidak memerlukan izin `sudo`):
- **Database Konfigurasi:** `~/.local/share/winebox/winebox.db`
- **Lingkungan Windows & Aplikasi:** `~/.local/share/winebox/prefixes/<id>/`
  - `prefix/`: Folder `drive_c` dan registry Windows.
  - `home/`: Virtual HOME pengguna Linux privat.
  - `logs/execution.log`: File log terotasi otomatis (maksimal 5MB, 3 cadangan).
  - `metadata.json`: Snapshot lokal untuk pemulihan bencana (*disaster recovery*).
  - `prefix.lock`: Pengunci konkurensi antar-proses.
- **Konfigurasi Global:** `~/.config/winebox/config.toml`

Jika ingin membersihkan seluruh data WineBox, cukup hapus folder `~/.local/share/winebox/`.
