# ADR-016: Eksekusi Prefix Single-Instance Berbasis File Lock

## Status
Accepted

## Konteks
Ketika beberapa aplikasi Windows berbagi satu Wine Prefix, aplikasi-aplikasi tersebut bergantung pada satu daemon `wineserver` per prefix. Jika dua aplikasi dijalankan serentak dalam dua container Bubblewrap yang terisolasi, isolasi mount `/tmp` dan PID namespace menyebabkan container kedua tidak dapat menjangkau socket `wineserver` container pertama, yang dapat memicu korupsi registry atau kegagalan inisialisasi Wine.

## Keputusan
Untuk MVP, WineBox membatasi eksekusi aplikasi di dalam satu Wine Prefix menjadi **single-instance**:
1. Setiap kali sebuah aplikasi di dalam suatu prefix dijalankan, WineBox membuat atau mengunci file `prefix.lock` di direktori prefix tersebut menggunakan file lock kernel (`fcntl`/`flock`).
2. Jika ada aplikasi lain yang mencoba berjalan di prefix yang sama saat file lock masih aktif, WineBox menolak eksekusi dan memberikan pesan peringatan bahwa prefix sedang digunakan oleh proses lain.
3. Fitur socket forwarding untuk multi-instance simultaneous execution di satu prefix ditunda ke fase post-MVP.

## Konsekuensi
### Positif
- Mencegah race condition, korupsi file registry Windows (`system.reg`), dan tabrakan daemon `wineserver`.
- Implementasi locking sangat handal dan otomatis terlepas jika proses host mati secara tidak terduga.

### Negatif / Mitigasi
- Pengguna tidak dapat menjalankan dua program dari prefix yang sama secara bersamaan di MVP (solusi: pengguna dapat membuat prefix kedua jika ingin menjalankan dua program sekaligus).

