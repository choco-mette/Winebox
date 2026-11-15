# WineBox

**WineBox** is a security-focused Linux orchestrator for managing and running Windows applications and games inside per-prefix **Bubblewrap (`bwrap`)** sandboxes, featuring a native **GTK4 + Libadwaita** desktop GUI and a **Typer** CLI.

## Core Security Principles

- **Hardware Allowed, Host Filesystem Denied** — Applications can access required display, audio, GPU, and controller devices without exposing your host `$HOME`.
- **Isolated by Default. Hardware Access by Policy.** — Every permission (`display`, `audio`, `network`, `gpu`, `gamepad`, `hidraw`, `mic`) and custom mount is explicitly governed by a `SecurityProfile` / `SecurityPolicy`.
- **No Sandbox, No Execution.** — Windows binaries and Wine tools (`winecfg`, `regedit`, `winetricks`) are never executed directly on the host outside Bubblewrap.

---

## Key Features

- **Per-Prefix Bubblewrap Sandboxing**: Isolated virtual `HOME` per prefix, symlink-escape auditing, `Z:` drive neutralization, `PULSE_SOURCE=null` microphone mute when `mic` is disabled, and `/dev/hidraw*` passthrough for wheels, flight sticks, and DualSense controllers.
- **GTK4 + Libadwaita Desktop GUI (`winebox gui`)**:
  - **Library**: Search, `Play`/`Kill`, Lutris-style overflow actions (`View Logs`, `Open Prefix Files`, `Winecfg`, `Winetricks`, `Create/Remove Desktop Shortcut`, `Remove`), and a 4-tab **Configure App** dialog (*App & Runner*, *Sandbox*, *Env & Mounts*, *Shortcut*).
  - **Prefixes & File Manager**: Create prefixes, launch sandboxed Wine tools, audit, backup/restore snapshots, kill processes, and browse/manage files inside prefixes.
  - **Runners**: Manage system Wine and download/install/share Proton/Wine-GE runners with live progress.
  - **Security Profiles**: Built-in presets (`permissive`, `balanced`, `zero-trust`, `paranoid`) plus full custom profile creation and deletion.
  - **System Doctor**: Verify host `bwrap`, unprivileged user namespaces, Wine, GPU/DRI, and audio readiness.
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
sudo apt install ./winebox_0.1.0_all.deb
```

### Fedora / RHEL (`.rpm`)
```bash
sudo dnf install ./winebox-0.1.0-1.fc45.noarch.rpm
```

### Arch Linux / Manjaro / CachyOS (`.pkg.tar.zst`)
```bash
sudo pacman -U ./winebox-0.1.0-1-any.pkg.tar.zst
```

### Portable Installer (Any Linux Distro, No `sudo` Required)
```bash
tar -xzf winebox-0.1.0-linux-noarch.tar.gz
cd winebox-0.1.0
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

# Manage prefixes, security profiles, and runners
winebox prefix list
winebox profile list
winebox runner list
```

---

## XDG Data & Configuration Layout

All WineBox data is stored rootless under standard XDG directories:

- **Data (`~/.local/share/winebox/`)**:
  - `winebox.db`: Centralized SQLite configuration database (prefixes, applications, security profiles, runners, shortcut metadata).
  - `prefixes/<prefix-id>/`: Isolated Wine prefix (`prefix/`, isolated `home/`, `logs/`, `prefix.lock`).
  - `runners/`: Managed custom Wine/Proton runners.
  - `cache/winetricks/`: Shared Winetricks download cache.
- **Configuration (`~/.config/winebox/`)**: Global WineBox settings.

---

## License

MIT
