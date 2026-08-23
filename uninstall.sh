#!/usr/bin/env bash
set -euo pipefail

data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}
app_dir="$data_home/kde-ascii-saver"
bin_dir="$HOME/.local/bin"
manage_session=true
remove_complete=true

usage() {
    cat <<'EOF'
Usage: ./uninstall.sh [OPTIONS]

Remove KDE ASCII Saver for the current user. The configuration and custom ASCII
art in $XDG_CONFIG_HOME/kde-ascii-saver (normally ~/.config/kde-ascii-saver)
are always preserved.

Options:
  --no-stop           Do not contact the user service manager or running processes
  --non-interactive   Accepted for unattended removal (the script never prompts)
  -h, --help          Show this help

Set KDE_ASCII_SAVER_NO_SESSION=1 for the same behavior as --no-stop.
EOF
}

while (($#)); do
    case "$1" in
        --no-stop) manage_session=false ;;
        --non-interactive) ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'Unknown option: %s\n\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

case "${KDE_ASCII_SAVER_NO_SESSION:-0}" in
    1|true|TRUE|yes|YES) manage_session=false ;;
esac

stop_watcher_pid_file() {
    local pid_file=$1
    local watcher_pid=
    local watcher_exe=
    local expected_exe=
    if [[ -r "$pid_file" ]]; then
        read -r watcher_pid <"$pid_file" || watcher_pid=
        if [[ "$watcher_pid" =~ ^[0-9]+$ ]] && [[ -e "/proc/$watcher_pid/exe" ]] && \
            [[ -e "$app_dir/kde-ascii-saver-watcher" ]]; then
            watcher_exe=$(readlink -f -- "/proc/$watcher_pid/exe" 2>/dev/null || true)
            expected_exe=$(readlink -f -- "$app_dir/kde-ascii-saver-watcher" 2>/dev/null || true)
            if [[ -n "$watcher_exe" && "$watcher_exe" == "$expected_exe" ]]; then
                [[ $(readlink -f -- "/proc/$watcher_pid/exe" 2>/dev/null || true) == "$expected_exe" ]] && \
                    kill "$watcher_pid" 2>/dev/null || true
            fi
        fi
        rm -f -- "$pid_file"
    fi
}

has_user_systemd=false
if "$manage_session" && command -v systemctl >/dev/null && \
    systemctl --user show-environment >/dev/null 2>&1; then
    has_user_systemd=true
fi

if "$manage_session"; then
    "$bin_dir/kde-ascii-saverctl" stop >/dev/null 2>&1 || true
    if "$has_user_systemd"; then
        systemctl --user disable --now kde-ascii-saver.service >/dev/null 2>&1 || true
    fi
    if [[ -n "${XDG_RUNTIME_DIR:-}" ]]; then
        stop_watcher_pid_file "$XDG_RUNTIME_DIR/kde-ascii-saver-watcher-$(id -u).pid"
    fi
    stop_watcher_pid_file "/tmp/kde-ascii-saver-watcher-$(id -u).pid"
fi

# Only remove exact paths owned by this installer. User configuration is separate
# and deliberately untouched so a reinstall restores the user's settings and art.
if [[ -d "$app_dir" && ! -L "$app_dir" ]]; then
    rm -rf -- "$app_dir"
elif [[ -e "$app_dir" || -L "$app_dir" ]]; then
    printf 'Not removing unexpected application path: %s\n' "$app_dir" >&2
    remove_complete=false
fi
rm -f -- "$data_home/applications/io.github.kde_ascii_saver.KdeAsciiSaver.desktop" \
    "$bin_dir/kde-ascii-saver" "$bin_dir/kde-ascii-saverctl" \
    "$bin_dir/kde-ascii-saver-watcher" \
    "$config_home/systemd/user/kde-ascii-saver.service" \
    "$config_home/autostart/kde-ascii-saver-watcher.desktop"

update-desktop-database "$data_home/applications" 2>/dev/null || true
if "$manage_session" && "$has_user_systemd"; then
    systemctl --user daemon-reload
fi

printf 'KDE ASCII Saver removed. Your settings and art are preserved in %s/kde-ascii-saver\n' "$config_home"
if ! "$remove_complete"; then
    printf 'Some application files remain at %s; remove them only after inspecting that path.\n' "$app_dir" >&2
    exit 1
fi
