# Changelog

All notable changes to this project will be documented here.

## [Unreleased]

### Added

- A GTK 4 control panel for status, start, preview, stop, preferences, artwork,
  and installation diagnostics.
- Guided installation of missing system dependencies on Fedora/RHEL,
  Debian/Ubuntu, Arch-family, and openSUSE systems.
- AppStream metadata and a project icon for desktop integration.
- Offline TerminalTextEffects wheels in published release archives.
- `kde-ascii-saverctl doctor` for runtime, configuration, D-Bus, and watcher
  checks.

### Changed

- Use the project-controlled `io.github.robbybobby77.KdeAsciiSaver` application
  ID and migrate legacy desktop entries during upgrade.
- `kde-ascii-saverctl prefs` opens the control panel; `config` opens the raw
  JSON file.
- Manual start and preview commands now report early renderer failures.
- Configuration updates use unique temporary files and sync data before their
  atomic replacement.

### Fixed

- Wait for an XDG-autostarted watcher to release its single-instance lock
  before replacing it, and verify that its successor starts successfully.
- Align the changelog with the contents and publication date of version 0.1.0.

## [0.1.0] - 2026-08-30

### Added

- Multi-monitor animated ASCII renderer using GTK 4, VTE, and TTE.
- KWin Layer Shell overlays with an X11 fullscreen fallback.
- Native Qt 6/KF6 KIdleTime watcher for Plasma Wayland and X11.
- Safe KScreenLocker `AboutToLock`, `ActiveChanged`, and `GetActive` handling.
- Plasma user service, desktop entry, installer, uninstaller, and control CLI.
- Upgrade-safe configuration and editable Plasma ASCII artwork.
- A checksum-verifying online installer for the latest stable tagged release.
- Public installation, maintenance, troubleshooting, support, security, and
  release-acceptance documentation.
- Structured GitHub forms for bug reports and feature requests.
- Dependency guidance for Fedora/RHEL, Debian/Ubuntu, Arch, openSUSE, and
  manually packaged distributions.
- Fedora and Debian native-watcher builds in CI.
- XDG session autostart when no systemd user manager is available.
- A single-instance watcher lock and PID-based lifecycle for autostart mode.
- Unit tests for config merge, config validation, TTE restart backoff, and
  `$EDITOR` argv parsing.

### Changed

- Make the verified online installer the recommended install path while keeping
  inspect-before-run and Git-clone alternatives.
- Pin TerminalTextEffects 0.15.0 with hashes for reproducible installation.
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
  the data directory.
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

[Unreleased]: https://github.com/RobbyBobby77/kde-ascii-saver/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/RobbyBobby77/kde-ascii-saver/releases/tag/v0.1.0
