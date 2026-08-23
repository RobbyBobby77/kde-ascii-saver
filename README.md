# KDE ASCII Saver

[![CI](https://github.com/RobbyBobby77/kde-ascii-saver/actions/workflows/ci.yml/badge.svg)](https://github.com/RobbyBobby77/kde-ascii-saver/actions/workflows/ci.yml)
![Plasma 6](https://img.shields.io/badge/KDE_Plasma-6-1d99f3)
![Wayland and X11](https://img.shields.io/badge/display-Wayland_%7C_X11-6c63ff)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

An Omarchy-inspired animated ASCII idle screen for KDE Plasma 6. It displays
custom artwork with random
[TerminalTextEffects](https://github.com/ChrisBuilds/terminaltexteffects)
animations on every monitor, then disappears on the first keyboard or pointer
input.

```text
  ██████╗ ██╗      █████╗ ███████╗███╗   ███╗ █████╗
  ██╔══██╗██║     ██╔══██╗██╔════╝████╗ ████║██╔══██╗
  ██████╔╝██║     ███████║███████╗██╔████╔██║███████║
  ██╔═══╝ ██║     ██╔══██║╚════██║██║╚██╔╝██║██╔══██║
  ██║     ███████╗██║  ██║███████║██║ ╚═╝ ██║██║  ██║
  ╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝
```

> [!IMPORTANT]
> KDE ASCII Saver is decorative, not an authentication screen. KScreenLocker
> remains responsible for securing the session. This project does not change
> Plasma's lock delay, lock-on-resume behavior, or PowerDevil settings.

## Install

On a supported Plasma 6 system, run:

```sh
curl -fsSL https://raw.githubusercontent.com/RobbyBobby77/kde-ascii-saver/main/install-online.sh | bash
```

The bootstrap downloads the latest stable tagged release, verifies its SHA-256
checksum, and runs the bundled user-local installer. The installer never uses
`sudo`; if system packages are missing, it prints the command for you to review
and run.

If you prefer to inspect the bootstrap before running it:

```sh
curl -fsSLO https://raw.githubusercontent.com/RobbyBobby77/kde-ascii-saver/main/install-online.sh
less install-online.sh
bash install-online.sh
```

You can also [install from a Git clone](docs/INSTALLATION.md#install-from-a-git-clone).
See the [installation guide](docs/INSTALLATION.md) for supported systems,
dependencies, upgrades, and uninstall instructions.

## What it does

- Shows editable ASCII artwork with randomly selected TTE animations.
- Creates one fullscreen surface per monitor.
- Uses KWin Layer Shell on Plasma Wayland for panel coverage, with a normal
  fullscreen fallback on X11 or when Layer Shell is unavailable.
- Uses KDE Frameworks `KIdleTime` for native Plasma Wayland and X11 idle
  detection.
- Gets out of the way when KScreenLocker starts locking.
- Provides a preview, manual launch, and a command-line control utility.
- Preserves user configuration and artwork across upgrades and uninstall.

## Requirements and status

KDE ASCII Saver targets Linux distributions with KDE Plasma 6, Qt 6, KDE
Frameworks 6, GTK 4, and VTE 3.91. Fedora/RHEL, Debian/Ubuntu, Arch-family, and
openSUSE package commands are documented in the
[distribution guide](docs/DISTRIBUTIONS.md). GTK4 Layer Shell is recommended
on Wayland but is optional.

Version `0.1.0` is an initial preview. CI builds the watcher and validates the
renderer dependencies on Fedora and Debian. A complete, recorded acceptance
pass on real Plasma 6 Wayland and X11 hardware is still required before this
project should be described as stable; see the
[release checklist](docs/RELEASE_CHECKLIST.md). A public screenshot or short
recording must come from that real-session pass and has not been added yet.

## Use it

The installer places commands in `~/.local/bin`:

```sh
kde-ascii-saverctl start        # show the fullscreen saver now
kde-ascii-saverctl preview      # open a decorated preview window
kde-ascii-saverctl stop         # close it
kde-ascii-saverctl edit         # edit the ASCII artwork
kde-ascii-saverctl prefs        # open config.json
kde-ascii-saverctl delay 180    # set the idle delay in seconds
kde-ascii-saverctl disable      # pause automatic launch
kde-ascii-saverctl enable
kde-ascii-saverctl status
```

If the command is not found, add the user binary directory to your shell path:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

The default idle delay is 120 seconds. The watcher waits for the next real
input event before arming its first timeout, so installing or restarting it on
an already-idle desktop does not suddenly cover the screen.

## Customize it

Artwork and settings live under `~/.config/kde-ascii-saver/` by default:

```text
~/.config/kde-ascii-saver/logo.txt
~/.config/kde-ascii-saver/config.json
```

Example configuration:

```json
{
  "enabled": true,
  "idle_delay": 120,
  "font": "Monospace 18",
  "background": "#000000",
  "frame_rate": 60,
  "exclude_effects": ["bouncyballs", "overflow"]
}
```

The project honors `XDG_CONFIG_HOME` and `XDG_DATA_HOME`. Existing config and
artwork are not overwritten during an upgrade.

## Help and security

Start with:

```sh
kde-ascii-saverctl status
systemctl --user status kde-ascii-saver.service
journalctl --user -u kde-ascii-saver.service -b
```

Systems without a systemd user manager use an XDG session-autostart entry
instead. The [troubleshooting guide](docs/TROUBLESHOOTING.md) covers both paths.
For general help, see [Support](SUPPORT.md); report vulnerabilities privately
as described in [Security](SECURITY.md).

The application runs entirely as the logged-in user. It does not collect
telemetry, send artwork or settings to the project, or require an account after
installation. Installation fetches a release from GitHub and installs a
version-pinned, hash-verified TerminalTextEffects package from PyPI into an
isolated virtual environment.

## Project documentation

- [Installation and maintenance](docs/INSTALLATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Architecture and trust boundaries](docs/ARCHITECTURE.md)
- [Distribution support](docs/DISTRIBUTIONS.md)
- [Release and Plasma acceptance checklist](docs/RELEASE_CHECKLIST.md)
- [Contributing](CONTRIBUTING.md)

## Credits

- Inspired by [Omarchy](https://github.com/basecamp/omarchy)
- Animated by [TerminalTextEffects](https://github.com/ChrisBuilds/terminaltexteffects)
- Built on KDE Frameworks, GTK, VTE, and GTK4 Layer Shell

Released under the [MIT License](LICENSE).
