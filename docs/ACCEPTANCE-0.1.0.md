# Version 0.1.0 acceptance record

This record separates completed launch validation from cases that still need a
person to observe them on suitable hardware. It does not turn KDE ASCII Saver
into an authentication screen; KScreenLocker remains the security boundary.

## Environment

- Date: 2026-08-22
- Distribution: CachyOS
- KDE Plasma: 6.7.4
- KWin: 6.7.4
- Session: Wayland
- Display: built-in `eDP-1`, 2560x1600 at 180 Hz
- Logical geometry: 1600x1000 at 160% scale
- Integration: active systemd user service

## Passed

- 65 Python unit tests, installer tests, metadata checks, and native watcher
  build passed locally.
- Fedora 44 and Debian 13 passed the merged `main` CI matrix, including release
  packaging and the hash-pinned TerminalTextEffects installation.
- A committed `v0.1.0`-shaped archive passed checksum verification, online
  bootstrap extraction, compilation, install, version checks, and uninstall.
- Isolated install, repeated upgrade, rollback simulation, and uninstall
  preserved `config.json` and `logo.txt`.
- A real in-place systemd upgrade preserved the existing config and artwork
  byte for byte, removed the old embedded build directory, and restarted the
  watcher without journal errors.
- Decorated preview and fullscreen Wayland launch paths created a renderer and
  a real TerminalTextEffects 0.15.0 child with the expected arguments.
- Controller shutdown removed the renderer, TTE child, and runtime PID file.
- A manual KScreenLocker request while the fullscreen saver was active emitted
  the lock handoff: within one second the renderer and TTE child had exited and
  `org.freedesktop.ScreenSaver.GetActive` returned `true`.
- After normal unlock, `GetActive` returned `false` and the systemd watcher
  remained active without new journal errors.

## Still required before claiming stable coverage

- Observe and record keyboard, pointer motion, click, and scroll dismissal as
  separate controlled cases.
- Observe an automatic idle-time launch and automatic KScreenLocker handoff.
- Confirm visual placement and panel coverage, not only process lifecycle, on
  the 160% Wayland display.
- Repeat the Wayland cases with multiple monitors, mixed scale factors, and
  monitor hotplug when that hardware is available.
- Repeat the manual launch, dismissal, lock, and monitor cases in a Plasma X11
  session.
- Exercise a live XDG-autostart session rather than the isolated no-session
  installation path.
- Capture and privacy-review a real screenshot or short recording for the
  public project page.

Version 0.1.0 should remain described as a preview until these remaining cases
are completed or explicitly disclosed in its release notes.
