"""Unit tests for in-app update service, version parsing, and asset matching (ADR-020)."""

import json
import tempfile
import unittest
from pathlib import Path

from winebox.application.update_service import (
    UpdateInfo,
    UpdateService,
    is_newer_version,
    parse_semver,
)


class TestUpdateService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.svc = UpdateService(data_root=self.root / "data", project_root=self.root / "proj")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_semver_and_is_newer_version(self):
        self.assertEqual(parse_semver("0.1.0"), (0, 1, 0))
        self.assertEqual(parse_semver("v0.1.1"), (0, 1, 1))
        self.assertEqual(parse_semver("1.2.3.4"), (1, 2, 3, 4))

        self.assertTrue(is_newer_version("0.1.0", "0.1.1"))
        self.assertTrue(is_newer_version("0.1.1", "0.2.0"))
        self.assertTrue(is_newer_version("0.1.1", "1.0.0"))
        self.assertTrue(is_newer_version("0.1.1", "0.1.1.1"))

        self.assertFalse(is_newer_version("0.1.1", "0.1.1"))
        self.assertFalse(is_newer_version("0.1.1", "0.1.0"))
        self.assertFalse(is_newer_version("1.0.0", "0.9.9"))

    def test_find_matching_asset_by_distro(self):
        sample_assets = [
            {"name": "winebox-0.1.1-1-any.pkg.tar.zst", "browser_download_url": "http://pkg.tar.zst"},
            {"name": "winebox-0.1.1-1.fc45.noarch.rpm", "browser_download_url": "http://rpm"},
            {"name": "winebox_0.1.1_all.deb", "browser_download_url": "http://deb"},
            {"name": "winebox-0.1.1-linux-noarch.tar.gz", "browser_download_url": "http://tar.gz"},
        ]

        deb_asset = self.svc.find_matching_asset(sample_assets, "debian")
        self.assertIsNotNone(deb_asset)
        self.assertTrue(deb_asset["name"].endswith(".deb"))

        rpm_asset = self.svc.find_matching_asset(sample_assets, "fedora")
        self.assertIsNotNone(rpm_asset)
        self.assertTrue(rpm_asset["name"].endswith(".rpm"))

        arch_asset = self.svc.find_matching_asset(sample_assets, "arch")
        self.assertIsNotNone(arch_asset)
        self.assertTrue(arch_asset["name"].endswith(".pkg.tar.zst"))

        fallback_asset = self.svc.find_matching_asset(sample_assets, "unknown_distro")
        self.assertIsNotNone(fallback_asset)
        self.assertTrue(fallback_asset["name"].endswith(".tar.gz"))

    def test_cache_file_generation_and_reading(self):
        import time

        cache_data = {
            "etag": '"abc-123"',
            "last_checked": time.time(),
            "release": {
                "tag_name": "v0.9.9",
                "name": "Release 0.9.9",
                "body": "Sample notes",
                "html_url": "https://github.com/example",
                "assets": [],
            },
        }
        self.svc.cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

        info = self.svc.check_update(force=False)
        self.assertIsNotNone(info)
        self.assertEqual(info.latest_version, "0.9.9")
        self.assertTrue(info.has_update)
        self.assertEqual(info.release_notes, "Sample notes")


if __name__ == "__main__":
    unittest.main()
