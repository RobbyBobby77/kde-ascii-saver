# Release and acceptance checklist

This checklist separates automated confidence from behavior that must be
observed in a real Plasma session. A release owner should record the tested
distribution, Plasma version, session type, monitor arrangement, and results
in the release pull request or issue.

The current preview results are recorded in
[Version 0.1.0 acceptance](ACCEPTANCE-0.1.0.md).

## Repository and documentation

- [ ] `VERSION`, changelog heading, tag, and release title agree.
- [ ] The working tree is clean and the release commit is on the default branch.
- [ ] CI passes on every supported build image.
- [ ] README install commands work from a clean account.
- [ ] Documentation links and GitHub issue forms render correctly.
- [ ] Dependency commands match currently supported distribution releases.
- [ ] Release notes identify breaking configuration or dependency changes.
- [ ] No secrets, private URLs, generated build trees, or user config are present.

## Automated validation

- [ ] Python compilation and unit tests pass.
- [ ] Shell syntax, JSON, and desktop entries validate.
- [ ] The native watcher builds with release flags and warnings enabled.
- [ ] GTK 4, VTE 3.91, and GTK4 Layer Shell imports pass in CI.
- [ ] Versioned and generic release archives and matching `.sha256` files are
      produced from the tagged commit.
- [ ] The online bootstrap rejects a deliberately incorrect checksum.
- [ ] Clean-container install, upgrade, and uninstall tests pass.
- [ ] Release artifacts contain the expected source and no unexpected files.

## Plasma 6 Wayland acceptance

- [ ] Install in a clean user account and provide the first input to arm it.
- [ ] Manual fullscreen launch and decorated preview both work.
- [ ] Idle timeout launches once and input dismisses every surface.
- [ ] Keyboard, pointer motion, click, and scroll each dismiss the saver.
- [ ] KScreenLocker manual shortcut removes the saver before authentication.
- [ ] Automatic KScreenLocker activation removes the saver.
- [ ] Lock cancellation does not permanently suppress the next idle launch.
- [ ] One monitor works with GTK4 Layer Shell installed.
- [ ] Multiple monitors receive one correctly placed surface each.
- [ ] Mixed scale factors render correctly when hardware is available.
- [ ] Monitor hotplug adds and removes surfaces without leaving an overlay.
- [ ] Panels are covered with GTK4 Layer Shell and fallback behavior is clear
      without it.
- [ ] Restarting the watcher while already idle does not launch immediately.

## Plasma 6 X11 acceptance

- [ ] Repeat manual launch, preview, idle launch, and all dismissal inputs.
- [ ] Repeat manual and automatic KScreenLocker handoff tests.
- [ ] Test one and multiple monitors using the fullscreen fallback.
- [ ] Test monitor hotplug when hardware is available.
- [ ] Restarting the watcher while already idle does not launch immediately.

## Lifecycle and preservation

- [ ] Test the systemd user-service install path.
- [ ] Test the XDG session-autostart fallback on a non-systemd user session.
- [ ] Reinstalling and upgrading do not create duplicate watchers.
- [ ] `disable`, `enable`, `delay`, `edit`, and `prefs` behave as documented.
- [ ] Upgrade preserves modified `config.json` and `logo.txt`.
- [ ] Uninstall stops running processes and removes installed program files.
- [ ] Uninstall preserves modified `config.json` and `logo.txt`.
- [ ] Reinstall after uninstall reuses the preserved configuration.

## Public release

- [ ] Real Plasma results and any untested combinations are stated in the notes.
- [ ] The tag is signed or otherwise traceable to the reviewed release commit.
- [ ] GitHub release archives and their `.sha256` files are published together.
- [ ] The public install command downloads and verifies the published artifact.
- [ ] The release is installed once from the public command after publication.
- [ ] Capture public screenshot or recording media from real Plasma testing;
      this media is still required and no placeholder should be advertised.
- [ ] Inspect release media for private artwork, usernames, notifications, and
      other personal information before publishing it.
