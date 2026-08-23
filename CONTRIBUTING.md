# Contributing

Thanks for helping improve KDE ASCII Saver. Bug reports, focused feature
proposals, documentation fixes, tests, and code changes are welcome.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
For usage help, read [Support](SUPPORT.md). Report security issues privately as
described in [Security](SECURITY.md).

## Start with an issue

Search existing issues before opening a new one. For a substantial change,
open an issue before investing heavily so the scope and security implications
can be discussed. Small documentation and test fixes can go directly to a pull
request.

KDE ASCII Saver is a visual idle screen and must not weaken, inhibit, replace,
or reconfigure KScreenLocker. A proposal that changes this boundary needs an
explicit security discussion.

## Development setup

Fork and clone the repository, then create a focused branch:

```sh
git clone https://github.com/YOUR-USER/kde-ascii-saver.git
cd kde-ascii-saver
git switch -c fix/short-description
```

Ask the dependency helper for the current distribution's package command:

```sh
./scripts/dependency-hint.sh
```

Install those packages after reviewing the command. Build the native watcher
out of tree:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel
```

Install into your user account when an end-to-end test is needed:

```sh
./install.sh
kde-ascii-saverctl preview
```

The installer preserves existing files in `~/.config/kde-ascii-saver/`. Back
them up before deliberately testing config migrations or destructive edge cases.

## Validate a change

Run the checks relevant to the change; before opening a code pull request, run
the full local set:

```sh
python3 -m py_compile app.py ctl.py helpers.py
python3 -m unittest discover -s tests -t . -v
bash -n install.sh install-online.sh uninstall.sh bin/kde-ascii-saver \
  bin/kde-ascii-saverctl bin/kde-ascii-saver-watcher \
  scripts/dependency-hint.sh
python3 -m json.tool config/config.json >/dev/null
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
```

Changes to windows, input, idle behavior, locking, or session lifecycle also
need the relevant real-session cases from the
[Plasma acceptance checklist](docs/RELEASE_CHECKLIST.md). State exactly what
you tested and identify unavailable hardware or session types; do not mark an
untested case as passing.

Do not commit `build/`, virtual environments, Python caches, downloaded release
archives, or user configuration.

## Pull requests

Keep each pull request focused and explain the user-visible result. Include:

- the problem and chosen approach;
- linked issues;
- automated commands run and their results;
- Plasma version, Wayland/X11, and monitor setup for manual tests; and
- screenshots or recordings only when they help verify a visual change.

Use real project output for media and remove personal information before
uploading it. Maintainers may ask for tests, documentation, or a smaller scope.
Contributions are accepted under the repository's [MIT License](LICENSE).
