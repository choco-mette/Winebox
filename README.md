<div align="center">
  <img src="packaging/linux/id.winebox.WineBox.svg" width="128" height="128" alt="WineBox Logo" />
  <h1>WineBox</h1>
  <p><strong>Secure orchestrator for managing and running Windows applications in Linux via Bubblewrap isolation.</strong></p>

  <p>
    <a href="https://github.com/choco-mette/Winebox/releases"><img src="https://img.shields.io/badge/Release-v0.1.1-blue?logo=github" alt="Release" /></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" /></a>
    <img src="https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white" alt="Python 3.11+" />
    <img src="https://img.shields.io/badge/Sandbox-Bubblewrap-purple?logo=linux&logoColor=white" alt="Bubblewrap" />
    <img src="https://img.shields.io/badge/Compatibility-Wine%20%7C%20Proton-darkred?logo=wine&logoColor=white" alt="Wine | Proton" />
    <img src="https://img.shields.io/badge/GUI-GTK4%20%7C%20Libadwaita-blue?logo=gnome&logoColor=white" alt="GTK4 | Libadwaita" />
    <img src="https://img.shields.io/badge/Database-SQLite%20WAL-003B57?logo=sqlite&logoColor=white" alt="SQLite WAL" />
    <img src="https://img.shields.io/badge/Packages-Debian%20%7C%20Fedora%20%7C%20Arch-informational" alt="Distros" />
  </p>

  <p>
    <a href="#core-security-principles">Security</a> •
    <a href="#key-features">Features</a> •
    <a href="#installation">Installation</a> •
    <a href="#quick-start">Quick Start</a> •
    <a href="CHANGELOG.md">Changelog</a> •
    <a href="LICENSE">License</a>
  </p>
</div>

---

## Core Security Principles

- **Hardware Allowed, Host Filesystem Denied** — Applications access required display, audio, GPU, and controllers without exposing your host `$HOME`.
- **Isolated by Default. Access by Explicit Policy.** — Every permission (`display`, `audio`, `network`, `gpu`, `gamepad`, `hidraw`, `mic`) and custom mount is strictly governed by a `SecurityProfile` / `SecurityPolicy`.
- **No Sandbox, No Execution.** — Windows binaries and Wine utilities (`winecfg`, `regedit`, `winetricks`) never execute on the host outside Bubblewrap.

---

## Key Features

- **Per-Prefix Bubblewrap Sandboxing**: Isolated virtual `HOME` per prefix, symlink-escape auditing, `Z:` drive neutralization, `PULSE_SOURCE=null` microphone mute when `mic` is disabled, and `/dev/hidraw*` passthrough for steering wheels, flight sticks, and DualSense controllers.
- **GTK4 + Libadwaita Desktop GUI (`winebox gui`)**:
  - **Library**: Search, `Play`/`Kill`, Lutris-style overflow actions (`View Logs`, `Open Prefix Files`, `Winecfg`, `Winetricks`, `Desktop Shortcut`, `Rename`, `Manage Groups`), and 4-tab **Configure App** dialog (*App & Runner*, *Sandbox*, *Env & Mounts*, *Shortcut*).
  - **Multi-Tag Application Groups**: Organize apps into custom categories with collapsible Section Expanders (`Gtk.Expander`) and count badges.
  - **In-App Update System**: ETag-cached GitHub release checker with HeaderBar update badge, Git pull auto-updater, and distro package downloader.
  - **Modal Operation Progress Dialog**: Real-time visual spinner, live log streaming, and zero auto-close (manual dismissal) for Create Prefix, Backup, and Restore.
  - **Prefixes & File Manager**: Create prefixes, launch sandboxed Wine tools, audit, backup/restore snapshots with custom destination picker, kill processes, and browse/launch files.
  - **Runners**: Manage system Wine and download/install Proton and Wine-GE runners with progress tracking.
  - **Security Profiles**: Built-in presets (`permissive`, `balanced`, `zero-trust`, `paranoid`) and custom profile creator.
  - **System Doctor**: Verify host `bwrap`, unprivileged user namespaces, Wine, GPU/DRI, and audio readiness.
- **Real-Time Live Process Streaming & Observability**: Line-by-line streaming of game stdout/stderr to `execution.log` (Lutris-style) with a 100 MB rotating policy and upgraded `LogViewerDialog` (auto-refresh, copy, clear).
- **Persistent XDG Shortcuts**: Shortcut settings (`menu_enabled`, `desktop_enabled`, custom icon, categories, `Terminal`, `StartupWMClass`) persisted in SQLite and synced to `~/.local/share/applications/` and `~/Desktop`.

---

## System Prerequisites

- **OS**: Modern Linux distribution (Debian/Ubuntu, Fedora/RHEL, Arch/Manjaro) with Linux kernel `>= 5.4` and unprivileged user namespaces enabled.
- **Runtime**: `bubblewrap` (`bwrap`), `python3 >= 3.11`, and `wine` (or a Proton/Wine-GE runner installed via `winebox runner`).
- **GUI**: `python3-gi` / `python-gobject`, `gtk4`, and `libadwaita`.

---

## Installation

### Debian / Ubuntu (`.deb`)
```bash
sudo apt install ./winebox_0.1.1_all.deb
```

### Fedora / RHEL (`.rpm`)
```bash
sudo dnf install ./winebox-0.1.1-1.fc45.noarch.rpm
```

### Arch Linux / Manjaro / CachyOS (`.pkg.tar.zst`)
```bash
sudo pacman -U ./winebox-0.1.1-1-any.pkg.tar.zst
```

### Portable Installer (Any Linux Distro, No `sudo` Required)
```bash
tar -xzf winebox-0.1.1-linux-noarch.tar.gz
cd winebox-0.1.1
./scripts/install.sh
```

### From Source (Development)
```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e .
```

### Building Multi-Distro Packages
```bash
./scripts/build_all.sh
```
*(Builds `.tar.gz`, `.deb`, and uses Docker `archlinux:latest` / `fedora:latest` to produce `.pkg.tar.zst` and `.rpm` when `makepkg`/`rpmbuild` are not installed on the host.)*

---

## Quick Start

```bash
# Launch the GTK4 + Libadwaita desktop GUI
winebox gui

# Check host readiness (bwrap, userns, Wine, GPU, audio)
winebox system doctor

# Interactive wizard to install or register an .exe/.msi
winebox add /path/to/app_or_installer.exe

# Run a registered application inside its sandbox
winebox app run <app_id>

# Manage prefixes, groups, security profiles, and runners
winebox prefix list
winebox group list
winebox profile list
winebox runner list
```

---

## XDG Data & Configuration Layout

All WineBox data is stored rootless under standard XDG directories:

- **Data (`~/.local/share/winebox/`)**:
  - `winebox.db`: Centralized SQLite configuration database (prefixes, applications, groups, security profiles, runners, shortcut metadata).
  - `prefixes/<prefix-id>/`: Isolated Wine prefix (`prefix/`, isolated `home/`, `logs/execution.log`, `prefix.lock`).
  - `runners/`: Managed custom Wine/Proton runners.
  - `cache/winetricks/`: Shared Winetricks download cache.
  - `cache/update_cache.json`: ETag-cached release metadata for in-app updates.
- **Configuration (`~/.config/winebox/`)**: Global WineBox settings.

---

## Documentation & Decisions

- Architecture and design records are documented in [docs/03-decisions/](docs/03-decisions/).
- Release history and notable changes are in [CHANGELOG.md](CHANGELOG.md).

---

## License

This project is licensed under the [MIT License](LICENSE).
