# ADR-002: Antarmuka CLI-First, GUI Menyusul

## Status
Accepted

## Konteks
Pengembangan awal WineBox membutuhkan siklus validasi arsitektur inti (sandbox, mount builder, prefix auditor, runner manager) yang cepat, mudah diuji secara otomatis, dan dapat dijalankan di lingkungan terminal atau CI/CD tanpa dependensi GUI toolkit yang rumit.

## Keputusan
Menetapkan antarmuka CLI sebagai fokus antarmuka utama pada rilis MVP. Arsitektur harus dirancang berlapis (Modular Layered Architecture) sehingga use case di Application Layer sepenuhnya terpisah dari CLI, memungkinkan penambahan GUI di masa mendatang tanpa merombak logika bisnis.

## Konsekuensi
### Positif
- Mempercepat rilis MVP dan automasi pengujian end-to-end.
- Pemisahan tanggung jawab yang bersih antara presentasi dan logika inti.
- Scriptable dan ramah bagi pengguna power-user Linux.

### Negatif / Mitigasi
- Kurang ramah bagi pengguna awam yang terbiasa klik antarmuka grafis (dimitigasi dengan menyediakan interactive wizard pada CLI).

