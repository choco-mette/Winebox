# Development Setup

Panduan mempersiapkan lingkungan pengembangan lokal:

## 1. Prasyarat Sistem
Distribusi Linux dengan dependensi berikut terpasang:
```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y python3 python3-pip python3-venv bubblewrap wine

# Arch Linux
sudo pacman -S python bubblewrap wine

# Fedora
sudo dnf install python3 bubblewrap wine
```

## 2. Inisialisasi Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 3. Menjalankan CLI dalam Mode Pengembangan
```bash
winebox --help
winebox system doctor
```

## 4. Menjalankan Linter & Test
```bash
ruff check src/
pytest
```

