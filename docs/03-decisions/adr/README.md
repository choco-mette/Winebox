# Architecture Decision Records (ADR)

Index keputusan arsitektural proyek WineBox.

| ID | Judul | Status | Tanggal |
|---|---|---|---|
| [ADR-001](ADR-001-target-platform.md) | Target Platform Awal: Linux dengan systemd dan Bubblewrap | Accepted | 2026-11-08 |
| [ADR-002](ADR-002-cli-first.md) | Antarmuka CLI-First, GUI Menyusul | Accepted | 2026-11-08 |
| [ADR-003](ADR-003-shared-prefix.md) | Dukungan Beberapa Aplikasi Berbagi Satu Prefix | Accepted | 2026-11-08 |
| [ADR-004](ADR-004-mandatory-sandbox.md) | Kewajiban Eksekusi di Dalam Sandbox Bubblewrap | Accepted | 2026-11-08 |
| [ADR-005](ADR-005-distribution-format.md) | Format Distribusi: Paket Python Lebih Dahulu, .deb Kemudian | Accepted | 2026-11-08 |
| [ADR-006](ADR-006-home-isolation.md) | Isolasi HOME per Prefix | Accepted | 2026-11-08 |
| [ADR-007](ADR-007-installation-wizard.md) | Wizard Instalasi Mendukung Prefix Baru dan Eksisting | Accepted | 2026-11-08 |
| [ADR-008](ADR-008-portable-app-deployment.md) | Deployment Aplikasi Portable Menggunakan Copy ke Prefix | Accepted | 2026-11-08 |
| [ADR-009](ADR-009-clone-staging-external-app.md) | Cloning Direktori Aplikasi Eksternal Melalui Staging | Accepted | 2026-11-08 |
| [ADR-010](ADR-010-prefix-import-clone-sanitize-audit.md) | Import Wine Prefix Eksternal Melalui Clone, Sanitize, dan Audit | Accepted | 2026-11-08 |
| [ADR-011](ADR-011-wine-runner-strategy.md) | Strategi Wine Runner MVP: System Wine Default dengan Custom Path | Accepted | 2026-11-08 |
| [ADR-012](ADR-012-namespace-isolation-failfast.md) | Isolasi Namespace Bubblewrap dan Validasi Fail-Fast | Accepted | 2026-11-08 |
| [ADR-013](ADR-013-hardware-integration.md) | Integrasi Hardware: X11, Audio, dan GPU Passthrough | Accepted | 2026-11-08 |
| [ADR-014](ADR-014-binary-network-policy.md) | Model Kebijakan Jaringan Biner (Disabled / Enabled) | Accepted | 2026-11-08 |
| [ADR-015](ADR-015-xdg-storage-layout.md) | Tata Letak Penyimpanan Rootless Berbasis Spesifikasi XDG | Accepted | 2026-11-08 |
| [ADR-016](ADR-016-prefix-lock-single-instance.md) | Eksekusi Prefix Single-Instance Berbasis File Lock | Accepted | 2026-11-08 |
| [ADR-017](ADR-017-permissive-hardware-default-policy.md) | Kebijakan Default: Hardware Allowed, Host Filesystem Denied | Accepted | 2026-11-08 |
| [ADR-018](ADR-018-cli-framework-typer-rich.md) | Framework CLI Menggunakan Typer dan Rich dengan System Doctor | Accepted | 2026-11-08 |
| [ADR-019](ADR-019-build-tooling-hatchling.md) | Tooling Build dan Packaging PEP 621 Menggunakan Hatchling | Accepted | 2026-11-08 |
| [ADR-020](ADR-020-sqlite-configuration-and-rotating-logs.md) | Manajemen Konfigurasi SQLite Terpusat dan Log File Terotasi | Accepted | 2026-11-13 |
| [ADR-021](ADR-021-unified-interactive-add-wizard.md) | Wizard Penambahan Aplikasi Terpadu (winebox add) dengan Deteksi Interaktif Executable dan Profil Keamanan | Accepted | 2026-11-13 |
| [ADR-022](ADR-022-lutris-library-integration.md) | Integrasi Ekspor dan Sinkronisasi Aplikasi WineBox ke Lutris Library | Accepted | 2026-11-13 |
| [ADR-023](ADR-023-sandboxed-winetricks-shared-cache.md) | Eksekusi Winetricks Terisolasi di Bubblewrap dengan Shared Cache dan Dual-Mode Selector | Accepted | 2026-11-15 |
| [ADR-024](ADR-024-xdg-desktop-integration.md) | Integrasi XDG Desktop Entry (.desktop) dengan Opsi Interaktif dan Manajemen Siklus Hidup | Accepted | 2026-11-15 |
| [ADR-025](ADR-025-emergency-prefix-process-killer.md) | Terminasi Darurat Proses Prefix dan Sanitasi Lingkungan (Kill Switch) | Accepted | 2026-11-15 |

