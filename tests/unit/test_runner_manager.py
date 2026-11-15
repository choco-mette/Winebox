"""Unit tests for RunnerAdapter, RunnerService, and runner CLI commands (ADR-026)."""

import io
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from winebox.application.runner_service import RunnerService
from winebox.common.exceptions import WineboxError
from winebox.domain.models import Prefix
from winebox.infrastructure.runner_adapter import RunnerAdapter
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.interface.cli import app


def _make_tar_bytes(entries: list) -> bytes:
    """Builds an in-memory .tar.gz archive from (name, type, payload_or_link) tuples."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, kind, payload in entries:
            info = tarfile.TarInfo(name=name)
            if kind == "dir":
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                tf.addfile(info)
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = payload
                tf.addfile(info)
            else:
                data = payload.encode("utf-8") if isinstance(payload, str) else payload
                info.size = len(data)
                info.mode = 0o755
                tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class TestRunnerAdapter(unittest.TestCase):
    def test_safe_extract_tar_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            archive = tmp_path / "valid.tar.gz"
            archive.write_bytes(
                _make_tar_bytes(
                    [
                        ("wine-9.21/bin/wine", "file", "#!/bin/sh\n"),
                        ("wine-9.21/bin/wineserver", "file", "#!/bin/sh\n"),
                    ]
                )
            )
            dest = tmp_path / "out"
            RunnerAdapter.safe_extract_tar(archive, dest)
            self.assertTrue((dest / "wine-9.21" / "bin" / "wine").exists())
            self.assertTrue((dest / "wine-9.21" / "bin" / "wineserver").exists())

    def test_safe_extract_tar_rejects_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            archive = tmp_path / "evil_rel.tar.gz"
            archive.write_bytes(_make_tar_bytes([("../evil.txt", "file", "pwned")]))
            with self.assertRaises(WineboxError):
                RunnerAdapter.safe_extract_tar(archive, tmp_path / "out")

    def test_safe_extract_tar_rejects_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            archive = tmp_path / "evil_abs.tar.gz"
            archive.write_bytes(_make_tar_bytes([("/etc/evil.txt", "file", "pwned")]))
            with self.assertRaises(WineboxError):
                RunnerAdapter.safe_extract_tar(archive, tmp_path / "out")

    def test_safe_extract_tar_rejects_escaping_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            archive = tmp_path / "evil_sym.tar.gz"
            archive.write_bytes(_make_tar_bytes([("sub/escape", "symlink", "../../../etc/passwd")]))
            with self.assertRaises(WineboxError):
                RunnerAdapter.safe_extract_tar(archive, tmp_path / "out")

    def test_detect_wine_binaries_standard_and_proton(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            std_root = tmp_path / "std"
            (std_root / "bin").mkdir(parents=True)
            (std_root / "bin" / "wine").write_text("")
            (std_root / "bin" / "wineserver").write_text("")
            wine_bin, ws_bin = RunnerAdapter.detect_wine_binaries(std_root)
            self.assertEqual(wine_bin, (std_root / "bin" / "wine").resolve())
            self.assertEqual(ws_bin, (std_root / "bin" / "wineserver").resolve())

            proton_root = tmp_path / "proton"
            (proton_root / "GE-Proton9-20" / "files" / "bin").mkdir(parents=True)
            (proton_root / "GE-Proton9-20" / "files" / "bin" / "wine").write_text("")
            wine_bin_p, ws_bin_p = RunnerAdapter.detect_wine_binaries(proton_root)
            self.assertEqual(wine_bin_p, (proton_root / "GE-Proton9-20" / "files" / "bin" / "wine").resolve())
            self.assertIsNone(ws_bin_p)

            empty_root = tmp_path / "empty"
            empty_root.mkdir()
            with self.assertRaises(WineboxError):
                RunnerAdapter.detect_wine_binaries(empty_root)


class TestRunnerService(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.repo = SqliteRepository(
            data_root=self.tmp_path / "data",
            config_root=self.tmp_path / "config",
        )
        self.xdg_data = self.tmp_path / "xdg_data"
        self.svc = RunnerService(repo=self.repo)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_install_runner_and_share_symlink(self) -> None:
        archive_path = self.tmp_path / "GE-Proton9-20.tar.gz"
        archive_path.write_bytes(
            _make_tar_bytes(
                [
                    ("GE-Proton9-20/files/bin/wine", "file", "#!/bin/sh\n"),
                    ("GE-Proton9-20/files/bin/wineserver", "file", "#!/bin/sh\n"),
                ]
            )
        )
        fake_release = [
            {
                "source": "ge-proton",
                "kind": "proton",
                "version": "GE-Proton9-20",
                "filename": "GE-Proton9-20.tar.gz",
                "url": "https://example.invalid/GE-Proton9-20.tar.gz",
            }
        ]

        with patch.object(RunnerAdapter, "fetch_releases", return_value=fake_release), patch.object(
            RunnerAdapter, "download_tarball", return_value=archive_path
        ):
            runner, shared_link = self.svc.install_runner(
                "ge-proton", version="GE-Proton9-20", share=True, xdg_data_home=self.xdg_data
            )

        self.assertEqual(runner.id, "ge-proton9-20")
        self.assertTrue(runner.wine_bin.exists())
        self.assertIsNotNone(shared_link)
        assert shared_link is not None
        self.assertTrue(shared_link.is_symlink())
        self.assertEqual(shared_link.parent, self.xdg_data / "Steam" / "compatibilitytools.d")

    def test_scan_external_runners(self) -> None:
        lutris_wine = self.xdg_data / "lutris" / "runners" / "wine" / "wine-ge-8-26" / "bin"
        lutris_wine.mkdir(parents=True)
        (lutris_wine / "wine").write_text("")

        steam_proton = self.xdg_data / "Steam" / "compatibilitytools.d" / "GE-Proton9-11" / "files" / "bin"
        steam_proton.mkdir(parents=True)
        (steam_proton / "wine").write_text("")

        official_proton = self.xdg_data / "Steam" / "steamapps" / "common" / "Proton - Experimental" / "files" / "bin"
        official_proton.mkdir(parents=True)
        (official_proton / "wine").write_text("")

        added = self.svc.scan_external_runners(xdg_data_home=self.xdg_data)
        self.assertEqual({r.id for r in added}, {"wine-ge-8-26", "ge-proton9-11", "proton-experimental"})

        added_again = self.svc.scan_external_runners(xdg_data_home=self.xdg_data)
        self.assertEqual(added_again, [])

    def test_remove_runner_in_use_and_cleanup(self) -> None:
        runner_dir = self.repo.runners_dir / "custom-wine"
        (runner_dir / "bin").mkdir(parents=True)
        wine_bin = runner_dir / "bin" / "wine"
        wine_bin.write_text("")

        self.svc.register_custom_runner("custom-wine", "Custom Wine", wine_bin)
        link = self.svc.share_runner("custom-wine", xdg_data_home=self.xdg_data)
        self.assertTrue(link.is_symlink())

        self.repo.save_prefix(Prefix(id="pfx-1", name="Pfx", runner_id="custom-wine"))
        with self.assertRaises(WineboxError):
            self.svc.remove_runner("custom-wine", xdg_data_home=self.xdg_data)

        self.repo.save_prefix(Prefix(id="pfx-1", name="Pfx", runner_id="system-wine"))
        self.svc.remove_runner("custom-wine", xdg_data_home=self.xdg_data)

        self.assertFalse(runner_dir.exists())
        self.assertFalse(link.is_symlink())

    def test_remove_external_runner_does_not_delete_external_files(self) -> None:
        ext_dir = self.tmp_path / "external-lutris" / "wine-ext"
        (ext_dir / "bin").mkdir(parents=True)
        wine_bin = ext_dir / "bin" / "wine"
        wine_bin.write_text("")

        self.svc.register_custom_runner("wine-ext", "External Wine", wine_bin)
        self.svc.remove_runner("wine-ext", delete_files=True, xdg_data_home=self.xdg_data)
        self.assertTrue(ext_dir.exists())

    def test_download_rejects_non_https_and_share_dist_layout(self) -> None:
        with self.assertRaises(WineboxError):
            RunnerAdapter.download_tarball("http://example.invalid/wine.tar.xz", self.tmp_path, "wine.tar.xz")
        with self.assertRaises(WineboxError):
            RunnerAdapter.download_tarball("file:///etc/passwd", self.tmp_path, "passwd")

        dist_dir = self.repo.runners_dir / "old-proton" / "dist" / "bin"
        dist_dir.mkdir(parents=True)
        wine_bin = dist_dir / "wine"
        wine_bin.write_text("")
        self.svc.register_custom_runner("old-proton", "Old Proton", wine_bin)
        link = self.svc.share_runner("old-proton", xdg_data_home=self.xdg_data)
        self.assertEqual(link.parent, self.xdg_data / "Steam" / "compatibilitytools.d")

    def test_pick_asset_skips_aarch64_on_x86_64(self) -> None:
        assets = [
            {"name": "GE-Proton11-9-aarch64.tar.gz", "browser_download_url": "https://example.invalid/arm.tar.gz"},
            {"name": "GE-Proton11-9.tar.gz", "browser_download_url": "https://example.invalid/x86.tar.gz"},
            {"name": "GE-Proton11-9.sha512sum", "browser_download_url": "https://example.invalid/sha"},
        ]
        with patch("winebox.infrastructure.runner_adapter.platform.machine", return_value="x86_64"):
            picked = RunnerAdapter._pick_asset(assets, "ge-proton", ".tar.gz")
            self.assertIsNotNone(picked)
            assert picked is not None
            self.assertEqual(picked["name"], "GE-Proton11-9.tar.gz")

        with patch("winebox.infrastructure.runner_adapter.platform.machine", return_value="aarch64"):
            picked_arm = RunnerAdapter._pick_asset(assets, "ge-proton", ".tar.gz")
            self.assertIsNotNone(picked_arm)
            assert picked_arm is not None
            self.assertEqual(picked_arm["name"], "GE-Proton11-9-aarch64.tar.gz")

    def test_install_runner_emits_stage_and_extract_callbacks(self) -> None:
        archive_path = self.tmp_path / "GE-Proton9-20.tar.gz"
        archive_path.write_bytes(
            _make_tar_bytes(
                [
                    ("GE-Proton9-20/files/bin/wine", "file", "#!/bin/sh\n"),
                    ("GE-Proton9-20/files/bin/wineserver", "file", "#!/bin/sh\n"),
                ]
            )
        )
        fake_release = [
            {
                "source": "ge-proton",
                "kind": "proton",
                "version": "GE-Proton9-20",
                "filename": "GE-Proton9-20.tar.gz",
                "url": "https://example.invalid/GE-Proton9-20.tar.gz",
            }
        ]
        stages: list = []
        extract_ticks: list = []
        with patch.object(RunnerAdapter, "fetch_releases", return_value=fake_release), patch.object(
            RunnerAdapter, "download_tarball", return_value=archive_path
        ):
            self.svc.install_runner(
                "ge-proton",
                version="GE-Proton9-20",
                on_stage=stages.append,
                on_extract_progress=lambda d, t: extract_ticks.append((d, t)),
            )
        self.assertGreaterEqual(len(stages), 3)
        self.assertEqual(extract_ticks[-1], (2, 2))


class TestRunnerCLI(unittest.TestCase):
    def setUp(self) -> None:
        self.cli = CliRunner()

    def test_help_commands(self) -> None:
        res_avail = self.cli.invoke(app, ["runner", "available", "--help"])
        self.assertEqual(res_avail.exit_code, 0)
        res_inst = self.cli.invoke(app, ["runner", "install", "--help"])
        self.assertEqual(res_inst.exit_code, 0)
        self.assertIn("--share", res_inst.output)

    def test_cli_scan_and_remove(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_home = tmp_path / "xdg_data"
            config_home = tmp_path / "xdg_config"
            ext_bin = data_home / "lutris" / "runners" / "wine" / "lutris-wine-9" / "bin"
            ext_bin.mkdir(parents=True)
            (ext_bin / "wine").write_text("")

            env = os.environ.copy()
            env["XDG_DATA_HOME"] = str(data_home)
            env["XDG_CONFIG_HOME"] = str(config_home)

            res_scan = self.cli.invoke(app, ["runner", "scan"], env=env)
            self.assertEqual(res_scan.exit_code, 0)
            self.assertIn("lutris-wine-9", res_scan.output)

            res_rm = self.cli.invoke(app, ["runner", "remove", "lutris-wine-9"], env=env)
            self.assertEqual(res_rm.exit_code, 0)
            self.assertIn("removed", res_rm.output)
            self.assertTrue(ext_bin.exists())

    def test_cli_interactive_install_passes_valid_source_and_version(self) -> None:
        fake_release = [
            {
                "source": "wine-builds",
                "kind": "wine",
                "version": "9.21",
                "filename": "wine-9.21-staging-tkg-amd64.tar.xz",
                "url": "https://example.invalid/wine.tar.xz",
            }
        ]
        with patch.object(RunnerService, "fetch_available_releases", return_value=fake_release) as mock_fetch, patch.object(
            RunnerService, "install_runner"
        ) as mock_install:
            mock_install.return_value = (
                unittest.mock.MagicMock(id="wine-builds-9-21", wine_bin=Path("/tmp/bin/wine")),
                None,
            )
            res = self.cli.invoke(app, ["runner", "install"], input="1\n1\nn\n")
            self.assertEqual(res.exit_code, 0)
            mock_fetch.assert_called_once_with("wine-builds", limit=30)
            self.assertEqual(mock_install.call_args.args, ("wine-builds",))
            self.assertEqual(mock_install.call_args.kwargs["version"], "9.21")
            self.assertFalse(mock_install.call_args.kwargs["share"])


if __name__ == "__main__":
    unittest.main()
