#!/usr/bin/env python3
"""Pure helpers shared by the renderer, controller, and unit tests."""

from __future__ import annotations

import json
import shlex
import shutil
import sys
from pathlib import Path


DEFAULT_CONFIG = {
    "enabled": True,
    "idle_delay": 120,
    "font": "Monospace 18",
    "background": "#000000",
    "frame_rate": 60,
    "exclude_effects": ["bouncyballs", "overflow"],
}
TTE_RESTART_MS = 80
TTE_MAX_FAILURES = 8
TTE_BACKOFF_CAP_MS = 5000
FALLBACK_VERSION = "0.1.0"


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
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or text.startswith("-"):
        return False
    if text.startswith("#"):
        digits = text[1:]
        return len(digits) in {3, 4, 6, 8} and all(char in "0123456789abcdefABCDEF" for char in digits)
    return True


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
        if isinstance(frame_rate, bool) or not isinstance(frame_rate, int) or frame_rate < 1:
            _warn(
                f"{origin}: ignoring invalid frame_rate {frame_rate!r}; using {config['frame_rate']}"
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


def tte_restart_after(status: int, failures: int) -> tuple[int, int] | None:
    """Return (delay_ms, updated_failures) or None to stop the saver.

    A zero wait/exit status is a completed effect. Anything else is a crash or
    missing resource: exponential backoff from TTE_RESTART_MS, capped, then
    give up after TTE_MAX_FAILURES consecutive failures.
    """
    if status == 0:
        return TTE_RESTART_MS, 0
    failures += 1
    if failures >= TTE_MAX_FAILURES:
        return None
    delay = min(TTE_BACKOFF_CAP_MS, TTE_RESTART_MS * (2 ** (failures - 1)))
    return delay, failures


def editor_argv(editor: str) -> list[str]:
    """Turn $EDITOR / $VISUAL into argv without a naive split on every space."""
    editor = editor.strip()
    if not editor:
        return []
    if " " not in editor:
        found = shutil.which(editor)
        return [found if found else editor]
    return shlex.split(editor)
