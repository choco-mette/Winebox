# ADR-003: Dukungan Beberapa Aplikasi Berbagi Satu Prefix

## Status
Accepted

## Konteks
Beberapa aplikasi Windows saling bergantung pada komponen, runtime (seperti .NET, DirectX, VC++ Redistributable), atau installer plugin yang harus berada di dalam instalasi registry dan filesystem Windows yang sama (misalnya: DAW dengan plugin VST, atau launcher game dengan game terpasang). Membuat prefix terpisah untuk setiap aplikasi memboroskan ruang disk dan menyulitkan integrasi inter-aplikasi.

## Keputusan
WineBox mendukung model one-to-many antara Wine Prefix dan Aplikasi: beberapa aplikasi terdaftar dapat menunjuk dan berbagi satu Wine Prefix yang sama.

## Konsekuensi
### Positif
- Hemat kapasitas penyimpanan disk (tidak perlu duplikasi instalasi runtime Wine untuk setiap aplikasi terkait).
- Memungkinkan interoperabilitas antar-aplikasi yang berbagi dependensi registry/DLL yang sama.

### Negatif / Mitigasi
- Potensi konflik versi runtime atau tabrakan proses Wine server jika dua aplikasi di prefix yang sama berjalan serentak (dimitigasi melalui file lock single-instance di ADR-016).

