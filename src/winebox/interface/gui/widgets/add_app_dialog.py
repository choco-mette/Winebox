"""Dialog wizard for registering or importing a Windows app into WineBox."""

from pathlib import Path
from typing import Callable, Optional
from gi.repository import Adw, Gio, Gtk
from winebox.interface.gui.state import ServiceContainer, run_async
from winebox.interface.tui.utils import slugify


class AddAppDialog(Adw.Dialog):
    """Interactive dialog to register an executable inside an existing prefix or import a portable folder."""

    def __init__(
        self,
        parent_window: Adw.ApplicationWindow,
        services: ServiceContainer,
        on_added: Callable[[str], None],
        default_prefix_id: Optional[str] = None,
        default_exe_path: Optional[str] = None,
    ) -> None:
        super().__init__(title="Add Windows Application", content_width=520, content_height=460)
        self._parent = parent_window
        self._services = services
        self._on_added = on_added
        self._portable_dir: Optional[Path] = None

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda *_: self.close())
        header.pack_start(cancel_btn)

        self._submit_btn = Gtk.Button(label="Register")
        self._submit_btn.add_css_class("suggested-action")
        self._submit_btn.connect("clicked", self._on_submit)
        header.pack_end(self._submit_btn)
        toolbar.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        group = Adw.PreferencesGroup(title="Application Details")
        self._name_row = Adw.EntryRow(title="Display Name")
        self._exe_row = Adw.EntryRow(title="Executable Path (relative to drive_c or C:\\...)")
        if default_exe_path:
            self._exe_row.set_text(default_exe_path)
            self._name_row.set_text(Path(default_exe_path.replace("\\", "/")).stem)
        group.add(self._name_row)
        group.add(self._exe_row)

        # Prefix dropdown
        self._prefixes = services.prefix_lifecycle.list_prefixes()
        prefix_model = Gtk.StringList.new([p.id for p in self._prefixes] or ["(none)"])
        self._prefix_row = Adw.ComboRow(title="Target Prefix", model=prefix_model)
        if default_prefix_id:
            for idx, p in enumerate(self._prefixes):
                if p.id == default_prefix_id:
                    self._prefix_row.set_selected(idx)
                    break
        group.add(self._prefix_row)

        # Profile dropdown
        self._profiles = services.profile_svc.list_profiles()
        profile_model = Gtk.StringList.new([p.id for p in self._profiles])
        self._profile_row = Adw.ComboRow(title="Security Profile", model=profile_model)
        for idx, p in enumerate(self._profiles):
            if p.id == "permissive":
                self._profile_row.set_selected(idx)
                break
        group.add(self._profile_row)

        # Portable folder picker row
        self._portable_row = Adw.ActionRow(
            title="Or Import Portable Folder",
            subtitle="Optional: copy a host game/app folder into prefix drive_c",
        )
        pick_btn = Gtk.Button(label="Browse...")
        pick_btn.set_valign(Gtk.Align.CENTER)
        pick_btn.connect("clicked", self._on_pick_portable)
        self._portable_row.add_suffix(pick_btn)
        group.add(self._portable_row)

        self._desktop_row = Adw.SwitchRow(title="Create Desktop Menu Shortcut (.desktop)")
        group.add(self._desktop_row)

        box.append(group)
        toolbar.set_content(box)
        self.set_child(toolbar)

    def _on_pick_portable(self, *_args: object) -> None:
        dialog = Gtk.FileDialog(title="Select Portable Application Folder")
        dialog.select_folder(self._parent, None, self._on_folder_chosen)

    def _on_folder_chosen(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except Exception:
            return
        if folder and folder.get_path():
            self._portable_dir = Path(folder.get_path())
            self._portable_row.set_subtitle(str(self._portable_dir))
            if not self._name_row.get_text().strip():
                self._name_row.set_text(self._portable_dir.name)
            exes = self._services.import_svc.scan_portable_executables(self._portable_dir)
            if exes and not self._exe_row.get_text().strip():
                self._exe_row.set_text(exes[0])

    def _on_submit(self, *_args: object) -> None:
        if not self._prefixes:
            return
        name = self._name_row.get_text().strip()
        exe_path = self._exe_row.get_text().strip()
        if not name or not exe_path:
            return

        prefix_obj = self._prefixes[self._prefix_row.get_selected()]
        profile_obj = self._profiles[self._profile_row.get_selected()]
        app_id = slugify(name)
        create_desktop = self._desktop_row.get_active()
        self._submit_btn.set_sensitive(False)

        def _work() -> str:
            if self._portable_dir:
                app_obj = self._services.import_svc.import_portable_app(
                    source_dir=self._portable_dir,
                    prefix_id=prefix_obj.id,
                    app_id=app_id,
                    name=name,
                    exe_rel_path=exe_path,
                    profile_id=profile_obj.id,
                )
            else:
                app_obj = self._services.app_svc.register_app(
                    app_id=app_id,
                    name=name,
                    prefix_id=prefix_obj.id,
                    exe_path=exe_path,
                    profile_id=profile_obj.id,
                )
            if create_desktop:
                self._services.desktop_svc.create_desktop_entry(app_obj.id)
            return app_obj.name

        def _done(app_name: str) -> None:
            self.close()
            self._on_added(f"Registered '{app_name}'")

        def _err(exc: Exception) -> None:
            self._submit_btn.set_sensitive(True)
            self._parent.show_toast(f"Error: {exc}")

        run_async(_work, _done, _err)
