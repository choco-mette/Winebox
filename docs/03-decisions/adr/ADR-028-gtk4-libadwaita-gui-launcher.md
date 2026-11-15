# ADR-028: GUI Launcher Menggunakan GTK4 & Libadwaita (`PyGObject`)

- **Status:** Accepted
- **Date:** 2026-11-15
- **Deciders:** WineBox Maintainers

## Context
WineBox membutuhkan GUI Launcher desktop Linux yang mencakup Library aplikasi, Prefix Manager + File Manager tersemat, Runner Hub, editor Security Profile, dan System Doctor tanpa menduplikasi logika bisnis di `src/winebox/application/`.

## Decision
1. **Stack GUI Utama:** Menggunakan **GTK4 + Libadwaita** melalui binding Python **`PyGObject`** (`gi.repository.Gtk`, `Adw`, `Gio`, `Gdk`, `GLib`).
2. **Integrasi Langsung Layer `application/`:** GUI berada di layer `interface/` (misal `winebox gui`) dan memanggil langsung service Python yang sudah ada (`AppService`, `PrefixLifecycleService`, `PrefixRuntimeService`, `PrefixBackupService`, `RunnerService`, `ProfileService`, `WinetricksService`) tanpa server IPC terpisah.
3. **Arsitektur Widget & Responsivitas:**
   - **Prefix File Manager:** Menggunakan `Gtk.ColumnView` + `Gio.ListStore` (virtualized list), `Gio.content_type_guess` untuk ikon native, `Gtk.DropTarget` (`Gdk.FileList`) untuk drag-and-drop mod/file, serta `Gtk.FileLauncher` untuk membuka folder di file manager sistem (kompatibel XDG Portal / Flatpak).
   - **Symlink Guard:** File manager menolak menelusuri symlink yang mengarah ke luar direktori prefix (seperti `dosdevices/`).
   - **Concurrency:** Operasi I/O berat (unduh runner, ekstraksi, backup, eksekusi sandbox) dijalankan pada worker `threading.Thread` dan memperbarui widget melalui `GLib.idle_add()`.
4. **Opsionalitas CLI:** Ketergantungan GTK4/Libadwaita bersifat opsional sehingga mode CLI (`winebox ...`) tetap berjalan ringan di lingkungan headless.

## Consequences
- Tampilan native Linux (Wayland/X11) selaras dengan GNOME/Bottles/Lutris dengan penggunaan memori rendah.
- Lingkungan development `.venv` perlu akses ke `python3-gi` sistem (`--system-site-packages`) serta paket `gir1.2-gtk-4.0` dan `gir1.2-adw-1`.
