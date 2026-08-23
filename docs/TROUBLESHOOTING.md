# Troubleshooting

## Collect status first

Run these commands in a terminal inside the affected Plasma session:

```sh
kde-ascii-saverctl --version
kde-ascii-saverctl status
printf 'session=%s runtime=%s\n' "${XDG_SESSION_TYPE:-unset}" "${XDG_RUNTIME_DIR:-unset}"
```

Do not post a full environment dump. It can contain tokens and private paths.

## The command is not found

The launchers are installed in `~/.local/bin`. Start a new login session, or
add this directory to the current shell:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

You can also invoke the controller directly as
`$HOME/.local/bin/kde-ascii-saverctl`.

## The watcher is inactive

When `kde-ascii-saverctl status` reports a systemd user service, inspect it:

```sh
systemctl --user status kde-ascii-saver.service
journalctl --user -u kde-ascii-saver.service -b
systemctl --user restart kde-ascii-saver.service
```

After a restart, provide one keyboard or pointer event before waiting for the
idle delay. The watcher deliberately does not arm on an already-idle desktop.

On a system without a systemd user manager, status should report XDG session
autostart. Confirm that this file exists:

```sh
ls "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/kde-ascii-saver-watcher.desktop"
```

Log out and back in after repairing a missing autostart entry by rerunning the
installer. For a foreground diagnostic, run:

```sh
kde-ascii-saver-watcher
```

Press `Ctrl+C` when finished. A missing `XDG_RUNTIME_DIR` usually means the
command was run outside a normal graphical login session.

## The preview or saver does not open

Try the renderer independently of idle detection:

```sh
kde-ascii-saverctl preview
```

If that fails silently, run the launcher in the foreground to see diagnostics:

```sh
kde-ascii-saver --windowed
```

Typical causes are missing GTK 4/VTE introspection bindings, a broken Python
virtual environment, or running outside a graphical session. The renderer also
refuses to display if it cannot monitor KScreenLocker's state on the session
bus. Rerun the dependency helper from a source checkout and then reinstall:

```sh
./scripts/dependency-hint.sh
./install.sh
```

## Wayland panels remain visible

GTK4 Layer Shell is optional. Without its introspection bindings, the saver
uses an ordinary fullscreen window and a compositor panel may remain above it.
Install the distribution's GTK4 Layer Shell package and rerun the installer.
See [Distribution support](DISTRIBUTIONS.md).

## Configuration warnings or unexpected defaults

The application ignores invalid values and emits a warning instead of passing
unsafe arguments to the renderer. Validate the JSON syntax:

```sh
python3 -m json.tool "${XDG_CONFIG_HOME:-$HOME/.config}/kde-ascii-saver/config.json"
```

The accepted idle delay is 10 through 86400 seconds. `frame_rate` must be an
integer from 1 through 240, colors must use `#RRGGBB`, `enabled` must be a JSON
boolean, and `exclude_effects` must be a list of effect names. Preserve a copy
before editing by hand.

## KScreenLocker behavior

KDE ASCII Saver must disappear when KScreenLocker begins locking, but it does
not control whether or when Plasma locks. Check lock timing in Plasma's Screen
Locking settings. If the decorative saver remains visible over a locked session
or appears to interfere with authentication, stop it, retain the relevant
service logs, and follow the private reporting instructions in
[Security](../SECURITY.md).

## Ask for help

Search existing issues, then use the bug-report template. Include the project
version, distribution, Plasma version, Wayland/X11 session type, monitor setup,
reproduction steps, and the smallest relevant log excerpt. Redact usernames,
hostnames, artwork, tokens, and other private data. See [Support](../SUPPORT.md).
