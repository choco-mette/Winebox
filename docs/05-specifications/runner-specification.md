# Runner Specification

Dokumen ini mendefinisikan manajemen Wine Runner pada WineBox.

## 1. Definisi Wine Runner

Runner adalah sekumpulan biner dan pustaka Wine yang digunakan untuk mengeksekusi aplikasi Windows. WineBox mendukung dua jenis runner pada fase MVP:

1. **System Wine Runner (`system-wine`):**
   - Menggunakan instalasi Wine bawaan sistem operasi host di `/usr/bin/wine`.
   - Menggunakan `wineserver` di `/usr/bin/wineserver` (jika tersedia).
   - Menjadi runner default untuk seluruh prefix baru.

2. **Custom Managed Runner:**
   - Direktori biner Wine mandiri yang didaftarkan oleh pengguna dari direktori lokal.
   - Disimpan metadata-nya di `$XDG_DATA_HOME/winebox/runners/<runner-id>.toml`.

---

## 2. Struktur Konfigurasi Runner (`<runner-id>.toml`)

```toml
[runner]
id = "wine-ge-custom"
name = "GE-Proton Custom Build"
is_system = false
wine_bin = "/home/user/runners/wine-ge/bin/wine"
wineserver_bin = "/home/user/runners/wine-ge/bin/wineserver"
version = "8.26"
created_at = "2026-11-08T19:30:00Z"
```

---

## 3. Isolasi & Mount Runner dalam Sandbox

- Untuk **System Wine**:
  - Direktori `/usr` di-mount read-only (`--ro-bind /usr /usr`).
  - File cache linker di-mount read-only (`--ro-bind /etc/ld.so.cache /etc/ld.so.cache`).
- Untuk **Custom Runner**:
  - Direktori induk runner di-mount secara read-only ke path yang terisolasi di dalam container (misalnya `/app/runner`).
  - Variabel `PATH` dan `LD_LIBRARY_PATH` sandbox diperbarui agar mengutamakan biner custom runner.

