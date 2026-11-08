# Threat Model and Security Architecture

## 1. Prinsip Keamanan Inti

- **Default-Deny:** Akses ke filesystem host, perangkat keras, atau jaringan dilarang kecuali diizinkan secara eksplisit oleh kebijakan keamanan.
- **Hardware Allowed, Host Filesystem Denied:** Akses display, audio, dan GPU diizinkan untuk kegunaan desktop Windows, namun seluruh filesystem pribadi host diblokir rapat.
- **No Sandbox, No Execution:** Tidak ada proses Wine yang boleh berjalan langsung di sistem host.

---

## 2. Batas Keamanan (Security Boundaries)

Batas keamanan WineBox ditegakkan oleh kombinasi:
1. **Linux Namespaces (Bubblewrap):**
   - User Namespace: Mencegah eskalasi hak istimewa di host.
   - PID Namespace: Proses Windows tidak dapat melihat atau mengirim sinyal ke proses lain di host.
   - Mount Namespace: Filesystem host digantikan dengan virtual view minimal.
   - IPC & UTS Namespace: Mengisolasi komunikasi inter-proses dan hostname sistem.
   - Network Namespace: Dipisahkan kecuali jika izin jaringan diaktifkan.
2. **Filesystem Isolation:**
   - Direktori pengguna host (`$HOME`, `~/.ssh`, `~/.config`, dsb.) tidak di-mount.
   - Virtual `$HOME` privat per prefix disediakan di `prefixes/<id>/home/`.
   - Host runtime (`/usr`, `/lib*`, `/etc/ld.so*`) hanya di-mount secara **Read-Only**.
3. **Prefix Sanitation:**
   - Audit rekursif terhadap symlink sebelum prefix atau aplikasi dijalankan.
   - Penonaktifan drive `Z:` Wine yang mengarah ke root filesystem host.

---

## 3. Matriks Ancaman dan Mitigasi

| Ancaman | Deskripsi Risiko | Mekanisme Mitigasi WineBox |
|---|---|---|
| **Pencurian Data Host** | Malware Windows membaca file sensitif (`~/.ssh`, cookies browser, dokumen pribadi). | Host `$HOME` tidak di-mount sama sekali. Sandbox hanya melihat virtual HOME privat prefix. |
| **Symlink Traversal Escape** | Installer atau aplikasi membuat symlink mengarah ke `/etc/passwd` atau file host di luar sandbox. | `PrefixAuditor` memindai dan memverifikasi `realpath` semua symlink. Symlink escaping ditolak. |
| **Drive Z: Escape** | Wine secara default memetakan drive `Z:` ke `/` (root host). | Konfigurasi Wine dosdevices dibersihkan, `Z:` dinonaktifkan atau dibatasi ke view sandbox. |
| **Tampering Host via D-Bus** | Aplikasi berkomunikasi dengan session D-Bus host untuk memicu eksekusi kode (eksploitasi portal/systemd). | Socket session D-Bus host (`/run/user/<uid>/bus`) diblokir dari dalam sandbox. |
| **Eskalasi Root Privilege** | Aplikasi mencoba mengeksploitasi biner setuid atau namespace kernel. | Bubblewrap dijalankan dengan flag `--unshare-user` dan mematikan bit setuid (`--new-session` / `PR_SET_NO_NEW_PRIVS`). |
| **Eksfiltrasi Jaringan** | Aplikasi tak tepercaya mengirimkan data keluar tanpa sepengetahuan pengguna. | Kebijakan jaringan biner (`network = false` secara default pada profil terisolasi). |
| **Korupsi Multi-Instance** | Dua proses aplikasi pada prefix yang sama merusak file registry `system.reg`. | Single-instance lock (`prefix.lock` berbasis `flock`) menolak eksekusi simultan di prefix yang sama. |

---

## 4. Batasan (Known Limitations & Residual Risks)

- **X11 Keylogger Risk:** Karena MVP menggunakan passthrough socket X11 standar host (demi performa dan kesederhanaan tanpa nested X server), aplikasi yang memiliki izin `display = true` pada sesi X11 host secara teoritis dapat merekam keystroke sesi X11. Pengguna disarankan menggunakan sesi Wayland (XWayland) untuk mitigasi alami.
- **Kernel Exploits:** Sandbox Bubblewrap tidak dapat melindungi host jika aplikasi Windows memicu exploit 0-day pada subsistem kernel Linux (seperti driver GPU proprietary atau kernel bug).

