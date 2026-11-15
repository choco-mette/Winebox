"""Runners management page for installed runners, Steam/Lutris scan, and Hub install."""

from typing import Dict, List, Optional
from gi.repository import Adw, GLib, Gtk
from winebox.interface.gui.state import run_async


class RunnersPage(Gtk.Box):
    """Manages Wine/Proton runners, ecosystem sharing, and GitHub Hub installations."""

    def __init__(self, window: Adw.ApplicationWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._window = window
        self._releases: List[Dict[str, str]] = []
        self.set_margin_top(16)
        self.set_margin_bottom(16)
        self.set_margin_start(16)
        self.set_margin_end(16)

        # Hub installer bar
        hub_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._source_keys = list(self._window.services.runner_svc.list_sources().keys())
        self._source_dropdown = Gtk.DropDown.new_from_strings(self._source_keys)
        self._source_dropdown.connect("notify::selected", lambda *_: self._fetch_releases())
        hub_box.append(self._source_dropdown)

        self._version_dropdown = Gtk.DropDown.new_from_strings(["(Click Fetch)"])
        self._version_dropdown.set_hexpand(True)
        hub_box.append(self._version_dropdown)

        self._share_check = Gtk.CheckButton(label="Share to Lutris/Steam")
        hub_box.append(self._share_check)

        self._install_btn = Gtk.Button(label="Install")
        self._install_btn.add_css_class("suggested-action")
        self._install_btn.connect("clicked", self._on_install)
        hub_box.append(self._install_btn)

        scan_btn = Gtk.Button(label="Scan Steam/Lutris")
        scan_btn.connect("clicked", self._on_scan)
        hub_box.append(scan_btn)
        self.append(hub_box)

        self._progress = Gtk.ProgressBar(show_text=True, visible=False)
        self.append(self._progress)

        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self._list_box = Gtk.ListBox()
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.set_child(self._list_box)
        self.append(scrolled)

        self._fetch_releases()

    def refresh(self) -> None:
        while child := self._list_box.get_first_child():
            self._list_box.remove(child)

        runners = self._window.services.runner_svc.list_runners()
        for r in runners:
            r_type = "System" if r.is_system else "Custom"
            row = Adw.ActionRow(title=f"{r.id} ({r.name})", subtitle=f"{r_type}  •  {r.wine_bin}")
            if not r.is_system:
                share_btn = Gtk.Button(label="Share")
                share_btn.set_valign(Gtk.Align.CENTER)
                share_btn.connect("clicked", lambda _b, rid=r.id: self._share_runner(rid))
                row.add_suffix(share_btn)

                rm_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
                rm_btn.add_css_class("flat")
                rm_btn.set_valign(Gtk.Align.CENTER)
                rm_btn.set_tooltip_text("Remove runner")
                rm_btn.connect("clicked", lambda _b, rid=r.id: self._confirm_remove_runner(rid))
                row.add_suffix(rm_btn)
            self._list_box.append(row)

    def _fetch_releases(self) -> None:
        idx = self._source_dropdown.get_selected()
        if idx == Gtk.INVALID_LIST_POSITION or idx >= len(self._source_keys):
            return
        source_key = self._source_keys[idx]
        self._version_dropdown.set_model(Gtk.StringList.new(["Fetching..."]))

        def _done(releases: List[Dict[str, str]]) -> None:
            self._releases = releases
            self._version_dropdown.set_model(
                Gtk.StringList.new([r["version"] for r in releases] or ["(none found)"])
            )

        run_async(
            lambda: self._window.services.runner_svc.fetch_available_releases(source_key, limit=30),
            on_success=_done,
            on_error=lambda e: self._window.show_toast(f"Fetch error: {e}"),
        )

    def _on_install(self, *_args: object) -> None:
        s_idx = self._source_dropdown.get_selected()
        v_idx = self._version_dropdown.get_selected()
        if s_idx >= len(self._source_keys) or v_idx >= len(self._releases):
            return
        source_key = self._source_keys[s_idx]
        version = self._releases[v_idx]["version"]
        share = self._share_check.get_active()

        self._install_btn.set_sensitive(False)
        self._progress.set_visible(True)
        self._progress.set_fraction(0.0)
        self._progress.set_text(f"Downloading {version}...")

        def _on_dl(downloaded: int, total: Optional[int]) -> None:
            if total and total > 0:
                frac = min(downloaded / total, 1.0)
                mb_done = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                GLib.idle_add(
                    lambda: (
                        self._progress.set_fraction(frac),
                        self._progress.set_text(f"Downloading {mb_done:.1f} / {mb_total:.1f} MB"),
                        False,
                    )[2]
                )

        def _on_ext(done: int, total: int) -> None:
            if total > 0:
                GLib.idle_add(
                    lambda: (
                        self._progress.set_fraction(done / total),
                        self._progress.set_text(f"Extracting {done}/{total} files"),
                        False,
                    )[2]
                )

        def _finish(res: object) -> None:
            runner, _ = res  # type: ignore[misc]
            self._install_btn.set_sensitive(True)
            self._progress.set_visible(False)
            self._window.show_toast(f"Installed '{runner.id}'")
            self.refresh()

        def _err(e: Exception) -> None:
            self._install_btn.set_sensitive(True)
            self._progress.set_visible(False)
            self._window.show_toast(f"Install failed: {e}")

        run_async(
            lambda: self._window.services.runner_svc.install_runner(
                source_key,
                version=version,
                share=share,
                on_download_progress=_on_dl,
                on_extract_progress=_on_ext,
            ),
            on_success=_finish,
            on_error=_err,
        )

    def _on_scan(self, *_args: object) -> None:
        added = self._window.services.runner_svc.scan_external_runners()
        self._window.show_toast(
            f"Found {len(added)} new external runner(s)" if added else "No new external runners found"
        )
        self.refresh()

    def _share_runner(self, runner_id: str) -> None:
        try:
            link = self._window.services.runner_svc.share_runner(runner_id)
            self._window.show_toast(f"Shared at {link}")
        except Exception as e:
            self._window.show_toast(f"Share failed: {e}")

    def _confirm_remove_runner(self, runner_id: str) -> None:
        dlg = Adw.AlertDialog.new(
            f"Remove runner '{runner_id}'?",
            "Deletes the installed runner from WineBox. Apps using it will need another runner.",
        )
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("remove", "Remove")
        dlg.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.connect("response", lambda _d, resp: self._remove_runner(runner_id) if resp == "remove" else None)
        dlg.present(self._window)

    def _remove_runner(self, runner_id: str) -> None:
        try:
            self._window.services.runner_svc.remove_runner(runner_id)
            self._window.show_toast(f"Removed '{runner_id}'")
            self.refresh()
        except Exception as e:
            self._window.show_toast(f"Remove failed: {e}")
