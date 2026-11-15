# ADR-025: Terminasi Darurat Proses Prefix dan Sanitasi Lingkungan (Kill Switch)

## Status
Accepted

## Konteks
Aplikasi atau game Windows yang berjalan di dalam sandbox Bubblewrap melalui WineBox terkadang dapat mengalami *freeze*, *deadlock*, *crash* dengan layar hitam, atau *hang* pada background wineserver.

Kondisi ini menimbulkan sejumlah hambatan operasional:
1. Mekanisme `prefix.lock` (ADR-016) akan terus mengunci direktori prefix karena proses sebelumnya masih hidup. Akibatnya, pengguna tidak dapat menjalankan kembali aplikasi atau melakukan konfigurasi sebelum proses yang macet dihentikan.
2. Pengguna Linux biasa sering kali kesulitan melacak proses Bubblewrap (`bwrap`), Wine, atau `wineserver` mana yang berkaitan dengan prefix tertentu jika harus menggunakan perintah manual seperti `killall`, `pkill -9 bwrap`, atau `fuser`.
3. Menghentikan proses secara paksa tanpa pembersihan dapat meninggalkan kondisi symlink yang tidak teraudit.

Pengguna membutuhkan satu perintah terpadu (*emergency stop / kill switch*) untuk mematikan semua proses yang berjalan di suatu prefix secara aman dan seketika.

## Keputusan

### 1. Deteksi Proses Aktif Berbasis `prefix.lock` dan Pindai Namespace
Sistem akan mengidentifikasi proses yang berjalan pada target prefix melalui dua lapis:
- **Lapis 1 (`prefix.lock` PID):** Membaca PID proses utama WineBox yang tercatat pada berkas kunci `prefix.lock`.
- **Lapis 2 (Pindai Subproses Host):** Memindai proses `/proc` pada sistem host yang memiliki argumen sandbox (`bwrap`) terikat pada direktori prefix yang bersangkutan untuk mengantisipasi proses anak (*orphan/zombie*).

### 2. Strategi Terminasi Bertahap (Graceful SIGTERM -> SIGKILL)
Proses terminasi dilakukan dengan tahapan:
1. Mengirim sinyal `SIGTERM` ke proses utama dan grup proses terkait untuk memberikan kesempatan *cleanup* internal (flush I/O buffer).
2. Menunggu dalam jendela toleransi singkat (*grace period* 1.0 detik).
3. Jika proses masih belum berhenti, sistem otomatis mengirimkan sinyal `SIGKILL` (`kill -9`).
4. Memastikan berkas kunci `prefix.lock` telah terlepas dan tidak lagi terkunci.

### 3. Pembersihan Pasca-Terminasi (Post-Termination Sanitization)
Setelah seluruh proses berhenti:
- Menjalankan `PrefixAuditor.sanitize_dosdevices(prefix_path)` untuk memastikan integritas pemetaan drive `dosdevices/z:` tetap ternetralisasi (ADR-010 & ADR-023).

### 4. Antarmuka Perintah CLI Mandiri
Menyediakan perintah CLI di level `prefix` dan `app`:
- `winebox prefix kill <prefix_id> [--force]`: Mematikan seluruh proses yang sedang aktif di prefix target.
- `winebox app kill <app_id> [--force]`: Memetakan `app_id` ke prefix terkait dan mengeksekusi terminasi.

### 5. Integrasi Aksi Desktop Entry (`[Desktop Action Kill]`)
Menyematkan aksi desktop standar ke dalam berkas `.desktop` (ADR-024):
```ini
Actions=Configure;Kill;

[Desktop Action Kill]
Name=Stop / Kill Process
Exec=winebox prefix kill <prefix_id>
```
Hal ini memungkinkan pengguna menghentikan game yang macet langsung melalui menu konteks klik-kanan pada launcher/dock desktop Linux.

## Konsekuensi

### Positif
- Solusi instan untuk game/aplikasi yang hang tanpa perlu perintah terminal Linux tingkat rendah (`killall`, `pkill`).
- Menghindari *prefix deadlock* dan memulihkan akses prefix secara aman.
- Terintegrasi langsung dengan menu klik kanan shortcut desktop OS.
- Pembersihan sanitasi otomatis menjaga keamanan isolasi host.

### Negatif / Mitigasi
- Terminasi darurat (`SIGKILL`) pada aplikasi yang sedang menulis data penyimpanan (*savegame*) dapat memicu korupsi berkas jika aplikasi sedang melakukan penulisan aktif (mitigasi: didahului `SIGTERM` dengan grace period agar aplikasi sempat melakukan shutdown tertib jika memungkinkan).
