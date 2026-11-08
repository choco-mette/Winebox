# Testing Strategy

Strategi pengujian WineBox untuk memastikan keamanan dan stabilitas.

## 1. Piramida Pengujian

1. **Unit Testing (`tests/unit/`):**
   - Menguji isolasi logika domain dan service.
   - Menguji `MountBuilder` menghasilkan kombinasi flag `bwrap` yang tepat tanpa mengeksekusi container asli.
   - Menguji `PolicyValidator` menolak path host sensitif (`~/.ssh`, `/root`, `/media`).
   - Menguji `PrefixAuditor` mendeteksi link berbahaya atau dosdevices `Z:`.

2. **Integration Testing (`tests/integration/`):**
   - Menguji interaksi `BwrapAdapter` dengan sistem operasi (menjalankan container dummy bwrap ringan).
   - Menguji operasi atomic move dan clone staging.
   - Menguji `fcntl.flock` pada `prefix.lock` untuk mencegah konkurensi ganda.

## 2. Mocking Policy
- Operasi eksekusi Wine yang memakan waktu lama (seperti `wineboot` atau menjalankan installer GUI) wajib di-mock saat CI testing.
- Unit test tidak boleh bergantung pada ketersediaan Wine atau display X11 host.

