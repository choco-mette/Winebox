# ADR-010: Import Wine Prefix Eksternal Melalui Clone, Sanitize, dan Audit

## Status
Accepted

## Konteks
Pengguna mungkin memiliki Wine Prefix yang dibuat di luar WineBox (misalnya dari Lutris, Bottles, PlayOnLinux, atau Wine manual). Prefix eksternal tersebut sering kali mengandung pemetaan drive berbahaya (seperti drive `Z:` yang mengarah ke root filesystem `/` host), symlink yang keluar dari direktori prefix, atau file konfigurasi registry yang merujuk direktori pengguna host.

## Keputusan
Import Wine Prefix eksternal wajib melalui tiga tahapan:
1. **Clone**: Salin direktori prefix eksternal ke dalam direktori `staging/` internal WineBox.
2. **Sanitize**: Hapus atau perbaiki symlink berbahaya, batasi drive mapping (khususnya menonaktifkan atau membatasi `Z:` drive), dan bersihkan path yang merujuk host filesystem secara langsung.
3. **Audit**: Jalankan Prefix Auditor untuk memverifikasi struktur file, junction points, dan integritas registry.

Prefix eksternal yang gagal dalam tahap audit ditolak dan tidak boleh dipindahkan ke status aktif.

## Konsekuensi
### Positif
- Mencegah prefix dari luar mengeksploitasi filesystem host melalui symlink atau drive mapping peninggalan konfigurasi lama.
- Melindungi prefix asli pengguna dari perubahan yang tidak disengaja karena WineBox beroperasi pada hasil kloning.

### Negatif / Mitigasi
- Waktu proses import lebih lama sebanding dengan ukuran data di dalam prefix eksternal.

