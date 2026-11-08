# ADR-005: Format Distribusi: Paket Python Lebih Dahulu, .deb Kemudian

## Status
Accepted

## Konteks
WineBox membutuhkan mekanisme distribusi yang fleksibel dan independen dari repositori paket sistem operasi agar dapat diiterasi secara cepat selama fase pengembangan awal dan rilis komunitas.

## Keputusan
Mendistribusikan WineBox sebagai paket standar Python (wheel / source distribution via PyPI / Git) pada tahap rilis awal (MVP). Distribusi format paket native sistem operasi seperti `.deb` atau `.rpm` ditunda untuk tahap rilis berikutnya.

## Konsekuensi
### Positif
- Instalasi mudah di berbagai distro Linux via `pipx` atau virtual environment tanpa memerlukan izin root (`sudo`).
- Siklus rilis dan patch bug lebih lincah dan cepat.

### Negatif / Mitigasi
- Pengguna harus menginstal dependensi sistem runtime (`bubblewrap`, `wine`) secara manual melalui package manager bawaan distro mereka (dimitigasi dengan `winebox system doctor` di ADR-018).

