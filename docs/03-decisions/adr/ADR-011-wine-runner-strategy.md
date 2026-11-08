# ADR-011: Strategi Wine Runner MVP: System Wine Default dengan Custom Path

## Status
Accepted

## Konteks
WineBox membutuhkan runner Wine untuk mengeksekusi biner Windows. Mengembangkan sistem download otomatis berbagai runner eksternal (seperti Proton-GE, Kron4ek, Lutris-Wine) beserta dependensinya membutuhkan infrastruktur downloader, ekstraktor tarball, dan manajemen dependensi yang kompleks pada fase MVP.

## Keputusan
Untuk rilis MVP:
1. Wine default yang terpasang di sistem host (`/usr/bin/wine`) digunakan sebagai runner bawaan (`system-wine`).
2. Pengguna dapat mendaftarkan runner custom secara manual (`winebox runner register --name <name> --path <path>`) dengan menunjukkan direktori biner Wine yang sudah diekstrak di host.
3. Fitur auto-download runner dari rilis GitHub/repositori eksternal ditunda ke fase post-MVP.

## Konsekuensi
### Positif
- Implementasi sangat sederhana dan minim dependensi jaringan tambahan.
- Mengurangi ukuran distribusi WineBox dan mempercepat penyelesaian fungsionalitas inti.

### Negatif / Mitigasi
- Pengguna harus memastikan Wine sudah terpasang di host melalui package manager distro (diverifikasi secara otomatis oleh `winebox system doctor`).

