#!/usr/bin/env python3
"""GTK 4 control panel for KDE ASCII Saver."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

import ctl  # noqa: E402
from helpers import load_config, valid_color  # noqa: E402


APP_ID = "io.github.robbybobby77.KdeAsciiSaver"


class SettingsWindow(Gtk.ApplicationWindow):
    def __init__(self, application: Gtk.Application):
        super().__init__(application=application, title="KDE ASCII Saver")
        self.set_default_size(680, 650)

        header = Gtk.HeaderBar()
        title = Gtk.Label(label="KDE ASCII Saver")
        title.add_css_class("title")
        header.set_title_widget(title)
        self.set_titlebar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        for setter in (
            content.set_margin_top,
            content.set_margin_bottom,
            content.set_margin_start,
            content.set_margin_end,
        ):
            setter(24)

        status_frame = Gtk.Frame(label="Status")
        status_grid = Gtk.Grid(column_spacing=20, row_spacing=10)
        status_grid.set_margin_top(14)
        status_grid.set_margin_bottom(14)
        status_grid.set_margin_start(14)
        status_grid.set_margin_end(14)
        self.renderer_status = Gtk.Label(xalign=0)
        self.watcher_status = Gtk.Label(xalign=0)
        status_grid.attach(Gtk.Label(label="Renderer", xalign=0), 0, 0, 1, 1)
        status_grid.attach(self.renderer_status, 1, 0, 1, 1)
        status_grid.attach(Gtk.Label(label="Idle watcher", xalign=0), 0, 1, 1, 1)
        status_grid.attach(self.watcher_status, 1, 1, 1, 1)
        status_frame.set_child(status_grid)
        content.append(status_frame)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for label, command, suggested in (
            ("Start Now", "start", True),
            ("Preview", "preview", False),
            ("Stop", "stop", False),
        ):
            button = Gtk.Button(label=label)
            if suggested:
                button.add_css_class("suggested-action")
            button.connect("clicked", self._on_command, command)
            actions.append(button)
        content.append(actions)

        preferences = Gtk.Frame(label="Preferences")
        grid = Gtk.Grid(column_spacing=20, row_spacing=12)
        grid.set_margin_top(14)
        grid.set_margin_bottom(14)
        grid.set_margin_start(14)
        grid.set_margin_end(14)
        grid.set_hexpand(True)

        self.enabled = Gtk.Switch(halign=Gtk.Align.START)
        self.delay = Gtk.SpinButton.new_with_range(10, 86400, 10)
        self.delay.set_numeric(True)
        self.font = Gtk.Entry(hexpand=True)
        self.background = Gtk.Entry(hexpand=True)
        self.frame_rate = Gtk.SpinButton.new_with_range(1, 240, 1)
        self.frame_rate.set_numeric(True)
        self.exclude_effects = Gtk.Entry(hexpand=True)
        self.exclude_effects.set_placeholder_text("Comma-separated effect names")

        rows = (
            ("Automatic activation", self.enabled),
            ("Idle delay (seconds)", self.delay),
            ("Terminal font", self.font),
            ("Background (#RRGGBB)", self.background),
            ("Frame rate", self.frame_rate),
            ("Excluded effects", self.exclude_effects),
        )
        for row, (label, widget) in enumerate(rows):
            grid.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
            grid.attach(widget, 1, row, 1, 1)
        preferences.set_child(grid)
        content.append(preferences)

        file_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        edit_art = Gtk.Button(label="Edit Artwork")
        edit_art.connect("clicked", self._on_command, "edit")
        raw_config = Gtk.Button(label="Open Config File")
        raw_config.connect("clicked", self._on_command, "config")
        diagnostics = Gtk.Button(label="Run Diagnostics")
        diagnostics.connect("clicked", self._on_command, "doctor")
        file_actions.append(edit_art)
        file_actions.append(raw_config)
        file_actions.append(diagnostics)
        content.append(file_actions)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.notice = Gtk.Label(xalign=0, hexpand=True, wrap=True)
        save = Gtk.Button(label="Save Preferences")
        save.add_css_class("suggested-action")
        save.connect("clicked", self._on_save)
        footer.append(self.notice)
        footer.append(save)
        content.append(footer)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(content)
        self.set_child(scroller)

        self._load_preferences()
        self._refresh_status()
        GLib.timeout_add_seconds(2, self._refresh_status)

    def _load_preferences(self) -> None:
        config = load_config(ctl.config_file)
        self.enabled.set_active(bool(config["enabled"]))
        self.delay.set_value(int(config["idle_delay"]))
        self.font.set_text(str(config["font"]))
        self.background.set_text(str(config["background"]))
        self.frame_rate.set_value(int(config["frame_rate"]))
        self.exclude_effects.set_text(", ".join(config.get("exclude_effects", [])))

    def _refresh_status(self) -> bool:
        self.renderer_status.set_text("Running" if ctl.current_pid() else "Stopped")
        self.watcher_status.set_text("Active" if ctl.current_watcher_pid() else "Inactive")
        return GLib.SOURCE_CONTINUE

    def _set_notice(self, message: str, error: bool = False) -> None:
        self.notice.set_text(message)
        if error:
            self.notice.add_css_class("error")
        else:
            self.notice.remove_css_class("error")

    def _on_save(self, _button: Gtk.Button) -> None:
        background = self.background.get_text().strip()
        font = self.font.get_text().strip()
        excluded = [
            name.strip() for name in self.exclude_effects.get_text().split(",") if name.strip()
        ]
        if not font:
            self._set_notice("Choose a non-empty terminal font.", error=True)
            return
        if not valid_color(background):
            self._set_notice("Background must use six-digit #RRGGBB notation.", error=True)
            return
        if any(name.startswith("-") for name in excluded):
            self._set_notice("Excluded effect names cannot start with '-'.", error=True)
            return
        try:
            ctl.update_config_values(
                {
                    "enabled": self.enabled.get_active(),
                    "idle_delay": self.delay.get_value_as_int(),
                    "font": font,
                    "background": background,
                    "frame_rate": self.frame_rate.get_value_as_int(),
                    "exclude_effects": excluded,
                }
            )
        except (OSError, SystemExit) as error:
            self._set_notice(f"Could not save preferences: {error}", error=True)
            return
        self._set_notice("Preferences saved. The idle watcher will reload them automatically.")

    def _on_command(self, _button: Gtk.Button, command: str) -> None:
        self._set_notice(f"Running {command}…")

        def worker() -> None:
            try:
                completed = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve().with_name("ctl.py")), command],
                    text=True,
                    capture_output=True,
                    check=False,
                    env=os.environ.copy(),
                )
            except OSError as error:
                GLib.idle_add(self._command_finished, str(error), True)
                return
            output = (completed.stdout or completed.stderr).strip()
            if not output:
                output = (
                    f"{command} completed" if completed.returncode == 0 else f"{command} failed"
                )
            GLib.idle_add(
                self._command_finished,
                output,
                completed.returncode != 0,
            )

        threading.Thread(target=worker, daemon=True).start()

    def _command_finished(self, output: str, failed: bool) -> bool:
        self._set_notice(output, error=failed)
        self._refresh_status()
        return GLib.SOURCE_REMOVE


class SettingsApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self) -> None:
        window = self.props.active_window
        if window is None:
            window = SettingsWindow(self)
        window.present()


def main() -> int:
    return SettingsApplication().run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
