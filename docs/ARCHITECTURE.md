# Architecture

KDE ASCII Saver separates visual rendering, idle detection, and secure locking.
This keeps animation code outside the compositor and leaves authentication
entirely under KScreenLocker control.

## Components

### `kde-ascii-saver-watcher`

`watcher.cpp` builds a small Qt 6 process linked to `KF6::IdleTime`.

- `KIdleTime::addIdleTimeout()` starts the configured idle countdown.
- `timeoutReached()` launches the renderer.
- `catchNextResumeEvent()` and `resumingFromIdle()` stop it on the first input.
- `org.kde.screensaver.AboutToLock` stops the renderer before lock begins.
- `org.freedesktop.ScreenSaver.ActiveChanged(true)` provides a second lock-state
  guard.
- `GetActive()` prevents launch while the session is already locked.

The watcher is a `QGuiApplication`, not a `QCoreApplication`, because the
KIdleTime Wayland backend needs access to the active Wayland seat.

A `QLockFile` in the XDG runtime directory enforces a single watcher process.
The watcher also records a validated PID so the controller and non-systemd
uninstaller can stop an XDG-autostarted process cleanly.

On Wayland, KIdleTime uses `ext-idle-notify-v1` with the legacy KWin idle
protocol as a fallback. It cannot poll current idle duration, so the watcher
waits for one genuine resume event after startup before registering its first
timeout. This avoids an immediate launch when the service is restarted on an
already-idle desktop.

### Renderer

`app.py` creates one GTK 4/VTE window for every GDK monitor and launches one TTE
process per terminal. Completed effects restart automatically with a new random
effect.

On supported Wayland compositors, GTK4 Layer Shell places each window on the
overlay layer and anchors it to all four output edges. The primary surface asks
for exclusive keyboard input so the first key can dismiss the animation; other
surfaces do not compete for keyboard focus. KIdleTime resume events remain the
authoritative dismissal mechanism.

On X11, or when GTK4 Layer Shell is unavailable, the renderer requests a normal
borderless fullscreen window on each monitor.

### Control utility

`ctl.py` manages manual launch, status, artwork editing, the delay, automatic
activation, and removal. It writes configuration atomically to avoid leaving a
partial JSON document.

### Session integration

When a systemd user manager is available, `kde-ascii-saver.service` is tied to
`plasma-workspace.target` and ordered after `plasma-core.target`. It stops with
the Plasma workspace. On non-systemd distributions, the installer creates an
`OnlyShowIn=KDE` XDG autostart entry instead and starts the same watcher binary.
The single-instance lock makes upgrades and repeated session startup safe.

## Data flow

```text
keyboard/pointer idle
        │
        ▼
KWin idle protocol → KF6 KIdleTime watcher → GTK/VTE renderer → TTE process
        │                       │                    │
        └─ resume ──────────────┴──── terminate ────┘

KScreenLocker AboutToLock/ActiveChanged ────────────┘
```

## Filesystem layout after installation

```text
~/.local/bin/kde-ascii-saver
~/.local/bin/kde-ascii-saverctl
~/.local/bin/kde-ascii-saver-watcher
~/.local/share/kde-ascii-saver/
~/.local/share/applications/io.github.kde_ascii_saver.KdeAsciiSaver.desktop
~/.config/kde-ascii-saver/config.json
~/.config/kde-ascii-saver/logo.txt
~/.config/systemd/user/kde-ascii-saver.service        # systemd path
~/.config/autostart/kde-ascii-saver-watcher.desktop  # non-systemd path
```

The project honors `XDG_CONFIG_HOME` and `XDG_DATA_HOME` for configuration and
application data. Launch wrappers remain under `~/.local/bin`.

See [Distribution support](DISTRIBUTIONS.md) for package names and validation
levels across Linux families.
