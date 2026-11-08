# ADR-018: Framework CLI Menggunakan Typer dan Rich dengan System Doctor

## Status
Accepted

## Konteks
WineBox membutuhkan antarmuka CLI yang kaya fitur, intuitif, mendukung hierarki sub-command yang kompleks (`winebox app run`, `winebox prefix create`, `winebox runner list`), serta mampu menampilkan wizard interaktif dengan format output visual yang rapi (tabel, progres transfer, peringatan warna). Selain itu, dibutuhkan perkakas diagnosa lingkungan sistem untuk mendeteksi kesiapan kernel dan dependensi host.

## Keputusan
1. Menggunakan pustaka **Typer** (berbasis Python type hints) sebagai kerangka kerja parsing argumen dan sub-command CLI.
2. Menggunakan pustaka **Rich** untuk rendering output terminal (tabel ringkasan, teks berwarna, format pesan error, dan status spinner).
3. Menyediakan modul diagnosa lingkungan sistem terdedikasi (`winebox system doctor`) yang memvalidasi bwrap, wine, userns, dan socket display/audio dengan rekomendasi perbaikan berbasis distribusi Linux jika terjadi kendala.
4. Menerapkan fail-fast check pada perintah eksekusi aplikasi untuk mendeteksi kegagalan sandbox sebelum memanggil Wine.

## Konsekuensi
### Positif
- Kode interface deklaratif, bersih, dan mudah diperluas.
- Pengalaman pengguna terminal modern dan estetik.
- Memudahkan troubleshooting bagi pengguna melalui perintah `doctor`.

### Negatif / Mitigasi
- Menambahkan dependensi paket Python pihak ketiga (`typer`, `rich`), namun keduanya merupakan standar de facto yang sangat stabil dan ringan di ekosistem Python modern.

