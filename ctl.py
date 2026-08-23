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

from helpers import (
    DEFAULT_CONFIG,
    editor_argv,
    load_config as load_config_file,
    pid_from_file,
    process_matches_saver,
    process_matches_watcher,
    read_version,
    runtime_dir,
    send_signal_if_matches,
)


home = Path.home()
config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
data_home = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
config_dir = config_home / "kde-ascii-saver"
config_file = config_dir / "config.json"
data_dir = data_home / "kde-ascii-saver"
launcher = home / ".local" / "bin" / "kde-ascii-saver"
service = "kde-ascii-saver.service"
autostart_file = config_home / "autostart" / "kde-ascii-saver-watcher.desktop"
VERSION = read_version()


def process_matches_installed_saver(pid: int) -> bool:
    return process_matches_saver(pid, data_dir / "app.py")


def process_matches_installed_watcher(pid: int) -> bool:
    return process_matches_watcher(pid, data_dir / "kde-ascii-saver-watcher")


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
    return load_config_file(config_file)


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
    return None if path is None else pid_from_file(path, process_matches_installed_saver)


def current_watcher_pid() -> int | None:
    path = watcher_pid_file()
    return None if path is None else pid_from_file(path, process_matches_installed_watcher)


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
    if not pid:
        print("KDE ASCII Saver is not running")
        return
    try:
        stopped = send_signal_if_matches(pid, signal.SIGTERM, process_matches_installed_saver)
    except PermissionError:
        print("Could not stop KDE ASCII Saver: permission denied")
        return
    print("Stopped KDE ASCII Saver" if stopped else "KDE ASCII Saver is no longer running")


def command_edit() -> None:
    logo = config_dir / "logo.txt"
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        argv = editor_argv(editor)
        if argv:
            subprocess.run([*argv, str(logo)], check=False)
            return
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
    installed_uninstaller = data_dir / "uninstall.sh"
    if not installed_uninstaller.is_file() or not os.access(installed_uninstaller, os.X_OK):
        raise SystemExit(
            "kde-ascii-saverctl: the hardened uninstaller is missing; "
            "reinstall KDE ASCII Saver or run uninstall.sh from a trusted source checkout"
        )
    completed = subprocess.run(
        [str(installed_uninstaller), "--non-interactive"],
        check=False,
    )
    if completed.returncode:
        raise SystemExit(
            f"kde-ascii-saverctl: uninstaller exited with status {completed.returncode}"
        )


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
        command_uninstall()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
