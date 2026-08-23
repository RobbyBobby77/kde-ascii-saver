#!/usr/bin/env python3
"""Config merge tests for kde-ascii-saverctl."""

from __future__ import annotations

import io
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
        with mock.patch("sys.stderr", io.StringIO()):
            loaded = ctl.load_config()
        self.assertEqual(loaded["font"], ctl.DEFAULT_CONFIG["font"])
        self.assertEqual(self.config_file.read_text(encoding="utf-8"), "{bad")

    def test_load_config_rejects_invalid_visual_keys(self) -> None:
        self.config_file.write_text(
            '{"frame_rate": "60", "background": "--red", "exclude_effects": "--help"}',
            encoding="utf-8",
        )
        with mock.patch("sys.stderr", io.StringIO()):
            loaded = ctl.load_config()
        self.assertEqual(loaded["frame_rate"], 60)
        self.assertEqual(loaded["background"], "#000000")
        self.assertEqual(loaded["exclude_effects"], ctl.DEFAULT_CONFIG["exclude_effects"])


class EditorCommandTests(unittest.TestCase):
    def test_edit_splits_editor_with_shlex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            with mock.patch.object(ctl, "config_dir", config_dir), mock.patch.dict(
                "os.environ",
                {"VISUAL": '"/home/user/my editor" --wait', "EDITOR": "vim"},
            ), mock.patch("ctl.subprocess.run") as run:
                ctl.command_edit()
        run.assert_called_once()
        argv = run.call_args[0][0]
        self.assertEqual(argv[0], "/home/user/my editor")
        self.assertEqual(argv[1], "--wait")
        self.assertEqual(argv[2], str(config_dir / "logo.txt"))

    def test_edit_resolves_single_token_with_which(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            with mock.patch.object(ctl, "config_dir", config_dir), mock.patch.dict(
                "os.environ", {"VISUAL": "vim", "EDITOR": ""}
            ), mock.patch("ctl.editor_argv", return_value=["/usr/bin/vim"]) as editor, mock.patch(
                "ctl.subprocess.run"
            ) as run:
                ctl.command_edit()
        editor.assert_called_once_with("vim")
        self.assertEqual(run.call_args[0][0][0], "/usr/bin/vim")


class StopCommandTests(unittest.TestCase):
    def test_stop_uses_identity_checked_signal(self) -> None:
        output = io.StringIO()
        with mock.patch("ctl.current_pid", return_value=42), mock.patch(
            "ctl.send_signal_if_matches", return_value=True
        ) as send, mock.patch("sys.stdout", output):
            ctl.command_stop()
        send.assert_called_once_with(42, ctl.signal.SIGTERM, ctl.process_matches_installed_saver)
        self.assertIn("Stopped", output.getvalue())

    def test_stop_is_idempotent_when_not_running(self) -> None:
        output = io.StringIO()
        with mock.patch("ctl.current_pid", return_value=None), mock.patch(
            "ctl.send_signal_if_matches"
        ) as send, mock.patch("sys.stdout", output):
            ctl.command_stop()
        send.assert_not_called()
        self.assertIn("not running", output.getvalue())

    def test_stop_handles_exit_between_lookup_and_signal(self) -> None:
        output = io.StringIO()
        with mock.patch("ctl.current_pid", return_value=42), mock.patch(
            "ctl.send_signal_if_matches", return_value=False
        ), mock.patch("sys.stdout", output):
            ctl.command_stop()
        self.assertIn("no longer running", output.getvalue())

    def test_stop_handles_permission_error_without_traceback(self) -> None:
        output = io.StringIO()
        with mock.patch("ctl.current_pid", return_value=42), mock.patch(
            "ctl.send_signal_if_matches", side_effect=PermissionError
        ), mock.patch("sys.stdout", output):
            ctl.command_stop()
        self.assertIn("permission denied", output.getvalue())


class UninstallCommandTests(unittest.TestCase):
    def test_delegates_to_installed_hardened_uninstaller(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            installed_data = Path(tmp)
            uninstaller = installed_data / "uninstall.sh"
            uninstaller.write_text("#!/bin/sh\n", encoding="utf-8")
            uninstaller.chmod(0o755)
            completed = mock.Mock(returncode=0)
            with mock.patch.object(ctl, "data_dir", installed_data), mock.patch(
                "ctl.subprocess.run", return_value=completed
            ) as run:
                ctl.command_uninstall()
        run.assert_called_once_with(
            [str(uninstaller), "--non-interactive"],
            check=False,
        )

    def test_reports_hardened_uninstaller_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            installed_data = Path(tmp)
            uninstaller = installed_data / "uninstall.sh"
            uninstaller.write_text("#!/bin/sh\n", encoding="utf-8")
            uninstaller.chmod(0o755)
            completed = mock.Mock(returncode=7)
            with mock.patch.object(ctl, "data_dir", installed_data), mock.patch(
                "ctl.subprocess.run", return_value=completed
            ), self.assertRaises(SystemExit) as raised:
                ctl.command_uninstall()
        self.assertIn("status 7", str(raised.exception))

    def test_refuses_when_hardened_uninstaller_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            ctl, "data_dir", Path(tmp)
        ), self.assertRaises(SystemExit) as raised:
            ctl.command_uninstall()
        self.assertIn("uninstaller is missing", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
