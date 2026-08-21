#!/usr/bin/env python3
"""Fullscreen GTK/VTE renderer for KDE ASCII Saver."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Vte", "3.91")
try:
    # Load the Layer Shell namespace before GTK realizes a Wayland surface.
    gi.require_version("Gtk4LayerShell", "1.0")
    _LAYER_SHELL_AVAILABLE = True
except ValueError:
    _LAYER_SHELL_AVAILABLE = False
if _LAYER_SHELL_AVAILABLE:
    from gi.repository import Gtk4LayerShell  # type: ignore[attr-defined]  # noqa: E402
else:
    Gtk4LayerShell = None
from gi.repository import Gdk, Gio, GLib, Gtk, Pango, Vte  # noqa: E402


APP_ID = "io.github.kde_ascii_saver.KdeAsciiSaver"
VERSION = "0.1.0"
DEFAULT_CONFIG = {
    "font": "Monospace 18",
    "background": "#000000",
    "frame_rate": 60,
    "exclude_effects": ["bouncyballs", "overflow"],
}


def xdg_path(env_name: str, fallback: Path) -> Path:
    value = os.environ.get(env_name)
    return Path(value).expanduser() if value else fallback


CONFIG_DIR = Path(
    os.environ.get(
        "KDE_ASCII_SAVER_CONFIG_DIR",
        xdg_path("XDG_CONFIG_HOME", Path.home() / ".config") / "kde-ascii-saver",
    )
)
DATA_DIR = Path(
    os.environ.get(
        "KDE_ASCII_SAVER_DATA_DIR",
        xdg_path("XDG_DATA_HOME", Path.home() / ".local" / "share") / "kde-ascii-saver",
    )
)
RUNTIME_DIR = xdg_path("XDG_RUNTIME_DIR", Path("/tmp"))
PID_FILE = RUNTIME_DIR / f"kde-ascii-saver-{os.getuid()}.pid"


def load_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    try:
        loaded = json.loads((CONFIG_DIR / "config.json").read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            config.update(loaded)
    except (OSError, ValueError):
        pass
    return config


def parse_color(value: str, fallback: str) -> Gdk.RGBA:
    color = Gdk.RGBA()
    if not color.parse(value):
        color.parse(fallback)
    return color


class SaverWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        app: "SaverApplication",
        monitor: Gdk.Monitor | None,
        windowed: bool,
        keyboard_surface: bool = False,
    ):
        super().__init__(application=app, title="KDE ASCII Saver")
        self.app = app
        self.monitor = monitor
        self.windowed = windowed
        self.armed = False
        self.running = False
        self.cancellable = Gio.Cancellable()
        self.set_decorated(windowed)
        self.set_resizable(True)

        self.terminal = Vte.Terminal()
        self.terminal.set_hexpand(True)
        self.terminal.set_vexpand(True)
        self.terminal.set_font(Pango.FontDescription.from_string(str(app.config["font"])))
        self.terminal.set_cursor_blink_mode(Vte.CursorBlinkMode.OFF)
        self.terminal.set_cursor_shape(Vte.CursorShape.BLOCK)
        background = parse_color(str(app.config["background"]), "#000000")
        foreground = parse_color("#f2f2f2", "#ffffff")
        self.terminal.set_colors(foreground, background, [])
        self.terminal.connect("child-exited", self._on_child_exited)
        self.set_child(self.terminal)

        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._dismiss)
        self.add_controller(key)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._dismiss)
        self.add_controller(motion)
        click = Gtk.GestureClick()
        click.connect("pressed", self._dismiss)
        self.add_controller(click)
        scroll = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.BOTH_AXES)
        scroll.connect("scroll", self._dismiss)
        self.add_controller(scroll)

        if windowed:
            self.set_default_size(1000, 700)
        elif app.layer_shell:
            Gtk4LayerShell.init_for_window(self)
            Gtk4LayerShell.set_namespace(self, "kde-ascii-saver")
            Gtk4LayerShell.set_layer(self, Gtk4LayerShell.Layer.OVERLAY)
            Gtk4LayerShell.set_monitor(self, monitor)
            for edge in (
                Gtk4LayerShell.Edge.LEFT,
                Gtk4LayerShell.Edge.RIGHT,
                Gtk4LayerShell.Edge.TOP,
                Gtk4LayerShell.Edge.BOTTOM,
            ):
                Gtk4LayerShell.set_anchor(self, edge, True)
            Gtk4LayerShell.set_exclusive_zone(self, -1)
            keyboard_mode = (
                Gtk4LayerShell.KeyboardMode.EXCLUSIVE
                if keyboard_surface
                else Gtk4LayerShell.KeyboardMode.NONE
            )
            Gtk4LayerShell.set_keyboard_mode(self, keyboard_mode)
        elif monitor is not None:
            self.fullscreen_on_monitor(monitor)
        else:
            self.fullscreen()

        self.connect("close-request", self._on_close)
        self.present()
        if not windowed:
            self._hide_cursor()
        GLib.timeout_add(350, self._start)
        GLib.timeout_add(900, self._arm)

    def _hide_cursor(self) -> None:
        pixels = GLib.Bytes.new(bytes((0, 0, 0, 0)))
        texture = Gdk.MemoryTexture.new(1, 1, Gdk.MemoryFormat.R8G8B8A8, pixels, 4)
        self.set_cursor(Gdk.Cursor.new_from_texture(texture, 0, 0, None))

    def _arm(self) -> bool:
        self.armed = True
        return GLib.SOURCE_REMOVE

    def _dismiss(self, *_args):
        if self.armed:
            self.app.quit_saver()
        return True

    def _on_close(self, *_args):
        self.app.quit_saver()
        return False

    def _tte_argv(self) -> list[str]:
        executable = Path(os.environ.get("KDE_ASCII_SAVER_TTE", DATA_DIR / "venv" / "bin" / "tte"))
        if not executable.exists():
            executable = Path("tte")
        background = str(self.app.config["background"]).lstrip("#")
        argv = [
            str(executable),
            "-i",
            str(CONFIG_DIR / "logo.txt"),
            "--frame-rate",
            str(max(1, int(self.app.config["frame_rate"]))),
            "--canvas-width",
            "0",
            "--canvas-height",
            "0",
            "--anchor-canvas",
            "c",
            "--anchor-text",
            "c",
            "--terminal-background-color",
            background,
            "--random-effect",
            "--no-eol",
            "--no-restore-cursor",
        ]
        excluded = self.app.config.get("exclude_effects", [])
        if isinstance(excluded, list) and excluded:
            argv.extend(["--exclude-effects", *map(str, excluded)])
        return argv

    def _start(self) -> bool:
        if self.app.stopping or self.running:
            return GLib.SOURCE_REMOVE
        self.running = True
        self.terminal.spawn_async(
            pty_flags=Vte.PtyFlags.DEFAULT,
            working_directory=str(Path.home()),
            argv=self._tte_argv(),
            envv=None,
            spawn_flags=GLib.SpawnFlags.SEARCH_PATH,
            child_setup=None,
            timeout=-1,
            cancellable=self.cancellable,
            callback=self._on_spawned,
            user_data=self,
        )
        return GLib.SOURCE_REMOVE

    def _on_spawned(self, _terminal, pid, error, _data) -> None:
        if error is not None:
            self.running = False
            print(f"kde-ascii-saver: could not start animation: {error.message}", file=sys.stderr)
            self.app.quit_saver()
        elif pid == -1:
            self.running = False
            self.app.quit_saver()

    def _on_child_exited(self, _terminal, _status) -> None:
        self.running = False
        if self.app.once:
            self.app.quit_saver()
        elif not self.app.stopping:
            GLib.timeout_add(80, self._start)


class SaverApplication(Gtk.Application):
    def __init__(self, *, windowed: bool, once: bool):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.windowed = windowed
        self.once = once
        self.config = load_config()
        self.stopping = False
        self.layer_shell = bool(Gtk4LayerShell and Gtk4LayerShell.is_supported())

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        css = Gtk.CssProvider()
        css.load_from_data(b"window, vte-terminal { background: #000; padding: 0; margin: 0; }")
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.set_accels_for_action("app.quit", ["Escape"])

    def do_activate(self) -> None:
        if self.get_windows():
            for window in self.get_windows():
                window.present()
            return

        PID_FILE.write_text(str(os.getpid()), encoding="ascii")
        if self.windowed:
            SaverWindow(self, None, True)
            return

        display = Gdk.Display.get_default()
        monitors = display.get_monitors() if display else None
        count = monitors.get_n_items() if monitors else 0
        if count:
            for index in range(count):
                SaverWindow(self, monitors.get_item(index), False, keyboard_surface=index == 0)
        else:
            SaverWindow(self, None, False)

    def quit_saver(self) -> None:
        if self.stopping:
            return
        self.stopping = True
        for window in list(self.get_windows()):
            window.terminal.feed_child(bytes((3,)))
            window.destroy()
        self.quit()

    def do_shutdown(self) -> None:
        try:
            if PID_FILE.read_text(encoding="ascii").strip() == str(os.getpid()):
                PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        Gtk.Application.do_shutdown(self)


def main() -> int:
    parser = argparse.ArgumentParser(description="Omarchy-style ASCII screensaver for KDE Plasma")
    parser.add_argument("--version", action="version", version=f"KDE ASCII Saver {VERSION}")
    parser.add_argument("--windowed", action="store_true", help="open one decorated preview window")
    parser.add_argument("--once", action="store_true", help="exit after one animation")
    args = parser.parse_args()
    app = SaverApplication(windowed=args.windowed, once=args.once)
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, lambda *_unused: GLib.idle_add(app.quit_saver))
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
