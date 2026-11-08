# ADR-008: Deployment Aplikasi Portable Menggunakan Copy ke Prefix

## Status
Accepted

## Konteks
Aplikasi Windows tipe portable (koleksi file biner mandiri tanpa wizard instalasi) perlu dijalankan di dalam lingkungan Wine Prefix. Menjaga file portable di luar prefix dan me-mount-nya secara dinamis menambah kompleksitas mount namespace dan drive mapping Wine pada MVP.

## Keputusan
Deployment aplikasi portable dilakukan dengan menyalin (copy) seluruh direktori aplikasi portable dari sumber eksternal langsung ke dalam direktori prefix target pada path `drive_c/Program Files/<app-id>/` (atau path yang setara), serupa dengan aplikasi yang diinstal melalui installer.

## Konsekuensi
### Positif
- Menyederhanakan arsitektur Bubblewrap Mount Builder: tidak perlu bind-mount direktori aplikasi eksternal terpisah ke dalam virtual drive Wine saat runtime.
- Aplikasi portable terikat rapi di dalam prefix-nya sendiri dan tidak rentan rusak jika file sumber di host dipindahkan atau dihapus.

### Negatif / Mitigasi
- Duplikasi penyimpanan jika pengguna menyimpan salinan cadangan di folder download host (dapat dibersihkan manual oleh pengguna setelah import berhasil).

