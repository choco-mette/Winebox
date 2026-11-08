# Configuration Specification

Dokumen ini mendefinisikan skema file konfigurasi WineBox.

## 1. Lokasi Berkas Konfigurasi (XDG Standard)

- **Konfigurasi Global:** `$XDG_CONFIG_HOME/winebox/config.toml` (default: `~/.config/winebox/config.toml`)
- **Metadata Aplikasi:** `$XDG_DATA_HOME/winebox/applications/<app-id>.toml`
- **Metadata Prefix:** `$XDG_DATA_HOME/winebox/prefixes/<prefix-id>/config.toml`
- **Metadata Runner:** `$XDG_DATA_HOME/winebox/runners/<runner-id>.toml`

---

## 2. Skema Konfigurasi Global (`~/.config/winebox/config.toml`)

```toml
[system]
default_runner = "system-wine"
check_doctor_on_startup = true

[security]
default_display = true
default_audio = true
default_network = true
default_gpu = true

[storage]
data_dir = "~/.local/share/winebox"
```

---

## 3. Skema Metadata Aplikasi (`applications/<app-id>.toml`)

```toml
[application]
id = "notepad-plus"
name = "Notepad++"
prefix_id = "default"
exe_path = "drive_c/Program Files/Notepad++/notepad++.exe"
runner_id = "system-wine"
status = "ready"
created_at = "2026-11-08T19:30:00Z"

[arguments]
default_args = []

[policy]
display = true
audio = true
network = true
gpu = true

[[policy.host_mounts]]
host_path = "/home/user/Documents/Projects"
sandbox_path = "/mnt/projects"
mode = "ro"

[environment]
WINEESYNC = "1"
```

