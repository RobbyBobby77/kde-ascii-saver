# Distribution support

KDE ASCII Saver does not use Fedora-specific runtime APIs. Its native watcher
needs Plasma 6, a C++17 compiler, CMake 3.20 or newer, Qt 6 Gui and D-Bus,
KF6 KIdleTime, Python 3, PyGObject, GTK 4, and the GTK4 build of VTE
(`Vte 3.91`). GTK4 Layer Shell is recommended for complete panel coverage on
Plasma Wayland but is not required; ordinary fullscreen windows are the
fallback.

The installer never runs `sudo` or invokes a system package manager. Run the
matching command yourself, review the packages, and then run `./install.sh`.
`./scripts/dependency-hint.sh` prints the appropriate known command based on
`/etc/os-release`.

## Known package commands

### Fedora and RPM-family Plasma desktops

```sh
sudo dnf install gcc-c++ cmake qt6-qtbase-devel kf6-kidletime-devel \
  python3 python3-gobject gtk4 vte291-gtk4 gtk4-layer-shell \
  desktop-file-utils
```

### Debian 13 and compatible Ubuntu releases

```sh
sudo apt update
sudo apt install build-essential cmake qt6-base-dev libkf6idletime-dev python3 \
  python3-gi python3-venv gir1.2-gtk-4.0 gir1.2-vte-3.91 \
  gir1.2-gtk4layershell-1.0 desktop-file-utils
```

Older Debian/Ubuntu releases that ship only KF5 cannot build this Plasma 6
watcher. Use a release with `libkf6idletime-dev` rather than mixing KDE
Frameworks repositories across distribution releases.

### Arch, EndeavourOS, and Manjaro

```sh
sudo pacman -S --needed base-devel cmake qt6-base kidletime python \
  python-gobject gtk4 vte4 gtk4-layer-shell desktop-file-utils
```

### openSUSE Tumbleweed

```sh
sudo zypper install gcc-c++ cmake qt6-base-devel kf6-kidletime-devel \
  python3 python3-gobject typelib-1_0-Gtk-4_0 \
  typelib-1_0-Vte-3_91 desktop-file-utils
```

Install `gtk4-layer-shell` too when it is available from the configured
openSUSE repositories. Without it, the renderer uses normal fullscreen mode.

## Other distributions

Map these capabilities to the native package manager:

- a C++17 compiler and CMake 3.20+;
- Qt 6 Gui and D-Bus development files;
- KDE Frameworks 6 KIdleTime development files;
- `python3` with `venv` and `pip` support;
- the `gi` Python module with `Gtk 4.0` and `Vte 3.91`; and
- GTK4 Layer Shell introspection bindings when available.

Then run:

```sh
./install.sh
kde-ascii-saverctl status
kde-ascii-saverctl preview
```

NixOS and other declarative/read-only systems should provide these dependencies
through their native development environment or package definition before
running the user-level installer.

## Init systems

If `systemctl --user` is usable, the installer enables the Plasma-scoped user
service. Otherwise it installs an XDG autostart entry under
`$XDG_CONFIG_HOME/autostart` and launches the watcher for the current session.
Both routes execute the same binary and preserve the same KIdleTime and
KScreenLocker behavior.

## Validation levels

- Fedora 44 and Debian 13 continuously compile the Qt/KF6 watcher and validate
  the renderer's introspection dependencies.
- The GTK/VTE/TTE renderer has live smoke coverage on Fedora GNOME Wayland.
- A real Plasma 6 Wayland/X11 acceptance pass remains required before a stable
  release, regardless of distribution.
