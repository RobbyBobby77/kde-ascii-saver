# Security

## Supported versions

Security fixes are applied to the latest code on the default branch while the
project is in its initial 0.x series.

## Security model

KDE ASCII Saver is decorative software. It does not authenticate the user and
must never be treated as a lock screen.

KScreenLocker remains the only security boundary. KDE ASCII Saver:

- does not modify `kscreenlockerrc`;
- does not change automatic lock or lock-on-resume settings;
- does not call the KScreenLocker `Inhibit` method;
- does not call `SetActive(false)` or attempt to unlock the session;
- exits when KScreenLocker announces `AboutToLock` or becomes active; and
- runs entirely as the logged-in user without elevated privileges.

Installation writes only to the current user's XDG data and config locations,
`~/.local/bin`, and the systemd user-unit directory. The only downloaded
runtime dependency is installed into the application's isolated Python
environment from the package index.

If the visual saver and KScreenLocker activate at nearly the same time,
KScreenLocker's session-lock surface takes precedence and blocks access to the
desktop.

## Reporting a vulnerability

Keep the repository private while reporting a suspected vulnerability. Open a
private repository security advisory on GitHub and include:

- affected commit or version;
- Plasma version and Wayland/X11 session type;
- reproduction steps;
- expected and observed behavior; and
- relevant user-service logs with secrets removed.

Do not include passwords, authentication logs, private keys, tokens, or an
unredacted environment dump.
