# ADR-004: Kewajiban Eksekusi di Dalam Sandbox Bubblewrap

## Status
Accepted

## Konteks
Aplikasi Windows yang dijalankan lewat Wine secara default memiliki hak akses penuh ke filesystem pengguna Linux host (`~`, dokumen, SSH keys, browser profiles). Untuk melindungi host dari kode tak tepercaya, WineBox menganut prinsip dasar: *No Sandbox, No Execution*.

## Keputusan
Semua eksekusi proses Wine (termasuk menjalankan aplikasi, installer EXE/MSI, dan wineboot initialization) wajib dieksekusi di dalam sandbox Bubblewrap (`bwrap`). Tidak ada opsi atau bypass untuk menjalankan Wine secara langsung di host tanpa sandbox.

## Konsekuensi
### Positif
- Jaminan isolasi keamanan konsisten across the board.
- Mencegah malware atau crash aplikasi Windows mencemari direktori pengguna host.
- Mempermudah perancangan audit logging dan security boundary.

### Negatif / Mitigasi
- Overhead inisialisasi namespace Linux (minimal, dalam satuan milidetik).
- Membutuhkan penanganan mount point yang presisi agar pustaka runtime yang sah tetap dapat diakses oleh Wine.

