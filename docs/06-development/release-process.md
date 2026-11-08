# Release Process

Alur rilis dan versioning WineBox:

1. **Semantic Versioning (SemVer):** Format `MAJOR.MINOR.PATCH` (dimulai dari `0.1.0` untuk MVP).
2. **Build Distribution:**
   ```bash
   pip install build
   python -m build
   ```
   Menghasilkan biner `.whl` dan `.tar.gz` di folder `dist/`.
3. **Pemeriksaan Pre-Release:**
   - Semua ADR disinkronkan statusnya.
   - Semua test unit dan integrasi lulus 100%.
   - `winebox system doctor` berfungsi pada lingkungan bersih.

