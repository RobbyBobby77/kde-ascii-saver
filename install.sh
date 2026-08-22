#!/bin/bash
set -euo pipefail

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}
app_dir="$data_home/kde-ascii-saver"
bin_dir="$HOME/.local/bin"
systemd_dir="$config_home/systemd/user"
autostart_dir="$config_home/autostart"
has_user_systemd=false

show_dependency_help() {
    "$source_dir/scripts/dependency-hint.sh" >&2
}

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

stop_existing_watcher() {
    if [[ -n "${XDG_RUNTIME_DIR:-}" ]]; then
        stop_watcher_pid_file "$XDG_RUNTIME_DIR/kde-ascii-saver-watcher-$(id -u).pid"
    fi
    # Older releases fell back to /tmp; reap a leftover PID file on upgrade.
    stop_watcher_pid_file "/tmp/kde-ascii-saver-watcher-$(id -u).pid"
}

for command in python3 cmake; do
    if ! command -v "$command" >/dev/null; then
        printf 'Missing required command: %s\n' "$command" >&2
        show_dependency_help
        exit 1
    fi
done

if ! python3 - <<'PY'
import gi
for namespace, version in (("Gtk", "4.0"), ("Vte", "3.91")):
    gi.require_version(namespace, version)
try:
    gi.require_version("Gtk4LayerShell", "1.0")
except ValueError:
    print("Warning: gtk4-layer-shell is unavailable; regular fullscreen windows will be used.")
PY
then
    printf 'Missing required Python GTK 4 or VTE 3.91 bindings.\n' >&2
    show_dependency_help
    exit 1
fi

if command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1; then
    has_user_systemd=true
fi

mkdir -p "$app_dir" "$bin_dir" "$config_home/kde-ascii-saver" \
    "$data_home/applications"
if "$has_user_systemd"; then
    mkdir -p "$systemd_dir"
else
    mkdir -p "$autostart_dir"
fi

build_dir=$(mktemp -d "${TMPDIR:-/tmp}/kde-ascii-saver-build.XXXXXX")
cleanup_build() {
    rm -rf -- "$build_dir"
}
trap cleanup_build EXIT

if ! cmake -S "$source_dir" -B "$build_dir" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$app_dir" \
    -DCMAKE_INSTALL_BINDIR=.; then
    printf 'Unable to configure the Qt 6/KF6 watcher build.\n' >&2
    show_dependency_help
    exit 1
fi
if ! cmake --build "$build_dir" --parallel; then
    printf 'Unable to build the Qt 6/KF6 watcher.\n' >&2
    exit 1
fi
if ! cmake --install "$build_dir"; then
    printf 'Unable to install the Qt 6/KF6 watcher.\n' >&2
    exit 1
fi
rm -rf -- "$app_dir/build"

if [[ ! -x "$app_dir/venv/bin/python" ]]; then
    if ! python3 -m venv --system-site-packages "$app_dir/venv"; then
        printf 'Unable to create a Python virtual environment.\n' >&2
        show_dependency_help
        exit 1
    fi
fi
if ! "$app_dir/venv/bin/python" -m pip install --quiet --disable-pip-version-check \
    -r "$source_dir/requirements.txt"; then
    printf 'Unable to install TerminalTextEffects. Check network access and Python packaging support.\n' >&2
    exit 1
fi

if "$has_user_systemd"; then
    systemctl --user stop kde-ascii-saver.service 2>/dev/null || true
fi
stop_existing_watcher
install -m 0755 "$source_dir/app.py" "$app_dir/app.py"
install -m 0755 "$source_dir/ctl.py" "$app_dir/ctl.py"
install -m 0644 "$source_dir/VERSION" "$app_dir/VERSION"
install -m 0755 "$source_dir/bin/kde-ascii-saver" "$bin_dir/kde-ascii-saver"
install -m 0755 "$source_dir/bin/kde-ascii-saverctl" "$bin_dir/kde-ascii-saverctl"
install -m 0755 "$source_dir/bin/kde-ascii-saver-watcher" "$bin_dir/kde-ascii-saver-watcher"

[[ -f "$config_home/kde-ascii-saver/config.json" ]] || \
    install -m 0644 "$source_dir/config/config.json" "$config_home/kde-ascii-saver/config.json"
[[ -f "$config_home/kde-ascii-saver/logo.txt" ]] || \
    install -m 0644 "$source_dir/config/logo.txt" "$config_home/kde-ascii-saver/logo.txt"

escaped_exec=$(printf '%s' "$bin_dir/kde-ascii-saver" | sed 's/[&|]/\\&/g')
sed "s|@EXEC@|$escaped_exec|" "$source_dir/io.github.kde_ascii_saver.KdeAsciiSaver.desktop.in" \
    >"$data_home/applications/io.github.kde_ascii_saver.KdeAsciiSaver.desktop"
update-desktop-database "$data_home/applications" 2>/dev/null || true

if "$has_user_systemd"; then
    install -m 0644 "$source_dir/kde-ascii-saver.service" "$systemd_dir/kde-ascii-saver.service"
    rm -f -- "$autostart_dir/kde-ascii-saver-watcher.desktop"
    systemctl --user daemon-reload
    systemctl --user enable --now kde-ascii-saver.service
    integration='systemd user service'
else
    rm -f -- "$systemd_dir/kde-ascii-saver.service"
    escaped_watcher=$(printf '%s' "$bin_dir/kde-ascii-saver-watcher" | sed 's/[&|]/\\&/g')
    sed "s|@WATCHER@|$escaped_watcher|" \
        "$source_dir/io.github.kde_ascii_saver.Watcher.desktop.in" \
        >"$autostart_dir/kde-ascii-saver-watcher.desktop"
    nohup "$bin_dir/kde-ascii-saver-watcher" >/dev/null 2>&1 &
    integration='XDG session autostart'
fi

printf '\nKDE ASCII Saver installed.\n'
printf 'Idle integration: %s\n' "$integration"
printf 'The idle watcher will arm after your next keyboard or pointer input.\n'
printf 'Start now:  %s/kde-ascii-saverctl start\n' "$bin_dir"
printf 'Edit art:   %s/kde-ascii-saverctl edit\n' "$bin_dir"
printf 'Set delay:  %s/kde-ascii-saverctl delay 180\n' "$bin_dir"
printf 'If those commands are not found, add %s to PATH.\n' "$bin_dir"
