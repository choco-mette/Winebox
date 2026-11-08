# Vision and Scope

## 1. Vision

Membangun platform pengelolaan aplikasi Windows di Linux yang mengutamakan isolasi, keamanan, kemudahan pengelolaan, dan fleksibilitas konfigurasi.

Prinsip utama:
- **Hardware Allowed, Host Filesystem Denied**
- **Isolated by Default. Hardware Access by Policy.**
- **No Sandbox, No Execution.**

WineBox bukan pengganti Wine maupun Bubblewrap, melainkan orchestrator yang mengatur konfigurasi, lifecycle, dan kebijakan keamanan keduanya.

---

## 2. Objectives (Tujuan)

1. Menjalankan aplikasi Windows melalui Wine di dalam sandbox Bubblewrap.
2. Mengisolasi data aplikasi dari filesystem pribadi pengguna host (`$HOME`).
3. Mengelola Wine Prefix secara terpusat (multi-aplikasi per prefix didukung).
4. Mendukung instalasi aplikasi melalui installer Windows (`.exe`, `.msi`).
5. Mendukung import aplikasi portable.
6. Mendukung import Wine Prefix eksternal (dengan mekanisme clone, sanitize, dan audit).
7. Mengelola runner Wine (System Wine default dan custom runner path).
8. Mengatur akses perangkat keras (display X11, audio PulseAudio/PipeWire, GPU) berdasarkan kebijakan keamanan terkontrol.
9. Menyediakan antarmuka CLI modern berbasis Typer dan Rich.
10. Menyediakan landasan arsitektur berlapis untuk pengembangan GUI di masa mendatang.
11. Menyediakan audit dan logging terhadap aktivitas aplikasi.

---

## 3. Non-Goals (Bukan Tujuan)

WineBox tidak bertujuan untuk:
- Menggantikan Wine atau Bubblewrap.
- Menjadi hypervisor atau virtual machine manager (tidak ada emulasi hardware VM).
- Memberikan proteksi setara VM terhadap seluruh kernel exploit host.
- Menjadi antivirus atau automated malware analysis sandbox.
- Menjamin 100% kompatibilitas seluruh aplikasi Windows di Linux (bergantung pada Wine).
- Menyediakan compatibility layer buatan sendiri.
- Mengelola seluruh paket dan dependensi sistem Linux host.
- Memberikan akses filesystem host tanpa batas.

---

## 4. Scope Target Rilis (MVP)

### Dalam Cakupan (In Scope)
- Target OS: Linux modern berbasis systemd dengan unprivileged user namespaces aktif.
- Antarmuka: CLI (`winebox`) dengan interactive wizard dan diagnostic tool (`winebox system doctor`).
- Runner: System Wine (`/usr/bin/wine`) + custom extracted runner path.
- Isolasi: Bubblewrap strict namespaces (`--unshare-all`), HOME isolasi per prefix.
- Hardware: Passthrough display X11/XWayland, audio PulseAudio/PipeWire, dan `/dev/dri` GPU.
- Jaringan: Kebijakan biner (`network = true | false`).
- Penyimpanan: Rootless user mode berbasis XDG (`~/.local/share/winebox/` dan `~/.config/winebox/`).
- Eksekusi: Single-instance prefix lock (`prefix.lock`).

### Di Luar Cakupan MVP (Post-MVP Roadmap)
- Antarmuka grafis (GUI desktop app).
- Auto-downloader runner online (GE-Proton, Lutris runner).
- X11 nested server (gamescope/Xephyr) untuk isolasi windowing tingkat tinggi.
- Filtering jaringan berbasis domain/proxy lokal (Restricted network).
- Penyimpanan multi-tenant sistem (`/var/lib/winebox`).
- Paket native OS distro (`.deb`, `.rpm`, Flatpak bundle).
