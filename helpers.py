#!/usr/bin/env python3
"""Pure helpers shared by the renderer, controller, and unit tests."""

from __future__ import annotations

import json
import os
import signal
import shlex
import shutil
import sys
from collections.abc import Callable, Mapping
from pathlib import Path


DEFAULT_CONFIG = {
    "enabled": True,
    "idle_delay": 120,
    "font": "Monospace 18",
    "background": "#000000",
    "frame_rate": 60,
    "exclude_effects": ["bouncyballs", "overflow"],
}
# Same waitpid-aware budget as gnome-ascii-saver: five failures, uncapped delays.
TTE_SUCCESS_RESTART_MS = 80
TTE_MAX_FAILURES = 5
FALLBACK_VERSION = "0.1.0"
MAX_FRAME_RATE = 240


def _warn(message: str) -> None:
    print(f"kde-ascii-saver: {message}", file=sys.stderr)


def new_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    config["exclude_effects"] = list(DEFAULT_CONFIG["exclude_effects"])
    return config


def read_version(here: Path | None = None) -> str:
    root = Path(__file__).resolve().parent if here is None else here
    try:
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return FALLBACK_VERSION
    return version or FALLBACK_VERSION


def _valid_color(value: object) -> bool:
    """Return whether *value* works in both GDK and TTE.

    TTE accepts six-digit RGB values while GDK expects the leading ``#``.
    Restricting the shared setting to their intersection keeps a bad config
    from putting the renderer into its child-process failure loop.
    """
    if not isinstance(value, str):
        return False
    text = value.strip()
    digits = text[1:] if text.startswith("#") else ""
    return len(digits) == 6 and all(char in "0123456789abcdefABCDEF" for char in digits)


def _apply_config(config: dict, loaded: dict, origin: Path) -> dict:
    if "enabled" in loaded:
        enabled = loaded["enabled"]
        if isinstance(enabled, bool):
            config["enabled"] = enabled
        else:
            _warn(f"{origin}: ignoring invalid enabled {enabled!r}")

    if "idle_delay" in loaded:
        delay = loaded["idle_delay"]
        if isinstance(delay, bool) or not isinstance(delay, int) or not 10 <= delay <= 86400:
            _warn(f"{origin}: ignoring invalid idle_delay {delay!r}; using {config['idle_delay']}")
        else:
            config["idle_delay"] = delay

    font = loaded.get("font", config["font"])
    if isinstance(font, str) and font.strip():
        config["font"] = font
    elif "font" in loaded:
        _warn(f"{origin}: ignoring invalid font {font!r}")

    background = loaded.get("background", config["background"])
    if _valid_color(background):
        config["background"] = str(background).strip()
    elif "background" in loaded:
        _warn(f"{origin}: ignoring invalid background color {background!r}")

    if "frame_rate" in loaded:
        frame_rate = loaded["frame_rate"]
        if (
            isinstance(frame_rate, bool)
            or not isinstance(frame_rate, int)
            or not 1 <= frame_rate <= MAX_FRAME_RATE
        ):
            _warn(
                f"{origin}: ignoring invalid frame_rate {frame_rate!r}; "
                f"expected 1-{MAX_FRAME_RATE}, using {config['frame_rate']}"
            )
        else:
            config["frame_rate"] = frame_rate

    if "exclude_effects" in loaded:
        excluded = loaded["exclude_effects"]
        if not isinstance(excluded, list):
            _warn(f"{origin}: exclude_effects must be a list of names; using defaults")
        else:
            cleaned: list[str] = []
            for item in excluded:
                if not isinstance(item, str) or not item:
                    _warn(f"{origin}: ignoring invalid exclude_effects entry {item!r}")
                    continue
                if item.startswith("-"):
                    _warn(
                        f"{origin}: ignoring exclude_effects entry {item!r} because it starts with '-'"
                    )
                    continue
                cleaned.append(item)
            config["exclude_effects"] = cleaned
    return config


def load_config(path: Path) -> dict:
    config = new_config()
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return config
    except OSError as error:
        _warn(f"could not read {path}: {error}")
        return config
    except ValueError as error:
        _warn(f"invalid JSON in {path}: {error}")
        return config
    if not isinstance(loaded, dict):
        _warn(f"{path} must contain a JSON object")
        return config
    return _apply_config(config, loaded, path)


def tte_exit_ok(status: int) -> bool:
    """True when a TTE child finished an effect successfully.

    VTE reports a waitpid-style status. A decoded exit code of 0 is also
    treated as success. A raw `status == 0` check is not enough: exit code 1
    is encoded as `1 << 8`.
    """
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status) == 0
    if os.WIFSIGNALED(status):
        return False
    return status == 0


def tte_failure_delay_ms(consecutive_failures: int) -> int | None:
    """Exponential backoff after a failed TTE child, or None to give up."""
    if consecutive_failures < 1:
        raise ValueError("consecutive_failures must be >= 1")
    if consecutive_failures >= TTE_MAX_FAILURES:
        return None
    return TTE_SUCCESS_RESTART_MS * (2 ** (consecutive_failures - 1))


def tte_restart_after(status: int, failures: int) -> tuple[int, int] | None:
    """Return (delay_ms, updated_failures) or None to stop the saver."""
    if tte_exit_ok(status):
        return TTE_SUCCESS_RESTART_MS, 0
    failures += 1
    delay = tte_failure_delay_ms(failures)
    if delay is None:
        return None
    return delay, failures


def runtime_dir(env: Mapping[str, str] | None = None) -> Path | None:
    """Return $XDG_RUNTIME_DIR, or None. Never fall back to /tmp."""
    value = (os.environ if env is None else env).get("XDG_RUNTIME_DIR")
    return Path(value).expanduser() if value else None


def pid_file_path(
    env: Mapping[str, str] | None = None,
    *,
    uid: int | None = None,
) -> Path:
    directory = runtime_dir(env)
    if directory is None:
        raise RuntimeError("XDG_RUNTIME_DIR is unset; refusing to use a world-writable PID path")
    resolved_uid = os.getuid() if uid is None else uid
    return directory / f"kde-ascii-saver-{resolved_uid}.pid"


def _process_argv(pid: int) -> tuple[bytes, ...]:
    if pid <= 0:
        return ()
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return ()
    return tuple(argument for argument in cmdline.split(b"\0") if argument)


def process_matches_saver(pid: int, expected_script: Path | None = None) -> bool:
    """Match the renderer's exact Python script argument.

    A substring check can confuse the renderer with the controller, watcher,
    or an unrelated command whose argument happens to mention the project.
    Both supported launch paths invoke Python with an absolute ``app.py`` as
    argv[1], so compare that complete argument instead.
    """
    argv = _process_argv(pid)
    script = (
        Path(__file__).resolve().with_name("app.py")
        if expected_script is None
        else expected_script
    )
    if len(argv) < 2:
        return False
    try:
        actual_script = Path(os.fsdecode(argv[1])).resolve(strict=False)
    except UnicodeError:
        return False
    return actual_script == script.resolve(strict=False)


def process_matches_watcher(pid: int, expected_executable: Path | None = None) -> bool:
    """Match the watcher's exact executable, following ``/proc/PID/exe``."""
    if pid <= 0:
        return False
    executable = (
        Path(__file__).resolve().with_name("kde-ascii-saver-watcher")
        if expected_executable is None
        else expected_executable
    )
    try:
        actual = Path(os.readlink(f"/proc/{pid}/exe"))
    except OSError:
        return False
    return actual == executable.resolve(strict=False)


def pid_from_file(path: Path, matches: Callable[[int], bool]) -> int | None:
    try:
        pid = int(path.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return None
    return pid if matches(pid) else None


def send_signal_if_matches(pid: int, signum: int, matches: Callable[[int], bool]) -> bool:
    """Signal a matching process, using a pidfd where Python supports it.

    Opening the pidfd before the second identity check prevents PID reuse from
    redirecting the eventual signal to an unrelated process. The fallback is
    retained for Python/platform combinations without pidfd support.
    """
    pidfd_open = getattr(os, "pidfd_open", None)
    pidfd_send_signal = getattr(signal, "pidfd_send_signal", None)
    if pidfd_open is not None and pidfd_send_signal is not None:
        try:
            descriptor = pidfd_open(pid)
        except ProcessLookupError:
            return False
        try:
            if not matches(pid):
                return False
            try:
                pidfd_send_signal(descriptor, signum)
            except ProcessLookupError:
                return False
            return True
        finally:
            os.close(descriptor)

    if not matches(pid):
        return False
    try:
        os.kill(pid, signum)
    except ProcessLookupError:
        return False
    return True


def pid_file_is_stale(path: Path) -> bool:
    try:
        pid = int(path.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return True
    return not process_matches_saver(pid)


def write_pid_file(path: Path, pid: int) -> Path:
    """Claim a PID file with O_EXCL / 0600, replacing only a stale file."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        if not pid_file_is_stale(path):
            raise RuntimeError(f"pid file {path} is already claimed") from None
        path.unlink(missing_ok=True)
        fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, f"{pid}\n".encode("ascii"))
    finally:
        os.close(fd)
    return path


def current_saver_pid(path: Path | None = None) -> int | None:
    try:
        pid_path = path if path is not None else pid_file_path()
    except RuntimeError:
        return None
    return pid_from_file(pid_path, process_matches_saver)


def editor_argv(editor: str) -> list[str]:
    """Turn $EDITOR / $VISUAL into argv without a naive split on every space."""
    editor = editor.strip()
    if not editor:
        return []
    if " " not in editor:
        found = shutil.which(editor)
        return [found if found else editor]
    return shlex.split(editor)
