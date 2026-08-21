# Changelog

All notable changes to this project will be documented here.

## [Unreleased]

### Added

- Dependency guidance for Fedora/RHEL, Debian/Ubuntu, Arch, openSUSE, and
  manually packaged distributions.
- Fedora and Debian native-watcher builds in CI.
- XDG session autostart when no systemd user manager is available.
- A single-instance watcher lock and PID-based lifecycle for autostart mode.

### Changed

- Resolve Python from `PATH` instead of assuming `/usr/bin/python3`.
- Report either systemd or XDG autostart integration in controller status.

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
