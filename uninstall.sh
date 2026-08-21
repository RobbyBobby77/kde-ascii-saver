#!/bin/bash
set -euo pipefail

data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}

"$HOME/.local/bin/kde-ascii-saverctl" stop >/dev/null 2>&1 || true
systemctl --user disable --now kde-ascii-saver.service >/dev/null 2>&1 || true

rm -r -- "$data_home/kde-ascii-saver" 2>/dev/null || true
rm -f -- "$data_home/applications/io.github.kde_ascii_saver.KdeAsciiSaver.desktop" \
    "$HOME/.local/bin/kde-ascii-saver" "$HOME/.local/bin/kde-ascii-saverctl" \
    "$HOME/.local/bin/kde-ascii-saver-watcher" \
    "$config_home/systemd/user/kde-ascii-saver.service"
systemctl --user daemon-reload

printf 'KDE ASCII Saver removed. Your art is preserved in %s/kde-ascii-saver\n' "$config_home"
