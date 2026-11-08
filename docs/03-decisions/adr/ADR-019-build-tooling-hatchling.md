# ADR-019: Tooling Build dan Packaging PEP 621 Menggunakan Hatchling

## Status
Accepted

## Konteks
Proyek Python modern membutuhkan standarisasi metadata proyek berbasis standar industri (PEP 517, PEP 518, PEP 621) di dalam berkas tunggal `pyproject.toml`. Diperlukan build backend yang cepat, ringan, tanpa boilerplate usang `setup.py`, serta kompatibel dengan installer modern seperti `pip`, `pipx`, dan `uv`.

## Keputusan
1. Menggunakan format deklaratif `pyproject.toml` sesuai spesifikasi PEP 621.
2. Menggunakan **Hatchling** (`hatchling.build`) sebagai build backend standar proyek WineBox.
3. Struktur source code diletakkan di dalam folder `src/winebox/` (src-layout) untuk mencegah import package lokal yang tidak sengaja saat pengujian dan memastikan package terinstall dengan benar.

## Konsekuensi
### Positif
- Standar resmi ekosistem Python modern tanpa vendor-lockin ke package manager tertentu.
- Instalasi editable mode (`pip install -e .`) berjalan lancar dan cepat.
- Src-layout mencegah bug path resolution saat menjalankan automated test suite (`pytest`).

### Negatif / Mitigasi
- Pengembang membutuhkan toolchain Python modern yang mendukung PEP 517/621 (Python >= 3.10).

