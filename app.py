#!/usr/bin/env python3
"""Fullscreen GTK/VTE renderer for KDE ASCII Saver."""

from __future__ import annotations

import argparse
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

from helpers import (  # noqa: E402
    TTE_MAX_FAILURES,
    TTE_SUCCESS_RESTART_MS,
    load_config,
    pid_file_path,
    read_version,
    runtime_dir,
    tte_exit_ok,
    tte_failure_delay_ms,
    write_pid_file,
)


APP_ID = "io.github.kde_ascii_saver.KdeAsciiSaver"
VERSION = read_version()


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
        self.closing = False
        self.tte_failures = 0
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
            str(self.app.config["frame_rate"]),
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
        if excluded:
            argv.extend(["--exclude-effects", *excluded])
        return argv

    def _start(self) -> bool:
        if self.app.stopping or self.closing or self.running:
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
            if self.app.stopping or self.closing or self.cancellable.is_cancelled():
                return
            print(f"kde-ascii-saver: could not start animation: {error.message}", file=sys.stderr)
            self.app.quit_saver()
        elif pid == -1:
            self.running = False
            if not self.app.stopping and not self.closing:
                self.app.quit_saver()

    def _on_child_exited(self, _terminal, status) -> None:
        self.running = False
        if self.app.once:
            self.app.quit_saver()
            return
        if self.app.stopping or self.closing:
            return
        if tte_exit_ok(status):
            self.tte_failures = 0
            GLib.timeout_add(TTE_SUCCESS_RESTART_MS, self._start)
            return
        self.tte_failures += 1
        delay = tte_failure_delay_ms(self.tte_failures)
        if delay is None:
            print(
                f"kde-ascii-saver: animation exited with status {status}; "
                f"giving up after {TTE_MAX_FAILURES} failures",
                file=sys.stderr,
            )
            self.app.quit_saver()
            return
        print(
            f"kde-ascii-saver: animation exited with status {status}; "
            f"retrying in {delay} ms ({self.tte_failures}/{TTE_MAX_FAILURES})",
            file=sys.stderr,
        )
        GLib.timeout_add(delay, self._start)


class SaverApplication(Gtk.Application):
    def __init__(self, *, windowed: bool, once: bool):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.windowed = windowed
        self.once = once
        self.config = load_config(CONFIG_DIR / "config.json")
        self.stopping = False
        self.pid_file: Path | None = None
        self._monitors = None
        self._screen_lock_bus: Gio.DBusConnection | None = None
        self._screen_lock_subscriptions: list[int] = []
        self._screen_lock_ready = False
        self._screen_lock_query_pending = False
        # Probed in do_startup after GTK connects a display; fullscreen fallback otherwise.
        self.layer_shell = False

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        if not self._watch_screen_lock():
            # This application is a visual overlay, never a locking surface.
            # Fail closed when lock handoff cannot be observed.
            print(
                "kde-ascii-saver: could not monitor KScreenLocker; refusing to start",
                file=sys.stderr,
            )
            self.stopping = True
            self.quit()
            return
        display = Gdk.Display.get_default()
        self.layer_shell = bool(
            display is not None and Gtk4LayerShell is not None and Gtk4LayerShell.is_supported()
        )
        css = Gtk.CssProvider()
        css.load_from_data(b"window, vte-terminal { background: #000; padding: 0; margin: 0; }")
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.set_accels_for_action("app.quit", ["Escape"])

    def do_activate(self) -> None:
        # The initial GetActive reply must arrive before any visual surface is
        # created. This avoids a brief overlay when a process is launched into
        # an already-locked session.
        if self.stopping or not self._screen_lock_ready:
            return
        if self.get_windows():
            for window in self.get_windows():
                window.present()
            return

        if self.pid_file is None:
            try:
                self.pid_file = write_pid_file(pid_file_path(), os.getpid())
            except (OSError, RuntimeError) as error:
                print(f"kde-ascii-saver: {error}", file=sys.stderr)
                self.quit()
                return
        if self.windowed:
            SaverWindow(self, None, True)
            return

        display = Gdk.Display.get_default()
        self._monitors = display.get_monitors() if display else None
        if self._monitors is not None:
            self._monitors.connect("items-changed", self._on_monitors_changed)
        self._sync_monitor_windows()

    def _watch_screen_lock(self) -> bool:
        """Subscribe before creating windows, then query the current lock state."""
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error:
            return False
        if bus is None:
            return False

        self._screen_lock_bus = bus
        self._screen_lock_subscriptions = [
            bus.signal_subscribe(
                "org.kde.screensaver",
                "org.kde.screensaver",
                "AboutToLock",
                "/ScreenSaver",
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_about_to_lock,
                None,
            ),
            bus.signal_subscribe(
                "org.freedesktop.ScreenSaver",
                "org.freedesktop.ScreenSaver",
                "ActiveChanged",
                "/ScreenSaver",
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_active_changed,
                None,
            ),
        ]
        # Keep the Gtk.Application registered while do_activate waits for this
        # asynchronous reply; otherwise it can exit because it has no window.
        self.hold()
        self._screen_lock_query_pending = True
        try:
            bus.call(
                "org.freedesktop.ScreenSaver",
                "/ScreenSaver",
                "org.freedesktop.ScreenSaver",
                "GetActive",
                None,
                GLib.VariantType.new("(b)"),
                Gio.DBusCallFlags.NONE,
                1000,
                None,
                self._on_get_active_finished,
                None,
            )
        except GLib.Error:
            self._finish_screen_lock_query()
            return False
        return True

    def _finish_screen_lock_query(self) -> None:
        if self._screen_lock_query_pending:
            self._screen_lock_query_pending = False
            self.release()

    def _on_about_to_lock(self, *_args) -> None:
        self.quit_saver()

    def _on_active_changed(
        self,
        _connection,
        _sender_name,
        _object_path,
        _interface_name,
        _signal_name,
        parameters,
        _user_data,
    ) -> None:
        try:
            active = bool(parameters.unpack()[0])
        except (AttributeError, IndexError, TypeError):
            return
        if active:
            self.quit_saver()

    def _on_get_active_finished(self, connection, result, _user_data) -> None:
        try:
            active = bool(connection.call_finish(result).unpack()[0])
        except (GLib.Error, AttributeError, IndexError, TypeError) as error:
            if not self.stopping:
                print(
                    f"kde-ascii-saver: could not query KScreenLocker: {error}",
                    file=sys.stderr,
                )
                self.stopping = True
                self._finish_screen_lock_query()
                self.quit()
            return
        if self.stopping:
            self._finish_screen_lock_query()
            return
        if active:
            self._finish_screen_lock_query()
            self.quit_saver()
            return
        self._screen_lock_ready = True
        self.activate()
        self._finish_screen_lock_query()

    def _on_monitors_changed(self, _model, _position, _removed, _added) -> None:
        self._sync_monitor_windows()

    def _close_overlay_window(self, window: SaverWindow) -> None:
        window.closing = True
        window.cancellable.cancel()
        window.terminal.feed_child(bytes((3,)))
        window.destroy()

    def _overlay_windows(self) -> list[SaverWindow]:
        return [window for window in self.get_windows() if not getattr(window, "windowed", False)]

    def _sync_monitor_windows(self) -> None:
        if self.stopping or self.windowed:
            return
        current = []
        if self._monitors is not None:
            current = [self._monitors.get_item(index) for index in range(self._monitors.get_n_items())]
        alive = set(current)
        for window in list(self._overlay_windows()):
            monitor = getattr(window, "monitor", None)
            if current:
                if monitor is None or monitor not in alive:
                    self._close_overlay_window(window)
            elif monitor is not None:
                self._close_overlay_window(window)
        remaining = {window.monitor for window in self._overlay_windows()}
        if current:
            for monitor in current:
                if monitor not in remaining:
                    SaverWindow(self, monitor, False, keyboard_surface=False)
            self._refresh_keyboard_surface()
        elif not self._overlay_windows():
            SaverWindow(self, None, False, keyboard_surface=True)

    def _refresh_keyboard_surface(self) -> None:
        if not self.layer_shell or Gtk4LayerShell is None:
            return
        primary = None
        if self._monitors is not None and self._monitors.get_n_items():
            primary = self._monitors.get_item(0)
        assigned = False
        for window in self._overlay_windows():
            exclusive = not assigned and (window.monitor is primary or primary is None)
            if exclusive:
                assigned = True
            Gtk4LayerShell.set_keyboard_mode(
                window,
                Gtk4LayerShell.KeyboardMode.EXCLUSIVE if exclusive else Gtk4LayerShell.KeyboardMode.NONE,
            )

    def quit_saver(self) -> None:
        if self.stopping:
            return
        self.stopping = True
        for window in list(self.get_windows()):
            window.closing = True
            window.cancellable.cancel()
            window.terminal.feed_child(bytes((3,)))
            window.destroy()
        self.quit()

    def do_shutdown(self) -> None:
        bus = self._screen_lock_bus
        if bus is not None:
            for subscription in self._screen_lock_subscriptions:
                bus.signal_unsubscribe(subscription)
        self._screen_lock_subscriptions.clear()
        self._screen_lock_bus = None
        path = self.pid_file
        if path is not None:
            try:
                if path.read_text(encoding="ascii").strip() == str(os.getpid()):
                    path.unlink(missing_ok=True)
            except OSError:
                pass
        Gtk.Application.do_shutdown(self)


def main() -> int:
    parser = argparse.ArgumentParser(description="Omarchy-style ASCII screensaver for KDE Plasma")
    parser.add_argument("--version", action="version", version=f"KDE ASCII Saver {VERSION}")
    parser.add_argument("--windowed", action="store_true", help="open one decorated preview window")
    parser.add_argument("--once", action="store_true", help="exit after one animation")
    args = parser.parse_args()
    if runtime_dir() is None:
        print("kde-ascii-saver: XDG_RUNTIME_DIR is unset; refusing to start", file=sys.stderr)
        return 1
    app = SaverApplication(windowed=args.windowed, once=args.once)
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, lambda *_unused: GLib.idle_add(app.quit_saver))
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
