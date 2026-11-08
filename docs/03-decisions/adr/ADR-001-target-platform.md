# ADR-001: Target Platform Awal: Linux dengan systemd dan Bubblewrap

## Status
Accepted

## Konteks
WineBox membutuhkan mekanisme isolasi lingkungan eksekusi untuk menjalankan aplikasi Windows tanpa mengekspos filesystem host. Dibutuhkan fondasi platform Linux modern yang mendukung unprivileged user namespaces, kontrol proses, dan ekosistem isolasi ringan tanpa overhead virtual machine.

## Keputusan
Menetapkan target platform awal WineBox adalah distribusi Linux modern berbasis systemd yang menyediakan utilitas Bubblewrap (`bwrap`) dan Wine.

## Konsekuensi
### Positif
- Memanfaatkan fitur keamanan native Linux kernel (user namespaces, mount namespaces, network namespaces).
- Bubblewrap ringan dan banyak tersedia di repositori distro utama (Ubuntu, Debian, Fedora, Arch).
- Pengelolaan proses dapat memanfaatkan cgroup dan sinyal standar Linux.

### Negatif / Mitigasi
- Bergantung pada ketersediaan user namespace di host. Jika dinonaktifkan oleh administrator, WineBox gagal jalan (dimitigasi melalui pre-flight check diagnostik).
- Tidak mendukung platform non-Linux (BSD/macOS/Windows).

