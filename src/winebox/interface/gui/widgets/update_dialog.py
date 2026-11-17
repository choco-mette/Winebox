"""Update dialog displaying release notes and providing Git/Package installation actions (ADR-020)."""

from pathlib import Path
from typing import Optional
from gi.repository import Adw, Gio, Gtk
from winebox.application.update_service import UpdateInfo
from winebox.interface.gui.state import ServiceContainer, run_async


class UpdateDialog(Adw.Dialog):
    """Displays changelog notes and executes Git pull or distro package download."""

    def __init__(
        self,
        parent_window: Adw.ApplicationWindow,
        services: ServiceContainer,
        update_info: UpdateInfo,
    ) -> None:
        super().__init__(title="WineBox Update", content_width=580, content_height=460)
        self._parent = parent_window
        self._services = services
        self._info = update_info

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar(show_start_title_buttons=False, show_end_title_buttons=False)
        close_btn = Gtk.Button(label="Close")
        close_btn.connect("clicked", lambda *_: self.close())
        header.pack_start(close_btn)
        toolbar.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)

        # Version status header
        info_banner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        up_icon = Gtk.Image.new_from_icon_name("software-update-available-symbolic")
        up_icon.set_pixel_size(40)
        up_icon.add_css_class("accent")
        info_banner.append(up_icon)

        text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        v_title = f"{self._info.release_title} Available" if self._info.has_update else "WineBox is Up to Date"
        lbl_title = Gtk.Label(label=v_title, halign=Gtk.Align.START)
        lbl_title.add_css_class("title-3")
        text_col.append(lbl_title)

        v_sub = f"Current version: v{self._info.current_version}  •  Latest version: v{self._info.latest_version}"
        lbl_sub = Gtk.Label(label=v_sub, halign=Gtk.Align.START)
        lbl_sub.add_css_class("dim-label")
        text_col.append(lbl_sub)
        info_banner.append(text_col)
        box.append(info_banner)

        # Changelog / Release notes viewer
        notes_group = Adw.PreferencesGroup(title="What's New")
        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scrolled.set_min_content_height(180)
        scrolled.add_css_class("card")

        text_view = Gtk.TextView(editable=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        text_view.set_top_margin(12)
        text_view.set_bottom_margin(12)
        text_view.set_left_margin(14)
        text_view.set_right_margin(14)
        text_view.get_buffer().set_text(self._info.release_notes)
        scrolled.set_child(text_view)
        notes_group.add(scrolled)
        box.append(notes_group)

        # Status / progress feedback
        self._status_label = Gtk.Label(label="", wrap=True)
        self._status_label.add_css_class("dim-label")
        box.append(self._status_label)

        # Action bar
        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        actions_box.set_halign(Gtk.Align.END)

        gh_btn = Gtk.Button(label="View on GitHub")
        gh_btn.connect("clicked", self._on_view_github)
        actions_box.append(gh_btn)

        if self._info.has_update:
            if self._info.is_git_install:
                self._update_btn = Gtk.Button(label="Update via Git")
                self._update_btn.add_css_class("suggested-action")
                self._update_btn.connect("clicked", self._on_git_update)
                actions_box.append(self._update_btn)
            elif self._info.matching_asset:
                asset_name = self._info.matching_asset.get("name", "package")
                self._update_btn = Gtk.Button(label=f"Download {asset_name}")
                self._update_btn.add_css_class("suggested-action")
                self._update_btn.connect("clicked", self._on_download_package)
                actions_box.append(self._update_btn)

        box.append(actions_box)
        toolbar.set_content(box)
        self.set_child(toolbar)

    def _on_view_github(self, *_args: object) -> None:
        try:
            Gio.AppInfo.launch_default_for_uri(self._info.html_url, None)
        except Exception:
            pass

    def _on_git_update(self, *_args: object) -> None:
        self._update_btn.set_sensitive(False)
        self._status_label.set_text("Pulling latest git changes...")

        def _work() -> str:
            return self._services.update_svc.perform_git_update()

        def _done(out: str) -> None:
            self._status_label.set_text(f"✓ {out}\nPlease restart WineBox to apply the update.")
            self._update_btn.set_label("Restart Required")
            self._parent.show_toast("Update pulled successfully. Please restart WineBox.")

        def _err(exc: Exception) -> None:
            self._update_btn.set_sensitive(True)
            self._status_label.set_text(f"Update failed: {exc}")
            self._parent.show_toast(f"Git update failed: {exc}")

        run_async(_work, _done, _err)

    def _on_download_package(self, *_args: object) -> None:
        if not self._info.matching_asset:
            return
        url = self._info.matching_asset.get("browser_download_url")
        name = self._info.matching_asset.get("name", "winebox-update")
        if not url:
            return

        self._update_btn.set_sensitive(False)
        self._status_label.set_text(f"Downloading {name} to ~/Downloads...")

        def _work() -> Path:
            return self._services.update_svc.download_package(
                asset_url=url,
                filename=name,
            )

        def _done(dest_file: Path) -> None:
            self._status_label.set_text(f"✓ Downloaded to {dest_file}")
            self._update_btn.set_label("Downloaded")
            self._parent.show_toast(f"Downloaded {dest_file.name}")
            try:
                Gio.AppInfo.launch_default_for_uri(f"file://{dest_file.resolve()}", None)
            except Exception:
                pass

        def _err(exc: Exception) -> None:
            self._update_btn.set_sensitive(True)
            self._status_label.set_text(f"Download failed: {exc}")
            self._parent.show_toast(f"Download error: {exc}")

        run_async(_work, _done, _err)
