#!/usr/bin/env python3
"""Config merge tests for kde-ascii-saverctl."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ctl


class UpdateConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.tmpdir.name)
        self.config_file = self.config_dir / "config.json"
        self.patches = [
            mock.patch.object(ctl, "config_dir", self.config_dir),
            mock.patch.object(ctl, "config_file", self.config_file),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in self.patches:
            patcher.stop()
        self.tmpdir.cleanup()

    def test_update_merges_into_existing_keys(self) -> None:
        original = {
            "enabled": True,
            "idle_delay": 120,
            "font": "Monospace 18",
            "background": "#112233",
            "frame_rate": 60,
            "exclude_effects": ["overflow"],
        }
        self.config_file.write_text(json.dumps(original) + "\n", encoding="utf-8")
        ctl.update_config("enabled", False)
        data = json.loads(self.config_file.read_text(encoding="utf-8"))
        self.assertFalse(data["enabled"])
        self.assertEqual(data["font"], "Monospace 18")
        self.assertEqual(data["background"], "#112233")
        self.assertEqual(data["exclude_effects"], ["overflow"])
        self.assertEqual(data["idle_delay"], 120)

    def test_update_fills_defaults_when_file_is_missing(self) -> None:
        ctl.update_config("idle_delay", 180)
        data = json.loads(self.config_file.read_text(encoding="utf-8"))
        self.assertEqual(data["idle_delay"], 180)
        self.assertEqual(data["font"], ctl.DEFAULT_CONFIG["font"])
        self.assertTrue(data["enabled"])
        self.assertEqual(data["exclude_effects"], ctl.DEFAULT_CONFIG["exclude_effects"])

    def test_refuses_unreadable_json(self) -> None:
        self.config_file.write_text("{not json", encoding="utf-8")
        with self.assertRaises(SystemExit) as raised:
            ctl.update_config("enabled", False)
        self.assertIn("refusing to overwrite", str(raised.exception))
        self.assertEqual(self.config_file.read_text(encoding="utf-8"), "{not json")

    def test_refuses_non_object_json(self) -> None:
        self.config_file.write_text("[1, 2, 3]\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as raised:
            ctl.update_config("idle_delay", 90)
        self.assertIn("not a JSON object", str(raised.exception))
        self.assertEqual(self.config_file.read_text(encoding="utf-8"), "[1, 2, 3]\n")

    def test_load_config_does_not_write_on_parse_failure(self) -> None:
        self.config_file.write_text("{bad", encoding="utf-8")
        loaded = ctl.load_config()
        self.assertEqual(loaded["font"], ctl.DEFAULT_CONFIG["font"])
        self.assertEqual(self.config_file.read_text(encoding="utf-8"), "{bad")


if __name__ == "__main__":
    unittest.main()
