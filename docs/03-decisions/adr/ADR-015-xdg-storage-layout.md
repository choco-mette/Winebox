# ADR-015: Tata Letak Penyimpanan Rootless Berbasis Spesifikasi XDG

## Status
Accepted

## Konteks
WineBox beroperasi dalam mode non-root (rootless user mode) untuk mematuhi prinsip least privilege. Direktori penyimpanan aplikasi, prefix, konfigurasi, dan data sementara harus teratur rapi sesuai standar desktop Linux tanpa mencemari sembarang lokasi di direktori pengguna host.

## Keputusan
Menetapkan struktur penyimpanan WineBox mengikuti XDG Base Directory Specification:
- **Data Root (`$XDG_DATA_HOME/winebox`, default: `~/.local/share/winebox`):**
  - `applications/<app-id>.toml`: Metadata aplikasi terdaftar.
  - `prefixes/<prefix-id>/`: Direktori lingkungan Wine Prefix (`prefix/`, `home/`, `config.toml`, `logs/`, `prefix.lock`).
  - `runners/`: Registrasi dan folder runner custom.
  - `staging/`: Area kerja sementara untuk operasi clone, sanitize, dan audit.
- **Config Root (`$XDG_CONFIG_HOME/winebox`, default: `~/.config/winebox`):**
  - `config.toml`: Konfigurasi global WineBox.
- Mode multi-user / system-wide installation (`/var/lib/winebox`) serta kuota penyimpanan otomatis ditunda untuk pengembangan lanjutan.

## Konsekuensi
### Positif
- Bersih, standar, dan sesuai ekspektasi pengguna ekosistem Linux modern.
- Menghindari kebutuhan izin root sama sekali dalam instalasi maupun pengoperasian harian.

### Negatif / Mitigasi
- Penghapusan data WineBox dapat dilakukan langsung dengan menghapus folder data pengguna tanpa hook uninstall sistem level OS.

