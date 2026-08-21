# Contributing

## Development setup

On Fedora:

```sh
sudo dnf install gcc-c++ cmake qt6-qtbase-devel kf6-kidletime-devel \
  python3-gobject gtk4 vte291-gtk4 gtk4-layer-shell desktop-file-utils
```

Build the native watcher out of tree:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel
```

Preview the renderer after installing the project dependencies:

```sh
kde-ascii-saverctl preview
```

## Before submitting a change

```sh
python3 -m py_compile app.py ctl.py
bash -n install.sh uninstall.sh bin/kde-ascii-saver \
  bin/kde-ascii-saverctl bin/kde-ascii-saver-watcher
python3 -m json.tool config/config.json >/dev/null
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
```

Do not commit `build/`, virtual environments, generated Python caches, or user
configuration.

## Plasma acceptance matrix

Changes affecting windows, idle behavior, or locking should be tested on a real
Plasma 6 session with:

- Wayland and X11;
- one and multiple monitors;
- mixed scale factors when available;
- pointer motion, click, scroll, and keyboard dismissal;
- manual and idle-triggered launch;
- automatic and manual KScreenLocker activation;
- monitor hotplug while running;
- service restart while the desktop is already idle; and
- install, upgrade, disable/enable, and uninstall flows.

Never weaken or replace KScreenLocker as part of a visual feature.
