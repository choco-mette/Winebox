"""3-tab Lutris-style Configure App dialog for GTK4 + Libadwaita."""

import shlex
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from gi.repository import Adw, Gio, Gtk
from winebox.domain.models import (
    Application,
    HostMount,
    MountMode,
    SecurityPolicy,
    SecurityProfile,
    ShortcutSettings,
)
from winebox.interface.gui.state import ServiceContainer


_SANDBOX_FLAGS: Tuple[Tuple[str, str, str], ...] = (
    ("display", "Display (X11 / Wayland)", "Allow graphical window rendering"),
    ("audio", "Audio (PulseAudio / PipeWire)", "Allow speaker / headphone output"),
    ("network", "Network Access", "Allow internet and LAN access inside sandbox"),
    ("gpu", "GPU Acceleration (DRI)", "Allow hardware Direct Rendering Infrastructure"),
    ("gamepad", "Gamepad / Joystick", "Bind /dev/input controller and evdev nodes"),
    ("hidraw", "Raw HID (/dev/hidraw*)", "Direct HID access for wheels, flight sticks, and DualSense"),
    ("mic", "Microphone Capture", "Allow audio input capture (muted via PULSE_SOURCE=null when off)"),
)


class ConfigureAppDialog(Adw.Dialog):
    """3-tab Adw.Dialog for editing App & Runner, Sandbox, and Env & Mounts."""

    def __init__(
        self,
        parent_window: Adw.ApplicationWindow,
        services: ServiceContainer,
        app_obj: Application,
        on_saved: Callable[[str], None],
    ) -> None:
        super().__init__(title=f"Configure {app_obj.name}", content_width=660, content_height=560)
        self._parent = parent_window
        self._services = services
        self._app = app_obj
        self._on_saved = on_saved
        self._updating_profile = False

        self._runners = self._services.runner_svc.list_runners()
        self._profiles: List[SecurityProfile] = self._services.profile_svc.list_profiles()
        self._env_vars: Dict[str, str] = dict(app_obj.policy.env_vars)
        self._host_mounts: List[HostMount] = list(app_obj.policy.host_mounts)
        self._switches: Dict[str, Adw.SwitchRow] = {}
        self._env_rows: List[Gtk.Widget] = []
        self._mount_rows: List[Gtk.Widget] = []

        self._toast_overlay = Adw.ToastOverlay()
        toolbar = Adw.ToolbarView()
        self._toast_overlay.set_child(toolbar)
        self.set_child(self._toast_overlay)

        self._stack = Adw.ViewStack()
        switcher = Adw.ViewSwitcher(stack=self._stack, policy=Adw.ViewSwitcherPolicy.WIDE)

        header = Adw.HeaderBar(
            show_start_title_buttons=False,
            show_end_title_buttons=False,
            title_widget=switcher,
        )
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda *_: self.close())
        header.pack_start(cancel_btn)

        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save_clicked)
        header.pack_end(save_btn)
        toolbar.add_top_bar(header)

        self._build_app_tab()
        self._build_sandbox_tab()
        self._build_system_tab()
        self._build_shortcut_tab()
        toolbar.set_content(self._stack)

    def _build_app_tab(self) -> None:
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(
            title="Application and Runner",
            description=f"Prefix: {self._app.prefix_id}  •  ID: {self._app.id}",
        )

        self._name_row = Adw.EntryRow(title="Application Name")
        self._name_row.set_text(self._app.name)
        group.add(self._name_row)

        self._exe_row = Adw.EntryRow(title="Executable Path")
        self._exe_row.set_text(self._app.exe_path)
        browse_btn = Gtk.Button(label="Browse...")
        browse_btn.set_valign(Gtk.Align.CENTER)
        browse_btn.connect("clicked", self._on_browse_exe)
        self._exe_row.add_suffix(browse_btn)
        group.add(self._exe_row)

        self._args_row = Adw.EntryRow(title="Launch Arguments")
        self._args_row.set_text(shlex.join(self._app.arguments) if self._app.arguments else "")
        group.add(self._args_row)

        self._runner_row = Adw.ComboRow(title="Wine / Proton Runner")
        runner_ids = [r.id for r in self._runners]
        self._runner_row.set_model(Gtk.StringList.new(runner_ids or [self._app.runner_id]))
        if self._app.runner_id in runner_ids:
            self._runner_row.set_selected(runner_ids.index(self._app.runner_id))
        group.add(self._runner_row)

        page.add(group)
        self._stack.add_titled_with_icon(page, "app", "App & Runner", "applications-games-symbolic")

    def _build_sandbox_tab(self) -> None:
        page = Adw.PreferencesPage()
        preset_group = Adw.PreferencesGroup(title="Security Profile Preset")

        self._profile_row = Adw.ComboRow(title="Base Profile")
        profile_ids = [p.id for p in self._profiles]
        self._profile_row.set_model(Gtk.StringList.new(profile_ids or [self._app.profile_id]))
        self._updating_profile = True
        if self._app.profile_id in profile_ids:
            self._profile_row.set_selected(profile_ids.index(self._app.profile_id))
        self._updating_profile = False
        self._profile_row.connect("notify::selected", self._on_profile_changed)
        preset_group.add(self._profile_row)
        page.add(preset_group)

        perm_group = Adw.PreferencesGroup(
            title="Per-App Sandbox Overrides",
            description="Customizes hardware and network isolation for this application.",
        )
        for key, title, subtitle in _SANDBOX_FLAGS:
            sw = Adw.SwitchRow(title=title, subtitle=subtitle)
            sw.set_active(bool(getattr(self._app.policy, key, False)))
            self._switches[key] = sw
            perm_group.add(sw)
        page.add(perm_group)

        self._stack.add_titled_with_icon(page, "sandbox", "Sandbox", "security-high-symbolic")

    def _build_system_tab(self) -> None:
        page = Adw.PreferencesPage()

        # Environment variables group
        self._env_group = Adw.PreferencesGroup(
            title="Environment Variables",
            description="Injected into Wine (e.g. DXVK_HUD=fps, WINEDLLOVERRIDES=...).",
        )
        env_add_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        env_add_box.set_margin_bottom(6)
        self._env_key_entry = Gtk.Entry(placeholder_text="KEY (e.g. DXVK_HUD)", hexpand=True)
        self._env_val_entry = Gtk.Entry(placeholder_text="VALUE (e.g. fps)", hexpand=True)
        env_add_btn = Gtk.Button(label="+ Add")
        env_add_btn.add_css_class("suggested-action")
        env_add_btn.connect("clicked", self._on_add_env)
        env_add_box.append(self._env_key_entry)
        env_add_box.append(self._env_val_entry)
        env_add_box.append(env_add_btn)
        self._env_group.add(env_add_box)
        page.add(self._env_group)
        self._rebuild_env_rows()

        # Host mounts group
        self._mount_group = Adw.PreferencesGroup(
            title="Host Mounts",
            description="Bind extra host directories into the sandbox (validated by PolicyValidator).",
        )
        mount_add_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        mount_add_box.set_margin_bottom(6)
        self._mount_host_entry = Gtk.Entry(placeholder_text="Host path (/home/.../saves)", hexpand=True)
        self._mount_sandbox_entry = Gtk.Entry(placeholder_text="Sandbox path (/mnt/saves)", hexpand=True)
        self._mount_ro_switch = Gtk.Switch(valign=Gtk.Align.CENTER, active=True)
        self._mount_ro_switch.set_tooltip_text("Read-Only when active, Read-Write when off")
        ro_lbl = Gtk.Label(label="RO")
        ro_lbl.add_css_class("dim-label")
        mount_add_btn = Gtk.Button(label="+ Add")
        mount_add_btn.add_css_class("suggested-action")
        mount_add_btn.connect("clicked", self._on_add_mount)
        mount_add_box.append(self._mount_host_entry)
        mount_add_box.append(self._mount_sandbox_entry)
        mount_add_box.append(ro_lbl)
        mount_add_box.append(self._mount_ro_switch)
        mount_add_box.append(mount_add_btn)
        self._mount_group.add(mount_add_box)
        page.add(self._mount_group)
        self._rebuild_mount_rows()

        self._stack.add_titled_with_icon(page, "system", "Env & Mounts", "preferences-system-symbolic")

    def _rebuild_env_rows(self) -> None:
        for row in self._env_rows:
            self._env_group.remove(row)
        self._env_rows.clear()
        for key, val in sorted(self._env_vars.items()):
            row = Adw.ActionRow(title=key, subtitle=val)
            del_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
            del_btn.add_css_class("flat")
            del_btn.set_valign(Gtk.Align.CENTER)
            del_btn.connect("clicked", lambda _b, k=key: self._remove_env(k))
            row.add_suffix(del_btn)
            self._env_group.add(row)
            self._env_rows.append(row)

    def _rebuild_mount_rows(self) -> None:
        for row in self._mount_rows:
            self._mount_group.remove(row)
        self._mount_rows.clear()
        for idx, mount in enumerate(self._host_mounts):
            row = Adw.ActionRow(
                title=f"{mount.host_path} -> {mount.sandbox_path}",
                subtitle=f"Mode: {mount.mode.value.upper()}",
            )
            del_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
            del_btn.add_css_class("flat")
            del_btn.set_valign(Gtk.Align.CENTER)
            del_btn.connect("clicked", lambda _b, i=idx: self._remove_mount(i))
            row.add_suffix(del_btn)
            self._mount_group.add(row)
            self._mount_rows.append(row)

    def _show_toast(self, message: str, timeout: int = 3) -> None:
        toast = Adw.Toast.new(message)
        toast.set_timeout(timeout)
        self._toast_overlay.add_toast(toast)

    def _on_add_env(self, *_args: object) -> None:
        key = self._env_key_entry.get_text().strip()
        val = self._env_val_entry.get_text().strip()
        if not key:
            self._show_toast("Environment key cannot be empty")
            return
        self._env_vars[key] = val
        self._env_key_entry.set_text("")
        self._env_val_entry.set_text("")
        self._rebuild_env_rows()

    def _remove_env(self, key: str) -> None:
        self._env_vars.pop(key, None)
        self._rebuild_env_rows()

    def _on_add_mount(self, *_args: object) -> None:
        host_raw = self._mount_host_entry.get_text().strip()
        sandbox_raw = self._mount_sandbox_entry.get_text().strip()
        if not host_raw or not sandbox_raw:
            self._show_toast("Host path and sandbox path are required")
            return
        mode = MountMode.RO if self._mount_ro_switch.get_active() else MountMode.RW
        self._host_mounts.append(HostMount(host_path=Path(host_raw), sandbox_path=Path(sandbox_raw), mode=mode))
        self._mount_host_entry.set_text("")
        self._mount_sandbox_entry.set_text("")
        self._rebuild_mount_rows()

    def _remove_mount(self, idx: int) -> None:
        if 0 <= idx < len(self._host_mounts):
            self._host_mounts.pop(idx)
            self._rebuild_mount_rows()

    def _on_profile_changed(self, *_args: object) -> None:
        if self._updating_profile or not self._profiles:
            return
        idx = self._profile_row.get_selected()
        if idx == Gtk.INVALID_LIST_POSITION or idx >= len(self._profiles):
            return
        prof = self._profiles[idx]
        for key, sw in self._switches.items():
            sw.set_active(bool(getattr(prof, key, False)))

    def _on_browse_exe(self, *_args: object) -> None:
        prefix_inner = (self._services.repo.get_prefix_dir(self._app.prefix_id) / "prefix").resolve()
        drive_c = prefix_inner / "drive_c"
        start_dir = drive_c if drive_c.is_dir() else prefix_inner

        dlg = Gtk.FileDialog(title="Select Windows Executable")
        if start_dir.is_dir():
            dlg.set_initial_folder(Gio.File.new_for_path(str(start_dir)))

        def _on_chosen(dialog: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
            try:
                gfile = dialog.open_finish(res)
                if gfile and gfile.get_path():
                    chosen = Path(gfile.get_path()).resolve()
                    if chosen.is_relative_to(prefix_inner):
                        self._exe_row.set_text(chosen.relative_to(prefix_inner).as_posix())
                    else:
                        self._exe_row.set_text(str(chosen))
            except Exception:
                pass

        dlg.open(self._parent, None, _on_chosen)

    def _build_shortcut_tab(self) -> None:
        page = Adw.PreferencesPage()
        sc = self._app.shortcut

        place_group = Adw.PreferencesGroup(
            title="Shortcut Placement",
            description="Choose where WineBox generates and syncs .desktop launchers.",
        )
        self._menu_switch = Adw.SwitchRow(
            title="Application Menu",
            subtitle="Install to XDG applications menu (~/.local/share/applications)",
        )
        self._menu_switch.set_active(
            sc.menu_enabled or self._services.desktop_svc.desktop_entry_exists(self._app.id)
        )
        place_group.add(self._menu_switch)

        self._desktop_switch = Adw.SwitchRow(
            title="Desktop Folder Icon",
            subtitle="Create clickable .desktop icon in Desktop folder (KDE, XFCE, Cinnamon, MATE, GNOME DING)",
        )
        self._desktop_switch.set_active(
            sc.desktop_enabled or self._services.desktop_svc.desktop_icon_exists(self._app.id)
        )
        place_group.add(self._desktop_switch)
        page.add(place_group)

        meta_group = Adw.PreferencesGroup(
            title="Appearance and Launch",
            description="Persisted in SQLite and synced to generated .desktop files on Save.",
        )
        self._sc_name_row = Adw.EntryRow(title="Application / Shortcut Name")
        self._sc_name_row.set_text(self._app.name)
        meta_group.add(self._sc_name_row)

        def _sync_sc_name(*_args: object) -> None:
            txt = self._sc_name_row.get_text()
            if self._name_row.get_text() != txt:
                self._name_row.set_text(txt)

        def _sync_app_name(*_args: object) -> None:
            txt = self._name_row.get_text()
            if self._sc_name_row.get_text() != txt:
                self._sc_name_row.set_text(txt)

        self._sc_name_row.connect("notify::text", _sync_sc_name)
        self._name_row.connect("notify::text", _sync_app_name)

        self._sc_icon_row = Adw.EntryRow(title="Icon (theme name or image path)")
        self._sc_icon_row.set_text(sc.icon)
        icon_btn = Gtk.Button(label="Browse...")
        icon_btn.set_valign(Gtk.Align.CENTER)
        icon_btn.connect("clicked", self._on_browse_icon)
        self._sc_icon_row.add_suffix(icon_btn)
        meta_group.add(self._sc_icon_row)

        self._sc_cat_row = Adw.EntryRow(title="Categories (semicolon-separated)")
        self._sc_cat_row.set_text(sc.categories or "Game;Utility;")
        meta_group.add(self._sc_cat_row)

        self._sc_comment_row = Adw.EntryRow(title="Comment / Description")
        self._sc_comment_row.set_text(sc.comment)
        meta_group.add(self._sc_comment_row)

        self._sc_terminal_switch = Adw.SwitchRow(
            title="Run in Terminal",
            subtitle="Set Terminal=true to inspect console stdout/stderr",
        )
        self._sc_terminal_switch.set_active(sc.terminal)
        meta_group.add(self._sc_terminal_switch)

        self._sc_wmclass_row = Adw.EntryRow(title="StartupWMClass (optional)")
        self._sc_wmclass_row.set_text(sc.startup_wm_class)
        meta_group.add(self._sc_wmclass_row)

        page.add(meta_group)
        self._stack.add_titled_with_icon(page, "shortcut", "Shortcut", "starred-symbolic")

    def _on_browse_icon(self, *_args: object) -> None:
        dlg = Gtk.FileDialog(title="Select Shortcut Icon (.png / .svg / .ico)")
        img_filter = Gtk.FileFilter()
        img_filter.set_name("Icon Images")
        for pat in ("*.png", "*.svg", "*.ico", "*.xpm"):
            img_filter.add_pattern(pat)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(img_filter)
        dlg.set_filters(filters)

        def _on_chosen(dialog: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
            try:
                gfile = dialog.open_finish(res)
                if gfile and gfile.get_path():
                    self._sc_icon_row.set_text(gfile.get_path())
            except Exception:
                pass

        dlg.open(self._parent, None, _on_chosen)

    def _on_save_clicked(self, *_args: object) -> None:
        app_name = (self._name_row.get_text() or self._sc_name_row.get_text()).strip()
        if not app_name:
            self._show_toast("Application name cannot be empty")
            return

        args_raw = self._args_row.get_text().strip()
        try:
            parsed_args = shlex.split(args_raw) if args_raw else []
        except ValueError as e:
            self._show_toast(f"Invalid arguments syntax: {e}")
            return

        r_idx = self._runner_row.get_selected()
        runner_id = (
            self._runners[r_idx].id
            if self._runners and r_idx != Gtk.INVALID_LIST_POSITION and r_idx < len(self._runners)
            else self._app.runner_id
        )
        p_idx = self._profile_row.get_selected()
        profile_id = (
            self._profiles[p_idx].id
            if self._profiles and p_idx != Gtk.INVALID_LIST_POSITION and p_idx < len(self._profiles)
            else self._app.profile_id
        )

        policy = SecurityPolicy(
            display=self._switches["display"].get_active(),
            audio=self._switches["audio"].get_active(),
            network=self._switches["network"].get_active(),
            gpu=self._switches["gpu"].get_active(),
            gamepad=self._switches["gamepad"].get_active(),
            hidraw=self._switches["hidraw"].get_active(),
            mic=self._switches["mic"].get_active(),
            host_mounts=list(self._host_mounts),
            env_vars=dict(self._env_vars),
        )

        shortcut = ShortcutSettings(
            menu_enabled=self._menu_switch.get_active(),
            desktop_enabled=self._desktop_switch.get_active(),
            icon=self._sc_icon_row.get_text().strip(),
            categories=self._sc_cat_row.get_text().strip() or "Game;Utility;",
            comment=self._sc_comment_row.get_text().strip(),
            terminal=self._sc_terminal_switch.get_active(),
            startup_wm_class=self._sc_wmclass_row.get_text().strip(),
        )

        try:
            updated = self._services.app_svc.update_app(
                self._app.id,
                name=app_name,
                exe_path=self._exe_row.get_text(),
                runner_id=runner_id,
                profile_id=profile_id,
                arguments=parsed_args,
                policy=policy,
                shortcut=shortcut,
            )
            self._services.desktop_svc.sync_shortcuts(updated.id)
            self._on_saved(f"Updated '{updated.name}'")
            self.close()
        except Exception as e:
            self._show_toast(f"Save failed: {e}")
