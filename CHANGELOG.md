# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.1] - 2026-11-17

### Added
- **In-App Update System (`UpdateService` & `UpdateDialog`)**:
  - Automated release checking via GitHub Releases API using HTTP ETag conditional requests (`If-None-Match: <etag>`) to avoid rate-limit consumption.
  - 15-minute background cooldown caching with instant manual "Check for Updates" bypass.
  - Dual installation mode execution:
    - **Git Mode:** In-app `git pull --ff-only` with post-update restart prompts.
    - **Distro Package Mode:** Automatic distro detection (`/etc/os-release`), downloading matching `.deb`, `.rpm`, `.pkg.tar.zst`, or portable tarball directly to `~/Downloads/`.
  - HeaderBar update notification badge pill (`[ ⬆ Update: vX.Y.Z ]`) and detailed changelog release notes viewer.
- **Modal Operation Progress Dialog (`OperationProgressDialog`)**:
  - Replaced transient auto-dismissing toasts for critical operations (Create Prefix, Backup, Restore) with a modal `Adw.Dialog`.
  - Active visual spinner, real-time status line, and embedded expandable execution log stream.
  - Zero auto-close policy: remains visible on completion with green `✓` or error `✕` badge, requiring manual confirmation via `Close` button.
- **Multi-tag Application Groups & Library Section Expanders**:
  - Many-to-Many application grouping schema (`groups` and `app_groups` tables).
  - Library page organized into collapsible Section Expanders (`Gtk.Expander`) with count badges, plus an *Uncategorized* section.
  - `GroupAssignmentDialog` for checklist tagging and inline category creation.
  - Full CLI command suite: `winebox group list|create|rename|delete` and `winebox app set-groups`.
- **Real-Time Live Process Streaming & Observability (Lutris-style)**:
  - Non-blocking daemon reader threads streaming stdout and stderr line-by-line into prefix `execution.log` with `bufsize=1` and `errors="replace"` decoding.
  - Log rotation policy expanded to 100 MB (`MAX_BYTES = 100 * 1024 * 1024`, 3 backup files).
  - Unified prefix event logging (`[APP]`, `[BACKUP]`, `[RESTORE]`, `[TOOL]`, `[WINETRICKS]`, `[KILL]`, `[AUDIT]`).
  - Upgraded `LogViewerDialog` with 2-second auto-refresh polling timer, manual refresh, clipboard copying, and clear logs with confirmation.
- **Application Renaming & Desktop Shortcut Flexibility**:
  - Rename applications directly from Tab 4 (Shortcut) in `ConfigureAppDialog` with real-time bidirectional synchronization with Tab 1.
  - Quick "Rename Application" prompt in Library card popover menu.
  - Added `--name` option to CLI: `winebox app desktop <app_id> --name <new_name>`.
- **Prefix Backup & Restore Enhancements**:
  - Custom backup file destination picker using native `Gtk.FileDialog`.
  - Direct restore into selected prefix with atomic rollback staging safety.

### Fixed
- **Kill Switch & Sandbox PID Safety**:
  - Skipped self-PID in `kill_prefix` to prevent parent WineBox GUI termination.
  - Recursively terminated child descendant PIDs trapped inside the Bubblewrap sandbox.
- **Wine Console Without TTY**:
  - Launched `cmd` via `wineconsole` when invoked from GUI without an active terminal.
- **Wine Tool Termination Signals**:
  - Handled SIGTERM/SIGKILL exit codes (-15, -9, 143, 137) on Wine tools as normal user termination instead of surfacing spurious error toasts.
- **Tool Hardware & Runner Propagation**:
  - Passed custom runner path, audio, and GPU permissions to Wine utilities (`winecfg`, `regedit`).
- **UI Typography**:
  - Replaced dot bullet separators (`•`) with hyphens (`-`) across card subtitles, runner rows, and configuration descriptions.

---

## [0.1.0] - 2026-11-15

### Added
- Initial public release of WineBox.
- Secure orchestrator for Windows applications in Linux using Bubblewrap (`bwrap`) isolation.
- Full hardware control policies: Display (X11/Wayland), Audio (PulseAudio/PipeWire), Network, GPU acceleration, Gamepad (evdev/SDL2), HIDRaw, and Microphone.
- Centralized SQLite repository with WAL mode and local per-prefix snapshot synchronization.
- Four-tab Application Configuration Dialog (`ConfigureAppDialog`) for Application & Runner, Sandbox Security, Environment & Host Mounts, and XDG Desktop Shortcuts.
- Multi-runner management (`wine-ge`, `proton`, `vanilla-wine`) with archive installation progress tracking and system Wine detection.
- Embedded Prefix File Manager with safe relative path traversal and instant Windows executable launching.
- Multi-distro package build scripts supporting Debian (`.deb`), Fedora (`.rpm`), Arch Linux (`.pkg.tar.zst`), and portable tarballs.
