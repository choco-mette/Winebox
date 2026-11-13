# ADR-020: Manajemen Konfigurasi SQLite Terpusat dan Log File Terotasi

## Status
Accepted

## Konteks
Pada rilis MVP awal (ADR-015), WineBox menggunakan file TOML individual (`applications/*.toml`, `prefixes/*/config.toml`). Seiring bertambahnya kebutuhan pengguna akan konfigurasi profil keamanan yang interaktif, dinamis, dan query relasional (seperti memfilter aplikasi berdasarkan tingkat izin atau mengelola preset keamanan secara terpusat), pendekatan file TOML individual memiliki keterbatasan:
1. Tidak memiliki integritas referensial otomatis (misal saat prefix dihapus, file konfigurasi aplikasi bisa tertinggal/yatim piatu).
2. Sulit mengelola preset profil keamanan hierarkis (*inheritance*) di mana perubahan satu profil otomatis berlaku ke seluruh aplikasi yang menggunakannya.
3. Namun di sisi lain, jika seluruh log eksekusi dicatat ke dalam database, ukuran file database akan cepat membengkak akibat keluaran diagnostik Wine yang sangat panjang dan berisik (*verbose*).
4. Jika database terpusat mengalami kerusakan (*corruption*), folder prefix yang ada di sistem penyimpanan lokal berisiko kehilangan identitas dan konfigurasinya.

## Keputusan

### 1. SQLite sebagai Sumber Data Utama (Single Source of Truth)
Menjadikan database SQLite lokal tersemat (`~/.local/share/winebox/winebox.db`) sebagai repositori konfigurasi utama WineBox. SQLite menggunakan pustaka bawaan standar Python (`sqlite3`) tanpa dependensi pihak ketiga atau server database eksternal.

Skema inti mencakup:
- `security_profiles`: Menyimpan preset profil keamanan (`paranoid`, `zero-trust`, `balanced`, `permissive`, dan preset custom pengguna).
- `prefixes`: Menyimpan metadata prefix dengan foreign key ke profil keamanan default.
- `applications`: Menyimpan metadata aplikasi, executable path, argumen, telemetry ringkas (`last_run_at`, `last_exit_code`), dan referensi profil keamanan.
- `app_host_mounts`: Menyimpan direktori host spesifik yang diizinkan untuk aplikasi tertentu.
- `runners`: Menyimpan runner Wine sistem maupun kustom.

### 2. Snapshot Metadata Lokal untuk Portabilitas & Pemulihan Bencana
Untuk menjaga portabilitas prefix (misal saat dipindahkan ke perangkat lain atau jika database rusak), setiap kali terjadi perubahan data prefix atau aplikasi, WineBox secara otomatis menuliskan snapshot ringkas (`metadata.json`) di dalam direktori masing-masing prefix (`prefixes/<id>/metadata.json`). WineBox menyediakan mekanisme auto-recovery dari file snapshot ini jika database hilang.

### 3. Konkurensi WAL dan Transaksi Milidetik
Mengaktifkan mode Write-Ahead Logging (`PRAGMA journal_mode=WAL`) pada SQLite. Transaksi database dibatasi hanya dalam hitungan milidetik saat membaca argumen atau menyimpan status sebelum eksekusi. Koneksi database wajib ditutup sebelum proses aplikasi Windows di dalam Bubblewrap sandbox dijalankan, sehingga konkurensi antar-proses tidak menyebabkan galat `database is locked`.

### 4. Log File Terotasi Otomatis (Anti-Bloat)
Seluruh keluaran teks proses Wine tidak disimpan di dalam database SQLite, melainkan dialirkan ke file log terpisah per-prefix:
- Jalur log: `prefixes/<id>/logs/execution.log`.
- Mekanisme: `logging.handlers.RotatingFileHandler` dengan ukuran maksimal 5 MB per file dan maksimal 3 berkas cadangan (*backup count*).

### 5. Migrasi Skema dan Kompatibilitas Data Lama
- Menggunakan `PRAGMA user_version` bawaan SQLite untuk mengelola versi dan migrasi skema database tanpa dependensi ORM berat.
- Menyediakan fungsi auto-import pada inisialisasi pertama untuk membaca data dari file `.toml` lama ke dalam database SQLite secara transparan.

## Konsekuensi

### Positif
- Manajemen level keamanan menjadi sangat fleksibel dan interaktif melalui antarmuka terminal Rich.
- Pemisahan tanggung jawab yang bersih: SQLite mengelola konfigurasi terstruktur murni, sedangkan file `.log` terotasi mengelola teks log bervolume tinggi.
- Relasi data aman dengan *Foreign Key Constraints* (`RESTRICT` penghapusan profil yang sedang digunakan).
- Integritas data terjaga dengan file snapshot lokal di tiap prefix.

### Negatif / Mitigasi
- File database SQLite tidak dapat diedit langsung menggunakan editor teks biasa seperti nano (dimitigasi dengan menyediakan perintah CLI interaktif `winebox profile edit` dan opsi ekspor/impor JSON/TOML).
- Diperlukan layer repositori database (`SqliteRepository`) yang menggantikan `ConfigRepository` TOML.
