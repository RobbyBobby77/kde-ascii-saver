#!/usr/bin/env python3
"""Unit tests for config validation, TTE backoff constants, and EDITOR argv."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import helpers


class LoadConfigTests(unittest.TestCase):
    def _write(self, directory: str, text: str) -> Path:
        path = Path(directory) / "config.json"
        path.write_text(text, encoding="utf-8")
        return path

    def test_valid_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                '{"font": "Monospace 20", "background": "#111111", '
                '"frame_rate": 30, "exclude_effects": ["matrix"], '
                '"enabled": false, "idle_delay": 180}',
            )
            config = helpers.load_config(path)
        self.assertEqual(config["font"], "Monospace 20")
        self.assertEqual(config["background"], "#111111")
        self.assertEqual(config["frame_rate"], 30)
        self.assertEqual(config["exclude_effects"], ["matrix"])
        self.assertFalse(config["enabled"])
        self.assertEqual(config["idle_delay"], 180)

    def test_missing_file_returns_defaults(self) -> None:
        path = Path("/tmp/does-not-exist-kde-ascii-saver.json")
        config = helpers.load_config(path)
        self.assertEqual(config["frame_rate"], helpers.DEFAULT_CONFIG["frame_rate"])
        self.assertEqual(config["exclude_effects"], helpers.DEFAULT_CONFIG["exclude_effects"])
        self.assertTrue(config["enabled"])
        self.assertEqual(config["idle_delay"], 120)

    def test_invalid_json_warns_and_returns_defaults(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, patch("sys.stderr", stderr):
            path = self._write(tmp, "{not json")
            config = helpers.load_config(path)
        self.assertEqual(config["frame_rate"], 60)
        self.assertIn("invalid JSON", stderr.getvalue())

    def test_non_object_json_warns(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, patch("sys.stderr", stderr):
            path = self._write(tmp, "[1, 2, 3]")
            config = helpers.load_config(path)
        self.assertEqual(config["font"], helpers.DEFAULT_CONFIG["font"])
        self.assertIn("JSON object", stderr.getvalue())

    def test_string_frame_rate_is_rejected(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, patch("sys.stderr", stderr):
            path = self._write(tmp, '{"frame_rate": "60"}')
            config = helpers.load_config(path)
        self.assertEqual(config["frame_rate"], 60)
        self.assertIn("frame_rate", stderr.getvalue())

    def test_bool_frame_rate_is_rejected(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, patch("sys.stderr", stderr):
            path = self._write(tmp, '{"frame_rate": true}')
            config = helpers.load_config(path)
        self.assertEqual(config["frame_rate"], 60)
        self.assertIn("frame_rate", stderr.getvalue())

    def test_zero_frame_rate_is_rejected(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, patch("sys.stderr", stderr):
            path = self._write(tmp, '{"frame_rate": 0}')
            config = helpers.load_config(path)
        self.assertEqual(config["frame_rate"], 60)

    def test_exclude_effects_flags_are_dropped(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, patch("sys.stderr", stderr):
            path = self._write(tmp, '{"exclude_effects": ["matrix", "--help", "-v", "beams"]}')
            config = helpers.load_config(path)
        self.assertEqual(config["exclude_effects"], ["matrix", "beams"])
        self.assertIn("starts with '-'", stderr.getvalue())

    def test_exclude_effects_must_be_a_list(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, patch("sys.stderr", stderr):
            path = self._write(tmp, '{"exclude_effects": "matrix"}')
            config = helpers.load_config(path)
        self.assertEqual(config["exclude_effects"], ["bouncyballs", "overflow"])
        self.assertIn("exclude_effects", stderr.getvalue())

    def test_invalid_color_keeps_default(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, patch("sys.stderr", stderr):
            path = self._write(tmp, '{"background": "--red", "font": 12}')
            config = helpers.load_config(path)
        self.assertEqual(config["background"], "#000000")
        self.assertEqual(config["font"], "Monospace 18")
        self.assertIn("background", stderr.getvalue())
        self.assertIn("font", stderr.getvalue())

    def test_named_color_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, '{"background": "black"}')
            config = helpers.load_config(path)
        self.assertEqual(config["background"], "black")

    def test_invalid_enabled_and_idle_delay_keep_defaults(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, patch("sys.stderr", stderr):
            path = self._write(tmp, '{"enabled": 1, "idle_delay": true}')
            config = helpers.load_config(path)
        self.assertTrue(config["enabled"])
        self.assertEqual(config["idle_delay"], 120)
        self.assertIn("enabled", stderr.getvalue())
        self.assertIn("idle_delay", stderr.getvalue())

    def test_idle_delay_bounds(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, patch("sys.stderr", stderr):
            path = self._write(tmp, '{"idle_delay": 9}')
            config = helpers.load_config(path)
            self.assertEqual(config["idle_delay"], 120)
            path.write_text('{"idle_delay": 10}', encoding="utf-8")
            self.assertEqual(helpers.load_config(path)["idle_delay"], 10)
            path.write_text('{"idle_delay": 86400}', encoding="utf-8")
            self.assertEqual(helpers.load_config(path)["idle_delay"], 86400)
            path.write_text('{"idle_delay": 86401}', encoding="utf-8")
            self.assertEqual(helpers.load_config(path)["idle_delay"], 120)

    def test_defaults_are_not_mutated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, '{"exclude_effects": ["matrix"]}')
            helpers.load_config(path)
        self.assertEqual(helpers.DEFAULT_CONFIG["exclude_effects"], ["bouncyballs", "overflow"])


class EditorArgvTests(unittest.TestCase):
    def test_single_token_uses_which(self) -> None:
        with patch("helpers.shutil.which", return_value="/usr/bin/vim"):
            self.assertEqual(helpers.editor_argv("vim"), ["/usr/bin/vim"])

    def test_single_token_without_which_is_kept(self) -> None:
        with patch("helpers.shutil.which", return_value=None):
            self.assertEqual(helpers.editor_argv("vim"), ["vim"])

    def test_command_with_spaces_uses_shlex(self) -> None:
        self.assertEqual(
            helpers.editor_argv('"/home/user/my editor" --wait'),
            ["/home/user/my editor", "--wait"],
        )

    def test_blank_editor_is_empty(self) -> None:
        self.assertEqual(helpers.editor_argv("   "), [])


class VersionTests(unittest.TestCase):
    def test_reads_version_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "VERSION").write_text("0.1.0\n", encoding="utf-8")
            self.assertEqual(helpers.read_version(Path(tmp)), "0.1.0")

    def test_missing_version_file_uses_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(helpers.read_version(Path(tmp)), helpers.FALLBACK_VERSION)


if __name__ == "__main__":
    unittest.main()
