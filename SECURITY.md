# Security

## Supported versions

During the initial 0.x series, security fixes are applied to the latest code on
the default branch. Older releases may not receive fixes. Upgrade to the newest
published release before reporting a problem unless the regression itself is
version-specific.

## Report a vulnerability privately

Do not open a public issue. Use
[GitHub private vulnerability reporting](https://github.com/RobbyBobby77/kde-ascii-saver/security/advisories/new)
to submit a repository security advisory. If that mechanism is unavailable,
contact the project owner through their GitHub profile without publishing
exploit details.

Include:

- the affected commit or version;
- distribution, Plasma version, and Wayland/X11 session type;
- clear reproduction steps and potential impact;
- expected and observed behavior; and
- the smallest relevant user-service log excerpt, with private data removed.

Do not include passwords, authentication logs, private keys, tokens, private
artwork, or an unredacted environment dump. You should receive an initial
acknowledgment when a maintainer is available; this volunteer project cannot
promise a response or remediation deadline. Please allow time for a fix before
public disclosure.

## Security boundary

KDE ASCII Saver is decorative software. It does not authenticate the user and
must never be treated as a lock screen. KScreenLocker remains the security
boundary.

KDE ASCII Saver:

- does not modify `kscreenlockerrc`;
- does not change automatic lock or lock-on-resume settings;
- does not inhibit KScreenLocker or try to unlock the session;
- exits when KScreenLocker announces that locking is starting or active; and
- runs as the logged-in user without elevated privileges.

If the visual saver and KScreenLocker activate at nearly the same time,
KScreenLocker's session-lock surface must take precedence and block access to
the desktop. A failure of this handoff is security-relevant even though the
project is not itself a lock screen.

## Installation, network, and privacy

The user-local installer writes to the current user's XDG data and config
locations, `~/.local/bin`, and either the systemd user-unit or XDG autostart
directory. It does not request root access or change system lock settings.

The recommended bootstrap downloads a tagged release and checksum from GitHub
before running the bundled installer. The installer creates an isolated Python
environment and obtains the version-pinned, hash-verified runtime dependency
from PyPI.
Review `install-online.sh`, `install.sh`, and `requirements.txt` when evaluating
the supply-chain boundary. A checksum detects a damaged or mismatched archive;
the GitHub repository and its release assets remain trusted inputs.

The running application does not include telemetry, analytics, or a project
account service. Artwork and settings remain local unless the user shares or
backs them up through another service. Service logs may include local paths or
diagnostics, so redact them before posting publicly.
