# ADR-017: Kebijakan Default: Hardware Allowed, Host Filesystem Denied

## Status
Accepted

## Konteks
Tujuan WineBox adalah memberikan pengalaman pengguna yang mulus saat menjalankan aplikasi Windows di Linux tanpa mengorbankan privasi data host. Jika semua izin hardware (display, suara, internet, GPU) dimatikan secara default (zero-trust), pengguna pemula akan mengalami kegagalan aplikasi seperti blank screen, silent crash tanpa suara, atau error koneksi yang membingungkan.

## Keputusan
Menetapkan profil kebijakan keamanan default (baseline profile) saat aplikasi baru didaftarkan atau diinstal:
- `display = true` (Akses ke display X11).
- `audio = true` (Akses ke socket suara PulseAudio/PipeWire).
- `network = true` (Akses internet/jaringan aktif).
- `gpu = true` (Akses akselerasi grafis `/dev/dri` aktif).
- **Filesystem Host:** Diblokir 100% secara default (tidak ada akses ke `$HOME` pengguna, SSH keys, file konfigurasi host, maupun arbitrary host paths).

Pengguna tetap dapat memperketat izin (misalnya mematikan network atau audio) melalui konfigurasi file profil atau flag CLI.

## Konsekuensi
### Positif
- Filosofi *Hardware Allowed, Host Filesystem Denied* terwujud: aplikasi langsung bekerja dengan baik (*out-of-the-box*) sambil menjaga data pribadi host tetap terisolasi rapat.
- Mengurangi friksi konfigurasi awal bagi pengguna awam.

### Negatif / Mitigasi
- Aplikasi Windows dapat mengakses jaringan dan GPU host secara default. Pengguna yang menginginkan isolasi ekstrem dapat mengubah profil ke mode restricted secara manual.

