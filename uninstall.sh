#!/bin/bash
set -euo pipefail

data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}

stop_watcher_pid_file() {
    local pid_file=$1
    if [[ -r "$pid_file" ]]; then
        read -r watcher_pid <"$pid_file" || watcher_pid=
        if [[ "$watcher_pid" =~ ^[0-9]+$ ]] && \
            [[ -r "/proc/$watcher_pid/cmdline" ]] && \
            grep -aq 'kde-ascii-saver-watcher' "/proc/$watcher_pid/cmdline"; then
            kill "$watcher_pid" 2>/dev/null || true
        fi
        rm -f -- "$pid_file"
    fi
}

"$HOME/.local/bin/kde-ascii-saverctl" stop >/dev/null 2>&1 || true
if command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1; then
    systemctl --user disable --now kde-ascii-saver.service >/dev/null 2>&1 || true
fi
if [[ -n "${XDG_RUNTIME_DIR:-}" ]]; then
    stop_watcher_pid_file "$XDG_RUNTIME_DIR/kde-ascii-saver-watcher-$(id -u).pid"
fi
stop_watcher_pid_file "/tmp/kde-ascii-saver-watcher-$(id -u).pid"

rm -r -- "$data_home/kde-ascii-saver" 2>/dev/null || true
rm -f -- "$data_home/applications/io.github.kde_ascii_saver.KdeAsciiSaver.desktop" \
    "$HOME/.local/bin/kde-ascii-saver" "$HOME/.local/bin/kde-ascii-saverctl" \
    "$HOME/.local/bin/kde-ascii-saver-watcher" \
    "$config_home/systemd/user/kde-ascii-saver.service" \
    "$config_home/autostart/kde-ascii-saver-watcher.desktop"
if command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1; then
    systemctl --user daemon-reload
fi

printf 'KDE ASCII Saver removed. Your art is preserved in %s/kde-ascii-saver\n' "$config_home"
