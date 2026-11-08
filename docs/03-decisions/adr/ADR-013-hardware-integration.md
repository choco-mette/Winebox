# ADR-013: Integrasi Hardware: X11, Audio, dan GPU Passthrough

## Status
Accepted

## Konteks
Sebagian besar aplikasi Windows (software grafis, editor audio, game) membutuhkan tampilan GUI, output suara, dan akselerasi GPU perangkat keras. Isolasi ketat tanpa akses hardware menyebabkan aplikasi gagal render atau tidak bersuara. Di sisi lain, isolasi total X11 (seperti nested server Xephyr/gamescope) menambah kompleksitas dependensi.

## Keputusan
Untuk MVP, WineBox menerapkan pendekatan integrasi desktop standar (serupa Flatpak):
1. **Display (X11 / XWayland):** Me-mount socket X11 host (`/tmp/.X11-unix/X*`) dan menyalin file otentikasi `XAUTHORITY` ke dalam sandbox saat izin display aktif.
2. **Audio:** Me-mount socket PulseAudio/PipeWire pengguna (`/run/user/<uid>/pulse/native` atau `/run/user/<uid>/pipewire-0`) ke dalam sandbox saat izin audio aktif.
3. **GPU:** Me-mount perangkat render kernel `/dev/dri` secara langsung ke dalam sandbox saat izin GPU aktif.
4. X11 nested server isolation dan manajemen USB device passthrough ditunda ke fase post-MVP.

## Konsekuensi
### Positif
- Kompatibilitas tinggi: aplikasi desktop Windows dan game dapat langsung menampilkan jendela, merender 3D/Vulkan via driver DRI, dan mengeluarkan suara.
- Tidak membutuhkan instalasi server display sekunder.

### Negatif / Mitigasi
- X11 pada dasarnya tidak memiliki isolasi antar-window (aplikasi di dalam sandbox secara teoretis dapat membaca keystroke jendela X11 lain). Solusi isolasi nested server dicatat sebagai roadmap keamanan di masa mendatang.

