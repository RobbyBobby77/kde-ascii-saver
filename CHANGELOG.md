# Changelog

All notable changes to this project will be documented here.

## [Unreleased]

### Added

- Dependency guidance for Fedora/RHEL, Debian/Ubuntu, Arch, openSUSE, and
  manually packaged distributions.
- Fedora and Debian native-watcher builds in CI.
- XDG session autostart when no systemd user manager is available.
- A single-instance watcher lock and PID-based lifecycle for autostart mode.
- Unit tests for config merge, config validation, TTE restart backoff, and
  `$EDITOR` argv parsing.

### Changed

- Resolve Python from `PATH` instead of assuming `/usr/bin/python3`.
- Report either systemd or XDG autostart integration in controller status.
- Probe GTK4 Layer Shell after GTK connects a display.
- Watcher lock failures exit 1, D-Bus `GetActive` uses a 1s timeout, and
  SIGTERM/SIGINT quit the overlay instead of relying on default terminate.
- TTE child crashes back off and give up instead of restarting every 80 ms.
- `kde-ascii-saverctl` refuses to overwrite an unreadable `config.json`.
- Require `XDG_RUNTIME_DIR` for PID and lock files instead of falling back to
  `/tmp`.
- Build the native watcher in a temporary directory and `cmake --install` into
  the data dir.
- Read the project version from the `VERSION` file.
- Validate `frame_rate`, colors, `exclude_effects`, `enabled`, and `idle_delay`
  when loading `config.json`.
- Split `$EDITOR` / `$VISUAL` with `shlex` and resolve a single token with
  `shutil.which`.
- Follow Gdk monitor add/remove while the saver is showing.
- Skip blocking `GetActive` once `AboutToLock` or `ActiveChanged` already
  reported a lock.
- Compile the watcher with `-Wall -Wextra` on GCC and Clang.
- Claim renderer and watcher PID files exclusively (`O_EXCL`, mode `0600`)
  inside `$XDG_RUNTIME_DIR`.
- Decode TTE child exits with waitpid helpers and give up after five
  consecutive failures, matching gnome-ascii-saver.
- Document default-branch-only security support and the PyPI/venv install path.

### Fixed

- Probe `GetActive` while the cached lock flag is set so a cancelled
  `AboutToLock` without `ActiveChanged(false)` cannot block idle launch.
- Fedora/RHEL dependency hint now includes `python3-pip` and `python3-devel`.

## [0.1.0] - 2026-08-21

### Added

- Multi-monitor animated ASCII renderer using GTK 4, VTE, and TTE.
- KWin Layer Shell overlays with an X11 fullscreen fallback.
- Native Qt 6/KF6 KIdleTime watcher for Plasma Wayland and X11.
- Safe KScreenLocker `AboutToLock`, `ActiveChanged`, and `GetActive` handling.
- Plasma user service, desktop entry, installer, uninstaller, and control CLI.
- Upgrade-safe configuration and editable Plasma ASCII artwork.
- Fedora CI and public-ready project documentation.

[Unreleased]: https://github.com/RobbyBobby77/kde-ascii-saver/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/RobbyBobby77/kde-ascii-saver/releases/tag/v0.1.0
