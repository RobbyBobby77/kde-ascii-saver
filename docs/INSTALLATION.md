# Installation and maintenance

## Before installing

KDE ASCII Saver is intended for a Linux desktop running KDE Plasma 6. It needs
a C++17 compiler, CMake 3.20 or newer, Qt 6, KDE Frameworks 6 KIdleTime,
Python 3 with virtual-environment support, PyGObject, GTK 4, and GTK4 VTE
(`Vte 3.91`). GTK4 Layer Shell is optional but recommended for full panel
coverage on Plasma Wayland.

The online bootstrap itself requires Bash, `curl`, Python 3, and either
`sha256sum` or `shasum`.

The installer is user-local. It does not invoke `sudo` or a system package
manager. See [Distribution support](DISTRIBUTIONS.md) for exact package names.

## Recommended online install

```sh
curl -fsSL https://raw.githubusercontent.com/RobbyBobby77/kde-ascii-saver/main/install-online.sh | bash
```

The bootstrap obtains the latest stable tagged release archive and its
published SHA-256 checksum, verifies the archive, extracts it to a temporary
directory, and runs the included installer. Installation stops on a missing or
mismatched checksum. The checksum detects a damaged or mismatched archive; the
GitHub repository and its release assets remain part of the trust boundary.

Piping a network response to a shell is convenient but requires trusting that
URL at execution time. To review exactly what will run first:

```sh
curl -fsSLO https://raw.githubusercontent.com/RobbyBobby77/kde-ascii-saver/main/install-online.sh
less install-online.sh
bash install-online.sh
```

To install or roll back to a specific published release with the reviewed
bootstrap:

```sh
KDE_ASCII_SAVER_VERSION=v0.1.0 bash install-online.sh
```

The bootstrap also accepts `--version v0.1.0`. Run
`bash install-online.sh --help` for non-interactive and no-start options.

## Install from a Git clone

This route is useful for development or for reviewing the complete source:

```sh
git clone https://github.com/RobbyBobby77/kde-ascii-saver.git
cd kde-ascii-saver
./scripts/dependency-hint.sh
./install.sh
```

The dependency helper only prints a package-manager command. Run that command
yourself if dependencies are missing, then rerun `./install.sh`.

To validate the required commands and GTK/VTE bindings without installing:

```sh
./install.sh --check
```

## Installed files

By default, installation creates:

```text
~/.local/bin/kde-ascii-saver
~/.local/bin/kde-ascii-saverctl
~/.local/bin/kde-ascii-saver-watcher
~/.local/share/kde-ascii-saver/
~/.local/share/applications/io.github.kde_ascii_saver.KdeAsciiSaver.desktop
~/.config/kde-ascii-saver/config.json
~/.config/kde-ascii-saver/logo.txt
~/.config/systemd/user/kde-ascii-saver.service
```

On systems without a working systemd user manager, the last file is replaced
by `~/.config/autostart/kde-ascii-saver-watcher.desktop`. `XDG_CONFIG_HOME` and
`XDG_DATA_HOME` override the corresponding config and data roots. Command
wrappers remain in `~/.local/bin`.

The application virtual environment lives inside the data directory. Python
packages are not installed globally.

## Verify the installation

Provide a real keyboard or pointer event once after installation, then check:

```sh
kde-ascii-saverctl status
kde-ascii-saverctl preview
```

The first input is intentional: it arms the watcher without immediately
showing the saver when installation occurs on an already-idle session.

## Upgrade

Rerun the recommended online install command to install the current stable
release. The installer replaces application files and refreshes the idle
integration, but preserves:

```text
~/.config/kde-ascii-saver/config.json
~/.config/kde-ascii-saver/logo.txt
```

Application files are staged before replacement. If the replacement cannot
complete, the installer restores the previous application files and service
state.

For a Git clone, update the checkout and rerun the installer:

```sh
git pull --ff-only
./install.sh
```

Review release notes before upgrading. To return to an older release, use the
specific-version command above or download that release's source archive and
checksum from GitHub, verify it, and run its included `install.sh`. Back up the
config directory first when moving backward, because older releases may not
understand newer settings.

## Uninstall

From any directory after installation:

```sh
kde-ascii-saverctl uninstall
```

Or, from a source checkout:

```sh
./uninstall.sh
```

Both methods remove the application, launchers, and idle integration while
preserving the configuration and artwork directory. Remove that directory
manually only if you no longer want the settings or artwork:

```sh
rm -r -- "${XDG_CONFIG_HOME:-$HOME/.config}/kde-ascii-saver"
```

That last command is irreversible unless the directory is backed up.

## Offline installation

Download a release archive and its checksum on a connected computer, verify
the checksum there, and transfer both the verified archive and checksum to the
Plasma system. Extract the archive and run `./install.sh`. System dependencies
and the Python package listed in `requirements.txt` must already be available;
the normal installer may otherwise need network access to populate its isolated
virtual environment.
