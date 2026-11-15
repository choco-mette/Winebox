"""Unit tests for Prefix Snapshot & Backup / Restore (ADR-027)."""

import io
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from winebox.application.prefix_service import PrefixService
from winebox.common.exceptions import WineboxError
from winebox.domain.models import Prefix
from winebox.infrastructure.backup_adapter import BackupAdapter
from winebox.infrastructure.process_manager import prefix_lock
from winebox.infrastructure.sqlite_repository import SqliteRepository
from winebox.interface.cli import app


def _make_tar_gz(path: Path, entries: list) -> None:
    with tarfile.open(path, mode="w:gz") as tf:
        for name, kind, payload in entries:
            info = tarfile.TarInfo(name=name)
            if kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = payload
                tf.addfile(info)
            else:
                data = payload.encode("utf-8") if isinstance(payload, str) else payload
                info.size = len(data)
                info.mode = 0o644
                tf.addfile(info, io.BytesIO(data))


class TestPrefixBackupRestore(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.repo = SqliteRepository(
            data_root=self.tmp_path / "data",
            config_root=self.tmp_path / "config",
        )
        self.svc = PrefixService(repo=self.repo)

        self.pfx_dir = self.repo.get_prefix_dir("skyrim")
        (self.pfx_dir / "prefix" / "drive_c").mkdir(parents=True)
        (self.pfx_dir / "prefix" / "dosdevices").mkdir(parents=True)
        (self.pfx_dir / "prefix" / "user.reg").write_text("REGEDIT4\n")
        (self.pfx_dir / "home" / "Saves").mkdir(parents=True)
        (self.pfx_dir / "home" / "Saves" / "save1.ess").write_text("save-data")
        (self.pfx_dir / "prefix.lock").write_text("999999")
        self.repo.save_prefix(Prefix(id="skyrim", name="Skyrim Prefix"))

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_backup_and_restore_roundtrip_default_and_gz_fallback(self) -> None:
        archive_default = self.svc.backup_prefix("skyrim")
        self.assertTrue(archive_default.exists())

        with patch.object(BackupAdapter, "has_zstd", return_value=False):
            archive_gz = self.svc.backup_prefix("skyrim")
        self.assertTrue(archive_gz.name.endswith(".tar.gz"))

        # Verify prefix.lock excluded in gz archive
        with tarfile.open(archive_gz, "r:gz") as tf:
            names = tf.getnames()
        self.assertIn("manifest.json", names)
        self.assertIn("prefix/user.reg", names)
        self.assertIn("home/Saves/save1.ess", names)
        self.assertNotIn("prefix.lock", names)

        # Restore under new ID
        restored = self.svc.restore_prefix(archive_default, target_prefix_id="skyrim-modded")
        self.assertEqual(restored.id, "skyrim-modded")
        restored_dir = self.repo.get_prefix_dir("skyrim-modded")
        self.assertEqual((restored_dir / "home" / "Saves" / "save1.ess").read_text(), "save-data")
        self.assertFalse((restored_dir / "prefix.lock").exists())

    def test_backup_refuses_running_locked_prefix(self) -> None:
        with prefix_lock(self.pfx_dir):
            with self.assertRaises(WineboxError):
                self.svc.backup_prefix("skyrim")

    def test_restore_rejects_traversal_and_escaping_symlink(self) -> None:
        evil_rel = self.tmp_path / "evil_rel.tar.gz"
        _make_tar_gz(evil_rel, [("../evil.txt", "file", "bad")])
        with self.assertRaises(WineboxError):
            self.svc.restore_prefix(evil_rel, target_prefix_id="safe")

        evil_abs = self.tmp_path / "evil_abs.tar.gz"
        _make_tar_gz(evil_abs, [("/etc/evil.txt", "file", "bad")])
        with self.assertRaises(WineboxError):
            self.svc.restore_prefix(evil_abs, target_prefix_id="safe")

        evil_sym = self.tmp_path / "evil_sym.tar.gz"
        _make_tar_gz(evil_sym, [("prefix/dosdevices/escape", "symlink", "../../../../etc/passwd")])
        with self.assertRaises(WineboxError):
            self.svc.restore_prefix(evil_sym, target_prefix_id="safe")

    def test_restore_overwrite_requires_force_and_preserves_safe_symlinks(self) -> None:
        c_link = self.pfx_dir / "prefix" / "dosdevices" / "c:"
        c_link.symlink_to("../drive_c")
        archive = self.svc.backup_prefix("skyrim")

        # Without --force -> raises WineboxError
        with self.assertRaises(WineboxError):
            self.svc.restore_prefix(archive, force=False)

        # Modify savegame, then restore with --force -> reverts savegame & preserves c:
        (self.pfx_dir / "home" / "Saves" / "save1.ess").write_text("corrupted")
        self.svc.restore_prefix(archive, force=True)
        self.assertEqual((self.pfx_dir / "home" / "Saves" / "save1.ess").read_text(), "save-data")
        self.assertTrue(c_link.is_symlink())

    def test_restore_rejects_invalid_target_prefix_id(self) -> None:
        archive = self.svc.backup_prefix("skyrim")
        for bad_id in ("../evil", "   ", "bad/id"):
            with self.assertRaises(WineboxError):
                self.svc.restore_prefix(archive, target_prefix_id=bad_id)


class TestPrefixBackupCLI(unittest.TestCase):
    def setUp(self) -> None:
        self.cli = CliRunner()

    def test_cli_help_and_roundtrip(self) -> None:
        self.assertEqual(self.cli.invoke(app, ["prefix", "backup", "--help"]).exit_code, 0)
        self.assertEqual(self.cli.invoke(app, ["prefix", "restore", "--help"]).exit_code, 0)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = os.environ.copy()
            env["XDG_DATA_HOME"] = str(tmp_path / "data")
            env["XDG_CONFIG_HOME"] = str(tmp_path / "cfg")

            repo = SqliteRepository(
                data_root=tmp_path / "data" / "winebox",
                config_root=tmp_path / "cfg" / "winebox",
            )
            p_dir = repo.get_prefix_dir("demo")
            (p_dir / "prefix" / "dosdevices").mkdir(parents=True)
            (p_dir / "home").mkdir(parents=True)
            (p_dir / "home" / "note.txt").write_text("ok")
            repo.save_prefix(Prefix(id="demo", name="Demo"))

            out_file = tmp_path / "demo.tar.gz"
            res_b = self.cli.invoke(app, ["prefix", "backup", "demo", "--output", str(out_file)], env=env)
            self.assertEqual(res_b.exit_code, 0)
            self.assertTrue(out_file.exists())

            res_r = self.cli.invoke(app, ["prefix", "restore", str(out_file), "--id", "demo-copy"], env=env)
            self.assertEqual(res_r.exit_code, 0)
            self.assertTrue((repo.get_prefix_dir("demo-copy") / "home" / "note.txt").exists())


if __name__ == "__main__":
    unittest.main()
