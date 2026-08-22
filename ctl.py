#!/usr/bin/env python3
"""Control utility for KDE ASCII Saver."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
from pathlib import Path


home = Path.home()
config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
data_home = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
config_dir = config_home / "kde-ascii-saver"
config_file = config_dir / "config.json"
data_dir = data_home / "kde-ascii-saver"
launcher = home / ".local" / "bin" / "kde-ascii-saver"
service = "kde-ascii-saver.service"
autostart_file = config_home / "autostart" / "kde-ascii-saver-watcher.desktop"

DEFAULT_CONFIG = {
    "enabled": True,
    "idle_delay": 120,
    "font": "Monospace 18",
    "background": "#000000",
    "frame_rate": 60,
    "exclude_effects": ["bouncyballs", "overflow"],
}


def load_version() -> str:
    try:
        text = Path(__file__).with_name("VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0.1.0"
    return text or "0.1.0"


VERSION = load_version()


def runtime_dir() -> Path | None:
    value = os.environ.get("XDG_RUNTIME_DIR")
    return Path(value) if value else None


def pid_file() -> Path | None:
    directory = runtime_dir()
    return None if directory is None else directory / f"kde-ascii-saver-{os.getuid()}.pid"


def watcher_pid_file() -> Path | None:
    directory = runtime_dir()
    return None if directory is None else directory / f"kde-ascii-saver-watcher-{os.getuid()}.pid"


def systemd_user_available() -> bool:
    executable = shutil.which("systemctl")
    if executable is None:
        return False
    return subprocess.run(
        [executable, "--user", "show-environment"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def load_config() -> dict:
    config = dict(DEFAULT_CONFIG)
    try:
        value = json.loads(config_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return config
    except (OSError, ValueError):
        return config
    if isinstance(value, dict):
        config.update(value)
    return config


def save_config(config: dict) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    temporary = config_file.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    temporary.replace(config_file)


def update_config(key: str, value) -> None:
    """Merge one key into config.json. Refuse to clobber an unreadable file."""
    if config_file.exists():
        try:
            loaded = json.loads(config_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SystemExit(
                f"kde-ascii-saverctl: config.json is unreadable ({exc}); refusing to overwrite it"
            ) from exc
        if not isinstance(loaded, dict):
            raise SystemExit(
                "kde-ascii-saverctl: config.json is not a JSON object; refusing to overwrite it"
            )
    else:
        loaded = {}
    config = dict(DEFAULT_CONFIG)
    config.update(loaded)
    config[key] = value
    save_config(config)


def current_pid() -> int | None:
    path = pid_file()
    if path is None:
        return None
    try:
        pid = int(path.read_text(encoding="ascii"))
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
        return pid if b"kde-ascii-saver" in cmdline or b"app.py" in cmdline else None
    except (OSError, ValueError):
        return None


def current_watcher_pid() -> int | None:
    path = watcher_pid_file()
    if path is None:
        return None
    try:
        pid = int(path.read_text(encoding="ascii"))
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
        return pid if b"kde-ascii-saver-watcher" in cmdline else None
    except (OSError, ValueError):
        return None


def stop_watcher() -> None:
    pid = current_watcher_pid()
    if pid is not None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    path = watcher_pid_file()
    if path is not None:
        path.unlink(missing_ok=True)


def command_start(windowed: bool = False) -> None:
    if current_pid():
        print("KDE ASCII Saver is already running")
        return
    args = [str(launcher)]
    if windowed:
        args.append("--windowed")
    subprocess.Popen(args, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def command_stop() -> None:
    pid = current_pid()
    path = pid_file()
    if not pid:
        if path is not None:
            path.unlink(missing_ok=True)
        print("KDE ASCII Saver is not running")
        return
    os.kill(pid, signal.SIGTERM)
    print("Stopped KDE ASCII Saver")


def command_edit() -> None:
    logo = config_dir / "logo.txt"
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        subprocess.run([*editor.split(), str(logo)], check=False)
    else:
        subprocess.Popen(["xdg-open", str(logo)], start_new_session=True)


def command_status() -> None:
    config = load_config()
    if systemd_user_available():
        state = subprocess.run(
            ["systemctl", "--user", "is-active", service],
            text=True,
            capture_output=True,
            check=False,
        ).stdout.strip()
        integration = f"systemd user service ({state or 'unavailable'})"
    elif current_watcher_pid() is not None:
        integration = "XDG session autostart (active)"
    elif autostart_file.exists():
        integration = "XDG session autostart (starts next login)"
    else:
        integration = "unavailable"
    print(f"running: {'yes' if current_pid() else 'no'}")
    print(f"automatic: {'enabled' if config.get('enabled', True) else 'disabled'}")
    print(f"idle delay: {config.get('idle_delay', 120)} seconds")
    print(f"Plasma idle integration: {integration or 'unavailable'}")
    print(f"logo: {config_dir / 'logo.txt'}")


def command_uninstall() -> None:
    if systemd_user_available():
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", service],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    stop_watcher()
    for path in (
        data_dir,
        data_home / "applications" / "io.github.kde_ascii_saver.KdeAsciiSaver.desktop",
        config_home / "systemd" / "user" / service,
        autostart_file,
        home / ".local" / "bin" / "kde-ascii-saver",
        home / ".local" / "bin" / "kde-ascii-saverctl",
        home / ".local" / "bin" / "kde-ascii-saver-watcher",
    ):
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
    if systemd_user_available():
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    print(f"Removed the application and idle integration. Your art is preserved in {config_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Control KDE ASCII Saver")
    parser.add_argument("--version", action="version", version=f"KDE ASCII Saver {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("start")
    sub.add_parser("preview")
    sub.add_parser("stop")
    sub.add_parser("edit")
    sub.add_parser("prefs")
    sub.add_parser("enable")
    sub.add_parser("disable")
    delay_parser = sub.add_parser("delay")
    delay_parser.add_argument("seconds", type=int)
    sub.add_parser("status")
    sub.add_parser("uninstall")
    args = parser.parse_args()

    if args.command == "start":
        command_start()
    elif args.command == "preview":
        command_start(windowed=True)
    elif args.command == "stop":
        command_stop()
    elif args.command == "edit":
        command_edit()
    elif args.command == "prefs":
        subprocess.Popen(["xdg-open", str(config_file)], start_new_session=True)
    elif args.command in ("enable", "disable"):
        update_config("enabled", args.command == "enable")
        print(f"Automatic screensaver {args.command}d")
    elif args.command == "delay":
        if not 10 <= args.seconds <= 86400:
            parser.error("delay must be between 10 and 86400 seconds")
        update_config("idle_delay", args.seconds)
        print(f"Idle delay set to {args.seconds} seconds")
    elif args.command == "status":
        command_status()
    elif args.command == "uninstall":
        if current_pid():
            command_stop()
        command_uninstall()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
