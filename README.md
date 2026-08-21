# KDE ASCII Saver

[![CI](https://github.com/RobbyBobby77/kde-ascii-saver/actions/workflows/ci.yml/badge.svg)](https://github.com/RobbyBobby77/kde-ascii-saver/actions/workflows/ci.yml)
![Plasma 6](https://img.shields.io/badge/KDE_Plasma-6-1d99f3)
![Wayland and X11](https://img.shields.io/badge/display-Wayland_%7C_X11-6c63ff)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

An Omarchy-inspired animated ASCII screensaver for KDE Plasma 6. It renders
custom artwork through random
[TerminalTextEffects](https://github.com/ChrisBuilds/terminaltexteffects)
animations across every monitor and disappears on the first keyboard, pointer,
click, or scroll event.

```text
  ██████╗ ██╗      █████╗ ███████╗███╗   ███╗ █████╗
  ██╔══██╗██║     ██╔══██╗██╔════╝████╗ ████║██╔══██╗
  ██████╔╝██║     ███████║███████╗██╔████╔██║███████║
  ██╔═══╝ ██║     ██╔══██║╚════██║██║╚██╔╝██║██╔══██║
  ██║     ███████╗██║  ██║███████║██║ ╚═╝ ██║██║  ██║
  ╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝
```

> [!IMPORTANT]
> KDE ASCII Saver is a visual idle screen, not an authentication screen.
> KScreenLocker remains responsible for security. The project never changes
> Plasma's lock delay, lock-on-resume behavior, or PowerDevil settings.

## Features

- Random TTE animations with editable ASCII artwork
- One fullscreen surface per monitor
- KWin Layer Shell overlays on Plasma Wayland, including panel coverage
- Borderless fullscreen fallback for X11 or unavailable Layer Shell support
- Native KDE Frameworks `KIdleTime` idle and resume detection
- Immediate handoff when KScreenLocker begins locking
- Manual launcher and a complete `kde-ascii-saverctl` command-line interface
- Upgrade-safe user configuration and a clean uninstaller

## Status

Version `0.1.0` is an initial preview. The native watcher is continuously built
on Fedora and Debian with Qt 6 and KF6 KIdleTime, and the renderer has passed
GTK, VTE, and TerminalTextEffects smoke tests. Final acceptance testing on a
real Plasma 6 Wayland session—especially mixed-DPI multi-monitor setups—is
still on the roadmap.

## Quick start on Linux

Ask the project for the correct dependency command for the current distro:

```sh
./scripts/dependency-hint.sh
```

Install those packages, then clone and install:

```sh
git clone https://github.com/RobbyBobby77/kde-ascii-saver.git
cd kde-ascii-saver
./install.sh
```

Because the repository is currently private, cloning requires a GitHub account
with access. The installer builds the small native watcher, creates an isolated
Python environment, registers the application, and enables either a Plasma
systemd user service or a portable XDG session-autostart entry. Existing
artwork and configuration survive upgrades.

The watcher waits for the next real input event before arming its first timeout.
This prevents installation or a watcher restart from suddenly covering an
already-idle desktop. A runtime lock also prevents duplicate watcher processes.

## Usage

```sh
kde-ascii-saverctl start        # start fullscreen now
kde-ascii-saverctl preview      # open a decorated preview window
kde-ascii-saverctl stop         # close it
kde-ascii-saverctl edit         # edit the ASCII art
kde-ascii-saverctl prefs        # open config.json
kde-ascii-saverctl delay 180    # set the idle delay in seconds
kde-ascii-saverctl disable      # pause automatic launch
kde-ascii-saverctl enable
kde-ascii-saverctl status
```

The default idle delay is 120 seconds. Plasma's normal lock shortcut and
automatic KScreenLocker behavior remain unchanged.

## Customization

Artwork is stored in:

```text
~/.config/kde-ascii-saver/logo.txt
```

Visual and idle settings are stored in:

```text
~/.config/kde-ascii-saver/config.json
```

Example:

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

## Install on another computer

The simplest route is Git. For an offline transfer, create an archive:

```sh
cd ~/Documents
tar -czf ~/kde-ascii-saver.tar.gz kde-ascii-saver
```

Move the archive by USB, cloud storage, or `scp`, then run on the Plasma system:

```sh
tar -xzf kde-ascii-saver.tar.gz
cd kde-ascii-saver
./install.sh
```

Run `./scripts/dependency-hint.sh` first on a new machine. It recognizes
Fedora/RHEL, Debian/Ubuntu, Arch-family, and openSUSE systems. For other package
managers, see the [distribution guide](docs/DISTRIBUTIONS.md).

To migrate custom artwork and settings, also copy
`~/.config/kde-ascii-saver/` to the same location on the destination computer.

## Architecture and security

The renderer uses GTK 4, VTE, and GTK4 Layer Shell. A small Qt 6 helper uses
KDE Frameworks `KIdleTime`, which is required because KScreenLocker's D-Bus
idle-time query is unsupported on Plasma Wayland. The watcher listens for both
`AboutToLock` and `ActiveChanged`, removing all visual surfaces before the
secure lock screen takes over.

See [Architecture](docs/ARCHITECTURE.md),
[Distributions](docs/DISTRIBUTIONS.md), and [Security](SECURITY.md) for the
full design, package mappings, and trust boundary.

## Development

See [Contributing](CONTRIBUTING.md) for build commands and the Plasma test
matrix. CI compiles the KF6 watcher and validates the Python, shell, JSON,
desktop-entry, and GObject-introspection surfaces on Fedora and Debian.

## Uninstall

```sh
./uninstall.sh
```

The uninstaller deliberately preserves `~/.config/kde-ascii-saver/`.

## Credits

- Inspired by [Omarchy](https://github.com/basecamp/omarchy)
- Animated by [TerminalTextEffects](https://github.com/ChrisBuilds/terminaltexteffects)
- Built on KDE Frameworks, GTK, VTE, and GTK4 Layer Shell

Released under the [MIT License](LICENSE).
