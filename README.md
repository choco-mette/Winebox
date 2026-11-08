# WineBox

Orchestrator keamanan untuk mengelola dan menjalankan aplikasi Windows di Linux melalui Wine dengan isolasi Bubblewrap (`bwrap`).

## Prinsip Utama
- **Hardware Allowed, Host Filesystem Denied**
- **Isolated by Default. Hardware Access by Policy.**
- **No Sandbox, No Execution.**

## Arsitektur
WineBox menggunakan *Modular Layered Architecture*:
- **Interface Layer**: CLI (`winebox`), future GUI.
- **Application Layer**: Services (App, Installation, Import, Prefix, Runner, Execution).
- **Domain Layer**: Models (Application, Prefix, Runner, SecurityPolicy).
- **Security Layer**: PolicyValidator, PrefixAuditor, MountBuilder, SandboxAuditor.
- **Infrastructure Layer**: BubblewrapAdapter, WineAdapter, FilesystemAdapter, ProcessManager, Repository.

Dokumentasi arsitektur lengkap: [SAD.md](SAD.md)  
Keputusan arsitektur (ADR): [docs/03-decisions/adr/](docs/03-decisions/adr/)

## Prasyarat Sistem
- Linux Kernel >= 5.4 dengan dukungan unprivileged user namespaces
- Bubblewrap (`bwrap`)
- Wine (`wine`)
- Python >= 3.11

## Lisensi
MIT

