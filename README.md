# WineBox

Orchestrator keamanan untuk mengelola dan menjalankan aplikasi Windows di Linux melalui Wine dengan isolasi Bubblewrap (`bwrap`).

## Prinsip Utama
- **Hardware Allowed, Host Filesystem Denied**
- **Isolated by Default. Hardware Access by Policy.**
- **No Sandbox, No Execution.**

---

## Prasyarat Sistem
- **OS:** Distribusi Linux modern (Ubuntu/Debian, Fedora, Arch) dengan kernel >= 5.4.
- **Unprivileged User Namespaces:** Aktif pada host.
- **Bubblewrap:** Biner `bwrap` terpasang di host (`sudo apt install bubblewrap` / `pacman -S bubblewrap`).
- **Wine:** Biner `wine` terpasang di host (`sudo apt install wine` / `pacman -S wine`).
- **Python:** Python >= 3.11.

---

## Instalasi

### Dari Repositori Lokal
```bash
# Buat virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install WineBox dalam mode editable
pip install -e .
```

---

## Panduan Penggunaan CLI

### 1. Bantuan Perintah (`help`)
Tampilkan panduan dan opsi perintah kapan saja:
```bash
# Menampilkan bantuan umum & daftar seluruh perintah
winebox help

# Menampilkan bantuan terperinci per sub-perintah
winebox help prefix
winebox help app
winebox help install
winebox help import
winebox help runner
winebox help system
```

---

### 2. Diagnosa Kesiapan Sistem (`doctor`)
Periksa kesiapan dependensi sistem (bwrap, wine, userns, display, audio, GPU):
```bash
winebox system doctor
```
Jika ada kendala (misal user namespaces dibatasi), doctor memberikan rekomendasi langkah perbaikan.

---

### 3. Mengelola Wine Prefix
Wine Prefix adalah lingkungan Windows virtual terisolasi. WineBox mengisolasi direktori `$HOME` host dan membuat virtual HOME privat per prefix.

```bash
# Membuat prefix baru (sekaligus inisialisasi wineboot di dalam sandbox)
winebox prefix create gaming --name "Gaming Environment"

# Membuat prefix tanpa inisialisasi wineboot (cepat)
winebox prefix create minimal-prefix --no-wineboot

# Melihat daftar semua prefix
winebox prefix list

# Menjalankan audit keamanan prefix (memeriksa symlink escape & drive Z:)
winebox prefix audit gaming

# Menghapus prefix beserta datanya
winebox prefix remove gaming
```

---

### 4. Memasang Aplikasi Windows (`install`)
Jalankan wizard instalasi interaktif untuk file installer `.exe` atau `.msi`:
```bash
winebox install /path/to/installer.exe
```
Wizard akan:
1. Meminta Anda memilih prefix tujuan (atau membuat prefix baru).
2. Mengonfigurasi izin akses jaringan (network).
3. Mengeksekusi installer di dalam sandbox Bubblewrap secara aman (direktori sumber di-mount read-only).
4. Menetralkan mapping drive berbahaya (`Z:`).
5. Memindai otomatis biner `.exe` baru yang berhasil dipasang dan menawarkan pendaftaran aplikasi.

---

### 5. Menjalankan & Mengelola Aplikasi (`app`)

```bash
# Menjalankan aplikasi Windows di dalam sandbox
winebox app run <app_id>

# Menjalankan aplikasi dengan argumen tambahan
winebox app run <app_id> -- --option argument

# Melihat daftar aplikasi terdaftar
winebox app list

# Melihat detail konfigurasi & kebijakan keamanan aplikasi
winebox app info <app_id>

# Mendaftarkan executable yang sudah ada di dalam prefix secara manual
winebox app register \
  --id notepad \
  --name "Wine Notepad" \
  --prefix gaming \
  --exe "drive_c/windows/notepad.exe"

# Menghapus registrasi aplikasi (tanpa menghapus prefix)
winebox app remove notepad
```

---

### 6. Mengimpor Aplikasi Portable (`import app`)
Salin folder aplikasi portable Windows ke dalam prefix tanpa perlu installer:
```bash
winebox import app /path/to/portable_folder \
  --prefix gaming \
  --id my-editor \
  --name "Portable Code Editor" \
  --exe "editor.exe"
```
WineBox akan:
- Mengkloning folder ke staging sementara.
- Memindai symlink untuk memastikan tidak ada link yang keluar ke filesystem host.
- Memindahkan aplikasi ke `drive_c/Program Files/my-editor/` di prefix target secara atomik.

---

### 7. Mengimpor Wine Prefix Eksternal (`import prefix`)
Migrasi prefix lama (dari Lutris, Bottles, atau Wine manual) ke lingkungan aman WineBox:
```bash
winebox import prefix /path/to/old_prefix \
  --id imported-daw \
  --name "DAW Audio Suite"
```
WineBox secara otomatis:
- Menetralkan symlink `dosdevices/z:` yang menunjuk ke root host `/`.
- Mengaudit integritas registry dan symlink.
- Membangun isolasi virtual HOME privat dan file lock `prefix.lock`.

---

### 8. Mengelola Runner Wine (`runner`)

```bash
# Melihat daftar runner yang tersedia (System Wine default)
winebox runner list

# Mendaftarkan runner Wine custom
winebox runner register custom-proton \
  --name "GE-Proton Custom" \
  --wine /path/to/runner/bin/wine \
  --wineserver /path/to/runner/bin/wineserver
```

---

## Struktur Direktori Data (Standar XDG)

Semua data dan konfigurasi WineBox tersimpan rapi di direktori pengguna (Rootless):
- **Data:** `~/.local/share/winebox/`
  - `applications/<app-id>.toml`: Metadata aplikasi terdaftar.
  - `prefixes/<prefix-id>/`: Lingkungan Wine (`prefix/`, `home/`, `config.toml`, `prefix.lock`).
  - `runners/`: Registrasi custom runner.
  - `staging/`: Area kerja sementara untuk clone & audit.
- **Konfigurasi Global:** `~/.config/winebox/config.toml`

---

## Dokumentasi Teknis
- [SAD.md](SAD.md): Software Architecture Document lengkap.
- [docs/03-decisions/adr/](docs/03-decisions/adr/): 19 Architecture Decision Records (ADR).
- [docs/04-security/threat-model.md](docs/04-security/threat-model.md): Model ancaman dan arsitektur keamanan.
- [docs/05-specifications/](docs/05-specifications/): Spesifikasi teknis sandbox, deployment, prefix, runner, config, dan CLI.

---

## Lisensi
MIT
