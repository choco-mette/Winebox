# ADR-009: Cloning Direktori Aplikasi Eksternal Melalui Staging

## Status
Accepted

## Konteks
Mengimpor direktori aplikasi dari luar secara langsung ke direktori aktif berisiko menimbulkan kondisi inkonsisten (partial write) jika proses copy terputus, atau menyisipkan file berbahaya seperti symlink escape ke sistem host saat proses transfer berlangsung.

## Keputusan
Setiap proses penyalinan atau import direktori aplikasi eksternal wajib melalui direktori sementara (`staging/`). Setelah penyalinan ke staging selesai, direktori tersebut divalidasi (audit symlink dan entri direktori). Jika verifikasi lolos, direktori dipindahkan secara atomik (`move`/`rename`) ke lokasi tujuan akhir di dalam penyimpanan WineBox.

## Konsekuensi
### Positif
- Jaminan integritas atomik: direktori aplikasi aktif tidak pernah berada dalam kondisi setengah ter-copy.
- Isolasi proses audit: pemindaian struktur file dilakukan sebelum file diakui oleh sistem WineBox.

### Negatif / Mitigasi
- Memerlukan ruang disk sementara di partisi yang sama untuk memastikan operasi rename berjalan secara atomik (diatasi dengan menempatkan folder `staging/` di bawah parent data root yang sama).

