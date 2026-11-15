"""Embedded GTK4 Prefix File Manager widget with symlink guard and Drag & Drop."""

import shutil
from pathlib import Path
from typing import Callable, Optional
from gi.repository import Adw, Gdk, Gio, GObject, Gtk
from winebox.common.exceptions import WineboxError
from winebox.infrastructure.fs_adapter import FilesystemAdapter
from winebox.interface.gui.state import (
    PrefixFileEntry,
    ServiceContainer,
    format_size,
    list_prefix_directory,
    run_async,
)
from winebox.interface.gui.widgets.add_app_dialog import AddAppDialog


class _FileRowItem(GObject.Object):
    def __init__(self, entry: PrefixFileEntry) -> None:
        super().__init__()
        self.entry = entry


class PrefixFileManager(Gtk.Box):
    """Safe embedded file browser for prefix drive_c/, home/, and logs/."""

    def __init__(
        self,
        window: Adw.ApplicationWindow,
        services: ServiceContainer,
        on_refresh_apps: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._window = window
        self._services = services
        self._on_refresh_apps = on_refresh_apps

        self._prefix_id: Optional[str] = None
        self._scope: str = "drive_c"
        self._rel_path: str = ""

        # Top controls: scope tabs + up + open in host FM
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._scope_btns = {}
        for key, label in (("drive_c", "drive_c/"), ("home", "home/ (Saves)"), ("logs", "logs/")):
            btn = Gtk.ToggleButton(label=label)
            bar.append(btn)
            self._scope_btns[key] = btn
        self._scope_btns["drive_c"].set_active(True)
        for key, btn in self._scope_btns.items():
            btn.connect("toggled", self._on_scope_toggled, key)

        self._up_btn = Gtk.Button.new_from_icon_name("go-up-symbolic")
        self._up_btn.set_tooltip_text("Parent folder")
        self._up_btn.connect("clicked", self._on_go_up)
        bar.append(self._up_btn)

        self._path_label = Gtk.Label(label="", xalign=0.0, hexpand=True)
        self._path_label.add_css_class("dim-label")
        bar.append(self._path_label)

        open_host_btn = Gtk.Button(label="Open in Host FM")
        open_host_btn.connect("clicked", self._on_open_host_fm)
        bar.append(open_host_btn)
        self.append(bar)

        # ColumnView backed by Gio.ListStore
        self._store = Gio.ListStore.new(_FileRowItem)
        self._selection = Gtk.SingleSelection.new(self._store)
        self._column_view = Gtk.ColumnView(model=self._selection)
        self._column_view.connect("activate", self._on_row_activated)

        self._add_column("Name", self._bind_name, expand=True)
        self._add_column("Type", self._bind_type, expand=False)
        self._add_column("Size", self._bind_size, expand=False)
        self._add_column("Actions", self._bind_actions, expand=False)

        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True, min_content_height=260)
        scrolled.set_child(self._column_view)

        # Drag & drop target for importing mods/files
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop_files)
        scrolled.add_controller(drop_target)

        frame = Gtk.Frame()
        frame.set_child(scrolled)
        self.append(frame)

    def _add_column(self, title: str, bind_fn: Callable[[Gtk.ListItem, _FileRowItem], None], expand: bool) -> None:
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", lambda _f, item: item.set_child(Gtk.Box(spacing=6)))
        factory.connect("bind", lambda _f, item: bind_fn(item, item.get_item()))
        col = Gtk.ColumnViewColumn(title=title, factory=factory)
        col.set_expand(expand)
        self._column_view.append_column(col)

    def set_prefix(self, prefix_id: Optional[str]) -> None:
        self._prefix_id = prefix_id
        self._rel_path = ""
        self.refresh()

    def _current_root(self) -> Optional[Path]:
        if not self._prefix_id:
            return None
        p_dir = self._services.repo.get_prefix_dir(self._prefix_id)
        if self._scope == "drive_c":
            return p_dir / "prefix" / "drive_c"
        if self._scope == "home":
            return p_dir / "home"
        return p_dir / "logs"

    def refresh(self) -> None:
        self._store.remove_all()
        root = self._current_root()
        if not root:
            self._path_label.set_text("")
            return
        self._path_label.set_text(f"{self._scope}/{self._rel_path}" if self._rel_path else f"{self._scope}/")
        self._up_btn.set_sensitive(bool(self._rel_path))
        try:
            entries = list_prefix_directory(root, self._rel_path)
        except WineboxError as e:
            self._window.show_toast(str(e))
            return
        for entry in entries:
            self._store.append(_FileRowItem(entry))

    def _on_scope_toggled(self, btn: Gtk.ToggleButton, key: str) -> None:
        if not btn.get_active():
            return
        for k, other in self._scope_btns.items():
            if k != key and other.get_active():
                other.set_active(False)
        self._scope = key
        self._rel_path = ""
        self.refresh()

    def _on_go_up(self, *_args: object) -> None:
        if not self._rel_path:
            return
        parent = str(Path(self._rel_path).parent)
        self._rel_path = "" if parent == "." else parent
        self.refresh()

    def _on_row_activated(self, _view: Gtk.ColumnView, pos: int) -> None:
        item = self._store.get_item(pos)
        if not isinstance(item, _FileRowItem):
            return
        entry = item.entry
        if entry.is_symlink:
            self._window.show_toast("Symlink navigation blocked for sandbox safety.")
            return
        if entry.is_dir:
            self._rel_path = entry.rel_path
            self.refresh()

    def _bind_name(self, list_item: Gtk.ListItem, item: _FileRowItem) -> None:
        box = list_item.get_child()
        while child := box.get_first_child():
            box.remove(child)
        e = item.entry
        if e.is_symlink:
            icon_name = "emblem-symbolic-link"
        elif e.is_dir:
            icon_name = "folder-symbolic"
        else:
            ctype, _ = Gio.content_type_guess(e.name, None)
            icon_name = "application-x-executable-symbolic" if e.name.lower().endswith(".exe") else "text-x-generic-symbolic"
            _ = ctype
        box.append(Gtk.Image.new_from_icon_name(icon_name))
        box.append(Gtk.Label(label=e.name, xalign=0.0))

    def _bind_type(self, list_item: Gtk.ListItem, item: _FileRowItem) -> None:
        box = list_item.get_child()
        while child := box.get_first_child():
            box.remove(child)
        e = item.entry
        text = "Symlink" if e.is_symlink else ("Folder" if e.is_dir else "File")
        box.append(Gtk.Label(label=text, xalign=0.0))

    def _bind_size(self, list_item: Gtk.ListItem, item: _FileRowItem) -> None:
        box = list_item.get_child()
        while child := box.get_first_child():
            box.remove(child)
        e = item.entry
        text = "-" if (e.is_dir or e.is_symlink) else format_size(e.size_bytes)
        box.append(Gtk.Label(label=text, xalign=0.0))

    def _bind_actions(self, list_item: Gtk.ListItem, item: _FileRowItem) -> None:
        box = list_item.get_child()
        while child := box.get_first_child():
            box.remove(child)
        e = item.entry
        if not e.is_dir and not e.is_symlink and e.name.lower().endswith(".exe") and self._scope == "drive_c":
            reg_btn = Gtk.Button(label="Register App")
            reg_btn.add_css_class("flat")
            reg_btn.connect("clicked", lambda *_: self._register_exe(e))
            box.append(reg_btn)

        del_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        del_btn.add_css_class("flat")
        del_btn.set_tooltip_text("Delete")
        del_btn.connect("clicked", lambda *_: self._confirm_delete(e))
        box.append(del_btn)

    def _register_exe(self, entry: PrefixFileEntry) -> None:
        if not self._prefix_id:
            return
        exe_rel = f"drive_c/{entry.rel_path}"
        dlg = AddAppDialog(
            parent_window=self._window,
            services=self._services,
            on_added=lambda msg: (self._window.show_toast(msg), self._on_refresh_apps and self._on_refresh_apps()),
            default_prefix_id=self._prefix_id,
            default_exe_path=exe_rel,
        )
        dlg.present(self._window)

    def _confirm_delete(self, entry: PrefixFileEntry) -> None:
        dlg = Adw.AlertDialog.new(
            f"Delete '{entry.name}'?",
            "This permanently removes the file or directory from the prefix.",
        )
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("delete", "Delete")
        dlg.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.connect("response", lambda _d, resp: self._do_delete(entry) if resp == "delete" else None)
        dlg.present(self._window)

    def _do_delete(self, entry: PrefixFileEntry) -> None:
        root = self._current_root()
        if not root:
            return
        resolved_root = root.resolve()
        if not entry.full_path.parent.resolve().is_relative_to(resolved_root):
            return
        try:
            FilesystemAdapter.remove_tree(entry.full_path)
            self._window.show_toast(f"Deleted '{entry.name}'")
            self.refresh()
        except Exception as e:
            self._window.show_toast(f"Delete failed: {e}")

    def _on_open_host_fm(self, *_args: object) -> None:
        root = self._current_root()
        if not root:
            return
        target = (root / self._rel_path) if self._rel_path else root
        target.mkdir(parents=True, exist_ok=True)
        launcher = Gtk.FileLauncher.new(Gio.File.new_for_path(str(target)))
        launcher.launch(self._window, None, None)

    def _on_drop_files(self, _target: Gtk.DropTarget, value: Gdk.FileList, _x: float, _y: float) -> bool:
        root = self._current_root()
        if not root:
            return False
        dest_dir = (root / self._rel_path) if self._rel_path else root
        files = [Path(f.get_path()) for f in value.get_files() if f.get_path()]
        if not files:
            return False

        def _copy() -> int:
            dest_dir.mkdir(parents=True, exist_ok=True)
            for src in files:
                dst = dest_dir / src.name
                if src.is_dir():
                    shutil.copytree(src, dst, symlinks=True, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
            return len(files)

        run_async(
            _copy,
            on_success=lambda n: (self._window.show_toast(f"Copied {n} item(s) into prefix"), self.refresh()),
            on_error=lambda e: self._window.show_toast(f"Import failed: {e}"),
        )
        return True
