# Project Structure

Struktur direktori proyek WineBox:

```text
Winebox/
├── docs/                       # Dokumentasi arsitektur dan spesifikasi
│   ├── 01-project/             # Visi, ruang lingkup, dan tujuan
│   ├── 02-architecture/        # Dokumen arsitektur perangkat lunak
│   ├── 03-decisions/adr/       # Architecture Decision Records (ADR)
│   ├── 04-security/            # Model ancaman dan arsitektur keamanan
│   ├── 05-specifications/      # Spesifikasi teknis komponen
│   └── 06-development/         # Panduan standar kode, setup, & rilis
│
├── src/
│   └── winebox/                # Source code Python (src-layout)
│       ├── __init__.py
│       ├── common/             # Exceptions dan utilitas umum
│       ├── domain/             # Domain models (App, Prefix, Runner, Policy)
│       ├── security/           # PolicyValidator, Auditor, MountBuilder
│       ├── application/        # Use cases / services
│       ├── infrastructure/     # Adapters (Bwrap, Wine, Filesystem, Process)
│       └── interface/          # Typer CLI dan Rich UI
│
├── tests/                      # Automated test suite
│   ├── conftest.py
│   ├── unit/                   # Unit test per layer
│   └── integration/            # Test integrasi sandbox dan runner
│
├── SAD.md                      # Software Architecture Document utama
├── pyproject.toml              # Definisi build PEP 621 (Hatchling)
├── README.md                   # Dokumentasi umum proyek
└── .gitignore                  # Filter berkas Git
```
