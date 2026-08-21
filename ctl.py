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
runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
config_dir = config_home / "kde-ascii-saver"
config_file = config_dir / "config.json"
data_dir = data_home / "kde-ascii-saver"
pid_file = runtime_dir / f"kde-ascii-saver-{os.getuid()}.pid"
launcher = home / ".local" / "bin" / "kde-ascii-saver"
service = "kde-ascii-saver.service"


def load_config() -> dict:
    try:
        value = json.loads(config_file.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(config: dict) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    temporary = config_file.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    temporary.replace(config_file)


def update_config(key: str, value) -> None:
    config = load_config()
    config[key] = value
    save_config(config)


def current_pid() -> int | None:
    try:
        pid = int(pid_file.read_text(encoding="ascii"))
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
        return pid if b"kde-ascii-saver" in cmdline or b"app.py" in cmdline else None
    except (OSError, ValueError):
        return None


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
        pid_file.unlink(missing_ok=True)
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
    integration = subprocess.run(
        ["systemctl", "--user", "is-active", service],
        text=True,
        capture_output=True,
        check=False,
    ).stdout.strip()
    print(f"running: {'yes' if current_pid() else 'no'}")
    print(f"automatic: {'enabled' if config.get('enabled', True) else 'disabled'}")
    print(f"idle delay: {config.get('idle_delay', 120)} seconds")
    print(f"Plasma idle integration: {integration or 'unavailable'}")
    print(f"logo: {config_dir / 'logo.txt'}")


def command_uninstall() -> None:
    subprocess.run(
        ["systemctl", "--user", "disable", "--now", service],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for path in (
        data_dir,
        data_home / "applications" / "io.github.kde_ascii_saver.KdeAsciiSaver.desktop",
        config_home / "systemd" / "user" / service,
        home / ".local" / "bin" / "kde-ascii-saver",
        home / ".local" / "bin" / "kde-ascii-saverctl",
        home / ".local" / "bin" / "kde-ascii-saver-watcher",
    ):
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    print(f"Removed the application and service. Your art is preserved in {config_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Control KDE ASCII Saver")
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
