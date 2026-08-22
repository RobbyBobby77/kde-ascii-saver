#!/bin/sh
set -eu

distro_id=unknown
distro_like=
if [ -r /etc/os-release ]; then
    # OS-provided values; used only to select a printed package hint.
    . /etc/os-release
    distro_id=${ID:-unknown}
    distro_like=${ID_LIKE:-}
fi

case " $distro_id $distro_like " in
    *" fedora "*|*" rhel "*)
        cat <<'EOF'
Install dependencies with:
  sudo dnf install gcc-c++ cmake qt6-qtbase-devel kf6-kidletime-devel python3 python3-pip python3-devel python3-gobject gtk4 vte291-gtk4 gtk4-layer-shell desktop-file-utils
EOF
        ;;
    *" debian "*|*" ubuntu "*)
        cat <<'EOF'
Install dependencies with:
  sudo apt update
  sudo apt install build-essential cmake qt6-base-dev libkf6idletime-dev python3 python3-gi python3-venv gir1.2-gtk-4.0 gir1.2-vte-3.91 gir1.2-gtk4layershell-1.0 desktop-file-utils
EOF
        ;;
    *" arch "*)
        cat <<'EOF'
Install dependencies with:
  sudo pacman -S --needed base-devel cmake qt6-base kidletime python python-gobject gtk4 vte4 gtk4-layer-shell desktop-file-utils
EOF
        ;;
    *" opensuse "*|*" suse "*)
        cat <<'EOF'
Install dependencies with:
  sudo zypper install gcc-c++ cmake qt6-base-devel kf6-kidletime-devel python3 python3-gobject typelib-1_0-Gtk-4_0 typelib-1_0-Vte-3_91 desktop-file-utils
Optional Wayland panel coverage: install gtk4-layer-shell when available.
EOF
        ;;
    *)
        cat <<'EOF'
Install your distribution's packages for a C++17 compiler, CMake 3.20+, Qt 6
(Gui and D-Bus), KF6 KIdleTime, Python 3 (including venv/pip), PyGObject,
GTK 4, and GTK4 VTE (Vte 3.91). GTK4 Layer Shell is recommended on Wayland.
Then rerun ./install.sh.
EOF
        ;;
esac
