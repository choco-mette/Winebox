# ADR-012: Isolasi Namespace Bubblewrap dan Validasi Fail-Fast

## Status
Accepted

## Konteks
Bubblewrap mengandalkan Linux namespaces untuk isolasi. Beberapa distribusi Linux membatasi atau menonaktifkan unprivileged user namespaces via sysctl (`kernel.unprivileged_userns_clone=0`) atau konfigurasi AppArmor. Jika WineBox mencoba menjalankan bwrap tanpa verifikasi, proses dapat gagal tanpa pesan kesalahan yang informatif. Selain itu, Wine membutuhkan pustaka sistem host (`/usr/lib`, `/lib64`, `/etc/ld.so*`) untuk berjalan.

## Keputusan
1. Bubblewrap dijalankan dengan konfigurasi namespace ketat: `--unshare-all` (mengisolasi user, pid, ipc, uts, cgroup), dan namespace network diisolasi secara dinamis sesuai policy.
2. Mount direktori sistem host dilakukan secara minimal dan wajib read-only (`--ro-bind /usr /usr`, `--ro-bind-try /lib /lib`, `--ro-bind-try /lib64 /lib64`, `--ro-bind /etc/ld.so.cache /etc/ld.so.cache`, `--ro-bind-try /etc/ld.so.conf /etc/ld.so.conf`).
3. Menerapkan mekanisme validasi cepat (fail-fast guard): saat startup, WineBox melakukan uji coba container dummy bwrap singkat. Jika user namespace tidak tersedia atau bwrap gagal, proses langsung dihentikan dengan pesan error jelas yang mengarahkan ke solusi konfigurasi sistem.

## Konsekuensi
### Positif
- Tingkat isolasi sandbox maksimal sedini mungkin.
- Diagnosa masalah lingkungan jelas dan tidak membingungkan pengguna jika host mereka memblokir user namespaces.

### Negatif / Mitigasi
- Membutuhkan kernel Linux yang mengaktifkan user namespaces (Linux >= 5.4 standar pada distro modern).

