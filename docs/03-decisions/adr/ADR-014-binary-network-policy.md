# ADR-014: Model Kebijakan Jaringan Biner (Disabled / Enabled)

## Status
Accepted

## Konteks
Isolasi jaringan penting untuk mencegah aplikasi Windows mengirimkan telemetri atau data keluar tanpa izin pengguna. Namun, penyaringan lalu lintas jaringan tingkat lanjut (seperti firewall per-domain, proxy SOCKS5/HTTP lokal di dalam container, atau bridging `slirp4netns`/veth) memerlukan komponen daemon latar belakang atau konfigurasi root.

## Keputusan
Untuk MVP, WineBox menerapkan model kebijakan jaringan biner sederhana:
1. `network = false`: Bubblewrap mengisolasi penuh namespace jaringan (tanpa argumen `--share-net`). Hanya interface loopback `lo` yang tersedia di dalam sandbox. Tidak ada akses internet atau jaringan lokal.
2. `network = true`: Bubblewrap membagikan namespace jaringan host dengan argumen `--share-net`.
3. Mode jaringan tingkat lanjut (restricted domain filter / user-mode slirp4netns) ditunda ke fase post-MVP.

## Konsekuensi
### Positif
- Sangat deterministik, andal, dan tidak memerlukan privilege tambahan atau dependensi utilitas jaringan eksternal.
- Memberikan perlindungan instan untuk aplikasi offline hanya dengan toggle konfigurasi.

### Negatif / Mitigasi
- Saat `network = true`, aplikasi memiliki akses ke seluruh antarmuka jaringan yang dapat dijangkau oleh host.

