#!/usr/bin/env python3
"""Unit tests for config validation, TTE backoff constants, and EDITOR argv."""

from __future__ import annotations

import io
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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

    def test_named_color_is_rejected_because_tte_requires_rgb(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, patch("sys.stderr", stderr):
            path = self._write(tmp, '{"background": "black"}')
            config = helpers.load_config(path)
        self.assertEqual(config["background"], "#000000")
        self.assertIn("background", stderr.getvalue())

    def test_only_six_digit_hash_rgb_colors_are_accepted(self) -> None:
        invalid_colors = ("#000", "#000f", "#000000ff", "000000", "not-a-color")
        with tempfile.TemporaryDirectory() as tmp, patch("sys.stderr", io.StringIO()):
            path = self._write(tmp, "{}")
            for color in invalid_colors:
                path.write_text(json.dumps({"background": color}), encoding="utf-8")
                self.assertEqual(helpers.load_config(path)["background"], "#000000")
            path.write_text('{"background": " #Ab12Ef "}', encoding="utf-8")
            self.assertEqual(helpers.load_config(path)["background"], "#Ab12Ef")

    def test_frame_rate_has_a_safe_upper_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch("sys.stderr", io.StringIO()):
            path = self._write(tmp, '{"frame_rate": 240}')
            self.assertEqual(helpers.load_config(path)["frame_rate"], 240)
            path.write_text('{"frame_rate": 241}', encoding="utf-8")
            self.assertEqual(helpers.load_config(path)["frame_rate"], 60)

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


class RuntimeDirTests(unittest.TestCase):
    def test_prefers_xdg_runtime_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(helpers.runtime_dir({"XDG_RUNTIME_DIR": tmp}), Path(tmp))

    def test_refuses_when_unset(self) -> None:
        self.assertIsNone(helpers.runtime_dir({}))
        with self.assertRaises(RuntimeError):
            helpers.pid_file_path({})


class PidFileTests(unittest.TestCase):
    def test_exclusive_create(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "saver.pid"
            helpers.write_pid_file(path, 4242)
            self.assertEqual(path.read_text(encoding="ascii").strip(), "4242")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with patch("helpers.pid_file_is_stale", return_value=False):
                with self.assertRaises(RuntimeError):
                    helpers.write_pid_file(path, 4343)
            self.assertEqual(path.read_text(encoding="ascii").strip(), "4242")

    def test_replaces_stale_pid_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "saver.pid"
            path.write_text("1\n", encoding="ascii")
            helpers.write_pid_file(path, 99)
            self.assertEqual(path.read_text(encoding="ascii").strip(), "99")


class ProcessIdentityTests(unittest.TestCase):
    def test_renderer_matches_exact_script_argument(self) -> None:
        expected = Path("/opt/kde-ascii-saver/app.py")
        cmdline = b"/opt/venv/bin/python\0/opt/kde-ascii-saver/app.py\0--once\0"
        with patch.object(Path, "read_bytes", return_value=cmdline):
            self.assertTrue(helpers.process_matches_saver(42, expected))

    def test_renderer_rejects_project_substrings_and_other_app_py(self) -> None:
        expected = Path("/opt/kde-ascii-saver/app.py")
        cmdlines = (
            b"/usr/bin/kde-ascii-saverctl\0status\0",
            b"/usr/bin/python3\0/tmp/app.py\0kde-ascii-saver\0",
            b"/usr/bin/bash\0-c\0kde-ascii-saver app.py\0",
        )
        for cmdline in cmdlines:
            with self.subTest(cmdline=cmdline), patch.object(
                Path, "read_bytes", return_value=cmdline
            ):
                self.assertFalse(helpers.process_matches_saver(42, expected))

    def test_renderer_identity_resolves_symlinked_install_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            real_dir = Path(tmp) / "real"
            real_dir.mkdir()
            (real_dir / "app.py").touch()
            linked_dir = Path(tmp) / "linked"
            linked_dir.symlink_to(real_dir, target_is_directory=True)
            cmdline = os.fsencode(f"/usr/bin/python3\0{linked_dir / 'app.py'}\0")
            with patch.object(Path, "read_bytes", return_value=cmdline):
                self.assertTrue(helpers.process_matches_saver(42, real_dir / "app.py"))

    def test_watcher_matches_exact_executable(self) -> None:
        expected = Path("/opt/kde-ascii-saver/kde-ascii-saver-watcher")
        with patch("helpers.os.readlink", return_value=str(expected)):
            self.assertTrue(helpers.process_matches_watcher(42, expected))
        with patch("helpers.os.readlink", return_value="/tmp/kde-ascii-saver-watcher-helper"):
            self.assertFalse(helpers.process_matches_watcher(42, expected))

    def test_invalid_pid_never_reads_proc(self) -> None:
        with patch.object(Path, "read_bytes") as read_bytes, patch(
            "helpers.os.readlink"
        ) as readlink:
            self.assertFalse(helpers.process_matches_saver(0))
            self.assertFalse(helpers.process_matches_watcher(-1))
        read_bytes.assert_not_called()
        readlink.assert_not_called()


class ProcessSignalTests(unittest.TestCase):
    def test_pidfd_signal_is_sent_after_identity_recheck(self) -> None:
        matches = Mock(return_value=True)
        with patch("helpers.os.pidfd_open", return_value=8) as pidfd_open, patch(
            "helpers.signal.pidfd_send_signal"
        ) as send, patch("helpers.os.close") as close:
            self.assertTrue(helpers.send_signal_if_matches(42, 15, matches))
        pidfd_open.assert_called_once_with(42)
        matches.assert_called_once_with(42)
        send.assert_called_once_with(8, 15)
        close.assert_called_once_with(8)

    def test_pidfd_is_not_signaled_after_identity_changes(self) -> None:
        with patch("helpers.os.pidfd_open", return_value=8), patch(
            "helpers.signal.pidfd_send_signal"
        ) as send, patch("helpers.os.close") as close:
            self.assertFalse(helpers.send_signal_if_matches(42, 15, lambda _pid: False))
        send.assert_not_called()
        close.assert_called_once_with(8)

    def test_missing_process_is_friendly(self) -> None:
        with patch("helpers.os.pidfd_open", side_effect=ProcessLookupError):
            self.assertFalse(helpers.send_signal_if_matches(42, 15, lambda _pid: True))

    def test_fallback_rechecks_before_kill(self) -> None:
        with patch.object(helpers.os, "pidfd_open", None), patch.object(
            helpers.signal, "pidfd_send_signal", None
        ), patch("helpers.os.kill") as kill:
            self.assertFalse(helpers.send_signal_if_matches(42, 15, lambda _pid: False))
        kill.assert_not_called()


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
