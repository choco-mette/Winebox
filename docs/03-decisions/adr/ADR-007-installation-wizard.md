# ADR-007: Wizard Instalasi Mendukung Prefix Baru dan Eksisting

## Status
Accepted

## Konteks
Saat pengguna menginstal aplikasi baru dari berkas installer (`.exe` atau `.msi`), pengguna mungkin ingin memasangnya ke dalam lingkungan Wine Prefix baru yang bersih, atau menggabungkannya ke dalam Wine Prefix yang sudah ada sebelumnya.

## Keputusan
Wizard instalasi interaktif (`winebox install`) harus memberikan opsi eksplisit kepada pengguna untuk:
1. Memilih Wine Prefix yang sudah terdaftar.
2. Membuat Wine Prefix baru secara langsung di dalam alur wizard.

Setelah instalasi selesai, wizard secara otomatis menjalankan audit prefix dan menawarkan registrasi executable yang baru terpasang ke daftar aplikasi WineBox.

## Konsekuensi
### Positif
- Fleksibilitas tinggi bagi pengguna: isolasi penuh (prefix baru) atau konsolidasi runtime (prefix eksisting).
- Alur kerja terpandu mengurangi kesalahan konfigurasi manual oleh pengguna.

### Negatif / Mitigasi
- Logika wizard instalasi sedikit lebih kompleks karena harus menangani pembuatan prefix on-the-fly jika user memilih opsi prefix baru.

