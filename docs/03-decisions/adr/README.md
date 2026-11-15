# Architecture Decision Records (ADRs)

This directory contains the Architecture Decision Records (ADRs) for **WineBox**. Each ADR documents a significant architectural or design choice, including its context, considered alternatives, rationale, and consequences.

## Decision Lifecycle

| Status | Meaning |
|---|---|
| **Proposed** | Under discussion and awaiting review. |
| **Accepted** | Approved and actively enforced in the codebase. |
| **Superseded** | Replaced by a newer ADR (referenced in the record). |
| **Deprecated** | No longer recommended for new development. |

---

## ADR Index

| ID | Category | Title | Status | Date |
|---|---|---|---|---|
| [ADR-001](ADR-001-target-platform.md) | Platform | Initial Target Platform: Linux with `systemd` and Bubblewrap | Accepted | 2026-11-08 |
| [ADR-002](ADR-002-cli-first.md) | Interface | CLI-First Interface with Subsequent GUI Layer | Accepted | 2026-11-08 |
| [ADR-003](ADR-003-shared-prefix.md) | Runtime | Multi-Application Support Within a Shared Wine Prefix | Accepted | 2026-11-08 |
| [ADR-004](ADR-004-mandatory-sandbox.md) | Security | Mandatory Execution Inside Bubblewrap Sandbox | Accepted | 2026-11-08 |
| [ADR-005](ADR-005-distribution-format.md) | Packaging | Distribution Strategy: Python Package First, Native `.deb` Subsequently | Accepted | 2026-11-08 |
| [ADR-006](ADR-006-home-isolation.md) | Security | Per-Prefix `HOME` Directory Isolation | Accepted | 2026-11-08 |
| [ADR-007](ADR-007-installation-wizard.md) | Onboarding | Installation Wizard Supporting New and Existing Prefixes | Accepted | 2026-11-08 |
| [ADR-008](ADR-008-portable-app-deployment.md) | Deployment | Portable Application Deployment via Copy-to-Prefix | Accepted | 2026-11-08 |
| [ADR-009](ADR-009-clone-staging-external-app.md) | Deployment | External Application Directory Cloning via Staging | Accepted | 2026-11-08 |
| [ADR-010](ADR-010-prefix-import-clone-sanitize-audit.md) | Security | External Wine Prefix Import via Clone, Sanitize, and Audit | Accepted | 2026-11-08 |
| [ADR-011](ADR-011-wine-runner-strategy.md) | Runtime | MVP Wine Runner Strategy: System Wine Default with Custom Paths | Accepted | 2026-11-08 |
| [ADR-012](ADR-012-namespace-isolation-failfast.md) | Security | Bubblewrap Namespace Isolation and Fail-Fast Validation | Accepted | 2026-11-08 |
| [ADR-013](ADR-013-hardware-integration.md) | Runtime | Hardware Integration: X11/Wayland Display, Audio, and GPU Passthrough | Accepted | 2026-11-08 |
| [ADR-014](ADR-014-binary-network-policy.md) | Security | Binary Network Access Policy (`Disabled` / `Enabled`) | Accepted | 2026-11-08 |
| [ADR-015](ADR-015-xdg-storage-layout.md) | Storage | Rootless Storage Layout Based on XDG Base Directory Specification | Accepted | 2026-11-08 |
| [ADR-016](ADR-016-prefix-lock-single-instance.md) | Runtime | File-Lock-Based Single-Instance Prefix Execution | Accepted | 2026-11-08 |
| [ADR-017](ADR-017-permissive-hardware-default-policy.md) | Security | Default Policy Model: Hardware Allowed, Host Filesystem Denied | Accepted | 2026-11-08 |
| [ADR-018](ADR-018-cli-framework-typer-rich.md) | Interface | CLI Framework Using Typer and Rich with System Doctor Diagnostics | Accepted | 2026-11-08 |
| [ADR-019](ADR-019-build-tooling-hatchling.md) | Packaging | PEP 621 Build and Packaging Tooling via Hatchling | Accepted | 2026-11-08 |
| [ADR-020](ADR-020-sqlite-configuration-and-rotating-logs.md) | Storage | Centralized SQLite Configuration Store and Rotating Log Files | Accepted | 2026-11-13 |
| [ADR-021](ADR-021-unified-interactive-add-wizard.md) | Interface | Unified Interactive Application Wizard (`winebox add`) with Executable Detection and Security Profiles | Accepted | 2026-11-13 |
| [ADR-022](ADR-022-lutris-library-integration.md) | Integration | Exporting and Synchronizing WineBox Applications with Lutris Library | Accepted | 2026-11-13 |
| [ADR-023](ADR-023-sandboxed-winetricks-shared-cache.md) | Runtime | Sandboxed Winetricks Execution in Bubblewrap with Shared Cache and Dual-Mode Selector | Accepted | 2026-11-15 |
| [ADR-024](ADR-024-xdg-desktop-integration.md) | Integration | XDG Desktop Entry (`.desktop`) Integration with Interactive Options and Lifecycle Management | Accepted | 2026-11-15 |
| [ADR-025](ADR-025-emergency-prefix-process-killer.md) | Runtime | Emergency Prefix Process Termination and Environment Sanitization (Kill Switch) | Accepted | 2026-11-15 |
| [ADR-026](ADR-026-runner-manager-and-shared-ecosystem.md) | Runtime | Integrated Runner Manager with Rootless Shared Ecosystem Symlinks | Accepted | 2026-11-15 |
| [ADR-027](ADR-027-prefix-snapshot-backup-restore.md) | Storage | Portable Prefix Snapshot & Backup with Security Validation and Atomic Staging | Accepted | 2026-11-15 |
| [ADR-028](ADR-028-gtk4-libadwaita-gui-launcher.md) | Interface | Desktop GUI Launcher Built with GTK4 and Libadwaita (PyGObject) | Accepted | 2026-11-15 |
