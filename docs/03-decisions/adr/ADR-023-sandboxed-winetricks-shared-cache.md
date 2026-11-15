# ADR-023: Eksekusi Winetricks Terisolasi di Bubblewrap dengan Shared Cache dan Dual-Mode Selector

## Status
Accepted

## Konteks
Permainan dan perangkat lunak Windows sering kali memerlukan komponen runtime tambahan (seperti Direct3D compiler, Visual C++ Redistributable, .NET Framework, atau font TrueType) yang biasanya dipasang menggunakan utilitas pihak ketiga **Winetricks**.

Jika pengguna menjalankan `winetricks` secara langsung di sistem host:
1. Menimbulkan risiko *race condition* dan korupsi registry karena mengabaikan mekanisme kunci `prefix.lock` milik WineBox (ADR-016).
2. Sering memulihkan tautan simbolik berbahaya `dosdevices/z:` yang mengarah ke root filesystem host Linux `/`.
3. Mengunduh berkas installer yang sama berulang-ulang untuk prefix yang berbeda, memboroskan ruang disk dan kuota internet.
4. Menjalankan proses tanpa batas isolasi namespace Bubblewrap (ADR-004).

## Keputusan

### 1. Eksekusi Sandboxed dengan `prefix.lock` dan Auto-Sanitize
Menyediakan perintah `winebox prefix winetricks <prefix_id> [verbs...]` yang menjalankan Winetricks di dalam Bubblewrap sandbox:
- Memperoleh `prefix_lock` sebelum proses dimulai untuk mencegah konkurensi.
- Menetapkan kebijakan keamanan sementara: `network = True` (untuk pengunduhan package), `display = True` (jika mode GUI), dan filesystem host tetap diblokir (`DENIED`).
- Menjalankan `PrefixAuditor.sanitize_dosdevices(prefix_path)` segera setelah proses instalasi selesai untuk memastikan `dosdevices/z:` tetap dinetralkan.

### 2. Penyimpanan Cache Bersama Terpusat (*Shared Cache Mount*)
Menempatkan cache unduhan installer Winetricks secara terpusat di `~/.local/share/winebox/cache/winetricks/` pada sistem host:
- Di-mount secara read-write ke `$HOME/.cache/winetricks` di dalam virtual home prefix.
- Seluruh prefix berbagi berkas unduhan yang sama sehingga installer besar (seperti .NET dan Visual C++) hanya perlu diunduh satu kali.

### 3. Dual-Mode Antarmuka Pengguna (CLI Langsung & TUI Multi-Select)
- **Mode CLI Langsung**: Jika argumen paket (verbs) disertakan (misalnya `winebox prefix winetricks gaming vcrun2022 dxvk`), sistem langsung mengeksekusi pemasangan tanpa meminta konfirmasi interaktif.
- **Mode TUI Selector**: Jika dipanggil tanpa argumen paket (misalnya `winebox prefix winetricks [prefix_id]`), sistem menampilkan menu interaktif (`↑/↓`, `Space`, `Enter`) yang memuat katalog paket runtime populer (`dxvk`, `vkd3d`, `vcrun2022`, `dotnet48`, `corefonts`, dll.), opsi memasukkan verb manual, serta opsi membuka GUI asli Winetricks.

## Konsekuensi

### Positif
- Eksekusi Winetricks 100% aman di dalam sandbox Bubblewrap tanpa risiko polusi filesystem host.
- Penghematan waktu dan kuota internet berkat *shared cache*.
- Pengalaman pengguna yang sangat ramah: pengguna awam dapat memilih dari menu katalog populer, sedangkan pengguna tingkat lanjut dapat mengetikkan verbs langsung di CLI.

### Negatif / Mitigasi
- Winetricks memerlukan biner `winetricks` terpasang di host Linux (sistem memeriksa ketersediaan biner dan memberikan petunjuk remediasi jika belum terpasang).
- Beberapa installer Windows versi lama yang dipanggil oleh Winetricks dapat menampilkan kotak dialog grafis sementara (dimitigasi dengan mengaktifkan akses display server saat sesi winetricks berlangsung).
