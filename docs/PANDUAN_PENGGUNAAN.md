# Panduan Lengkap dan Penjelasan Proyek WineBox

Dokumen ini menjelaskan secara menyeluruh tentang apa itu **WineBox**, bagaimana cara kerjanya, status progress pengembangan yang sudah selesai, serta panduan praktis penggunaannya dari awal hingga akhir.

---

## 1. Apa itu WineBox?

### Masalah Utama yang Diselesaikan
Di Linux, kita biasa menjalankan software Windows menggunakan **Wine**. Namun, Wine bawaan memiliki risiko keamanan yang besar:
1. **Akses File Tanpa Batas:** Secara default, aplikasi Windows yang berjalan di Wine dapat membaca seluruh isi folder pengguna host (`/home/user/`), termasuk berkas sensitif seperti SSH keys (`~/.ssh`), riwayat browser, cookies, dan dokumen pribadi.
2. **Drive `Z:` yang Berbahaya:** Wine secara default memetakan drive `Z:` ke direktori root host (`/`). Jika aplikasi Windows terkena malware, malware tersebut bisa mengacak-acak file Linux Anda.
3. **Pencemaran Direktori:** Wine sering membuat folder dan file konfigurasi acak di `$HOME` Anda.

### Solusi WineBox
**WineBox adalah orchestrator keamanan** yang menggabungkan **Wine** dengan **Bubblewrap (`bwrap`)**.

Bubblewrap bertindak seperti "kandang kaca" (sandbox berbasis Linux Namespaces). Di dalam kandang ini:
- **Aplikasi Windows DIBERI akses perangkat keras:** Layar (Display X11/Wayland), Suara (Audio PulseAudio/PipeWire), Akselerasi 3D (GPU `/dev/dri`), dan Internet.
- **Aplikasi Windows DITOLAK total dari filesystem pribadi host:** Aplikasi tidak bisa melihat folder `/home/user/` Anda. Setiap prefix memiliki folder "Home virtual palsu" sendiri.
- Prinsip utama: **"Hardware Allowed, Host Filesystem Denied"** & **"No Sandbox, No Execution"**.

---

## 2. Rangkuman Progress yang Sudah Selesai Dibuat

Semua fondasi arsitektur, kode inti MVP, dan antarmuka CLI telah selesai diimplementasikan:

```
Winebox/
├── docs/                        # Dokumentasi Lengkap
│   ├── 01-project/              # Visi & Batasan Cakupan
│   ├── 02-architecture/         # Diagram & Desain Modular
│   ├── 03-decisions/adr/        # 19 Keputusan Arsitektural Resmi (ADR-001 s/d ADR-019)
│   ├── 04-security/             # Threat Model & Analisis Ancaman
│   ├── 05-specifications/       # Spesifikasi Teknis (Sandbox, Prefix, Runner, CLI)
│   └── 06-development/          # Standar Coding, Setup, & Rilis
│
├── src/winebox/                 # Source Code Python (Modular Layered Architecture)
│   ├── common/                  # System Doctor & Exception Hierarchy
│   ├── domain/                  # Entitas Inti (Application, Prefix, Runner, SecurityPolicy)
│   ├── security/                # PolicyValidator, PrefixAuditor, MountBuilder
│   ├── infrastructure/          # BwrapAdapter, WineAdapter, ProcessManager, ConfigRepository
│   ├── application/             # Use Case Services (Prefix, App, Runner, Install, Import)
│   └── interface/               # CLI Modern (Typer + Rich)
│
├── tests/                       # Test Suite Otomatis
│   ├── unit/                    # 26 Unit Test (Security, Services, Config, Concurrency)
│   └── integration/             # 3 Integration Test (Live Bubblewrap Sandbox di Kernel Host)
│
├── pyproject.toml               # Standar Packaging Modern PEP 621 (Hatchling)
└── README.md                    # Dokumentasi Ringkas Proyek
```

### Fitur-Fitur Inti yang Sudah Aktif:
1. **System Doctor (`winebox system doctor`):** Memeriksa otomatis kesiapan kernel, bwrap, wine, display, audio, dan GPU pada distro Linux Anda.
2. **Isolasi Penuh Sandboxed:** Tidak ada proses Wine yang berjalan di luar Bubblewrap.
3. **Isolasi HOME Per Prefix:** Setiap prefix memiliki folder home privat di `prefixes/<id>/home/`.
4. **Sanitasi Drive Z Otomatis:** Symlink `dosdevices/z:` yang mengarah ke root host langsung dinetralkan otomatis sebelum eksekusi.
5. **Anti-Korupsi Registry (`prefix.lock`):** Menggunakan `fcntl.flock` kernel agar dua aplikasi di prefix yang sama tidak merusak file registry.
6. **Normalisasi Jalur Windows:** Mendukung path Windows (`C:\...`) maupun path relatif (`drive_c/...`).
7. **Dukungan Sertifikat SSL & Jaringan:** HTTPS dan verifikasi sertifikat SSL berfungsi di dalam container.
8. **Bantuan Interaktif (`winebox help [topik]`):** Navigasi perintah ramah pengguna.

---

## 3. Panduan Penggunaan Langkah demi Langkah

Pastikan virtual environment aktif sebelum menjalankan perintah:
```bash
cd /home/choco/Project/www/Winebox
source .venv/bin/activate
```

---

### Langkah 1: Cek Kesiapan Sistem
Periksa apakah distro Linux Anda siap menjalankan sandbox:
```bash
winebox system doctor
```
*Output yang diharapkan: Semua indikator bernilai `[PASS]` berwarna hijau.*

---

### Langkah 2: Membuat Environment Windows Baru (Prefix)
Prefix adalah "komputer Windows virtual" terisolasi.

```bash
# Membuat prefix bernama 'gaming' (otomatis inisialisasi Wine di dalam sandbox)
winebox prefix create gaming --name "Lingkungan Game"

# Melihat daftar prefix yang sudah ada
winebox prefix list

# Memeriksa keamanan prefix (memastikan tidak ada kebocoran symlink ke file host)
winebox prefix audit gaming
```

File prefix akan disimpan rapi di:
`~/.local/share/winebox/prefixes/gaming/`

---

### Langkah 3: Menginstal Aplikasi dari Installer Windows (`.exe` atau `.msi`)
Gunakan wizard instalasi interaktif:
```bash
winebox install /path/ke/installer.exe
```
Alur wizard:
1. Wizard akan menampilkan daftar prefix yang tersedia atau menawarkan pembuatan prefix baru.
2. Menanyakan izin internet (apakah installer boleh akses internet).
3. Menjalankan installer di dalam sandbox aman (folder installer di host di-mount *Read-Only*).
4. Setelah instalasi selesai, WineBox otomatis memindai file `.exe` yang baru terpasang di `Program Files`.
5. Anda cukup memilih file `.exe` mana yang ingin didaftarkan sebagai shortcut aplikasi.

---

### Langkah 4: Memasang Aplikasi Portable (Tanpa Installer)
Jika Anda memiliki folder game atau aplikasi portable:
```bash
winebox import app /path/ke/folder_aplikasi \
  --prefix gaming \
  --id notepad-plus \
  --name "Notepad++ Portable" \
  --exe "notepad++.exe"
```
WineBox akan:
- Meng-copy folder tersebut ke staging sementara.
- Memindai semua file untuk memastikan tidak ada symlink berbahaya yang keluar ke host.
- Memindahkannya ke `drive_c/Program Files/notepad-plus/` di dalam prefix target.
- Mendaftarkannya ke daftar aplikasi WineBox.

---

### Langkah 5: Menjalankan Aplikasi
Setelah aplikasi terdaftar, jalankan kapan saja dengan ID-nya:
```bash
# Menjalankan aplikasi
winebox app run notepad-plus

# Menjalankan aplikasi dengan parameter tambahan
winebox app run notepad-plus -- "dokumen.txt"
```

---

### Langkah 6: Mengelola Aplikasi
```bash
# Melihat daftar semua aplikasi yang terdaftar
winebox app list

# Melihat detail kebijakan keamanan (apakah display, audio, GPU, internet aktif)
winebox app info notepad-plus

# Mendaftarkan executable yang sudah ada di dalam prefix secara manual
winebox app register \
  --id cmd \
  --name "Command Prompt" \
  --prefix gaming \
  --exe "drive_c/windows/system32/cmd.exe"

# Menghapus pendaftaran aplikasi (data di dalam prefix tetap aman)
winebox app remove cmd
```

---

### Langkah 7: Melihat Bantuan Kapan Saja
```bash
winebox help           # Bantuan umum
winebox help prefix    # Bantuan perintah prefix
winebox help app       # Bantuan perintah app
winebox help install   # Bantuan perintah install
winebox help import    # Bantuan perintah import
winebox help runner    # Bantuan perintah runner
winebox help system    # Bantuan perintah system doctor
```

---

## 4. Lokasi Penyimpanan Data di Komputer Anda

WineBox beroperasi dalam mode **Rootless** (tidak butuh `sudo`):
- **Data Prefix & Aplikasi:** `~/.local/share/winebox/`
  - `prefixes/<id>/`: Tempat Windows virtual berada (`drive_c`, registry, dan virtual HOME).
  - `applications/<id>.toml`: File konfigurasi shortcut aplikasi.
  - `runners/`: Tempat registrasi Wine runner khusus.
- **Konfigurasi Global:** `~/.config/winebox/config.toml`

Jika ingin menghapus total data WineBox, cukup hapus folder `~/.local/share/winebox/`.
