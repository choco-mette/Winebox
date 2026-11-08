# ADR-006: Isolasi HOME per Prefix

## Status
Accepted

## Konteks
Aplikasi Windows yang berjalan di Wine sering kali memetakan folder pengguna Windows (`AppData`, `Desktop`, `Documents`) ke dalam folder HOME pengguna Linux (`$HOME`). Jika semua aplikasi berbagi `$HOME` host atau satu `$HOME` global, file konfigurasi dan data pribadi dapat diakses atau diubah oleh aplikasi lain.

## Keputusan
Menyediakan direktori Linux `$HOME` privat yang terisolasi untuk setiap prefix (berada di `Prefixes/<prefix-id>/home/`). Di dalam sandbox Bubblewrap, direktori ini di-mount sebagai `/home/<user>` atau `$HOME`, menggantikan total `$HOME` pengguna host.

## Konsekuensi
### Positif
- Filesystem pengguna host (`~/.ssh`, `~/.bashrc`, `~/.config`, dokumen) tidak dapat dilihat sama sekali oleh aplikasi di dalam sandbox.
- Efek samping atau file sampah yang dibuat oleh Wine dan installer terkurung rapat di direktori prefix masing-masing.

### Negatif / Mitigasi
- Aplikasi Windows tidak otomatis melihat file "My Documents" host (pengguna harus mengekspos folder spesifik secara eksplisit jika diperlukan melalui custom mount).

