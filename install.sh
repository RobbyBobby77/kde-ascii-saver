#!/bin/bash
set -euo pipefail

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}
app_dir="$data_home/kde-ascii-saver"
bin_dir="$HOME/.local/bin"
systemd_dir="$config_home/systemd/user"

for command in python3 cmake systemctl; do
    if ! command -v "$command" >/dev/null; then
        printf 'Missing required command: %s\n' "$command" >&2
        printf 'On Fedora, install dependencies with:\n' >&2
        printf '  sudo dnf install gcc-c++ cmake qt6-qtbase-devel kf6-kidletime-devel python3-gobject gtk4 vte291-gtk4 gtk4-layer-shell\n' >&2
        exit 1
    fi
done

python3 - <<'PY'
import gi
for namespace, version in (("Gtk", "4.0"), ("Vte", "3.91")):
    gi.require_version(namespace, version)
try:
    gi.require_version("Gtk4LayerShell", "1.0")
except ValueError:
    print("Warning: gtk4-layer-shell is unavailable; regular fullscreen windows will be used.")
PY

mkdir -p "$app_dir" "$bin_dir" "$config_home/kde-ascii-saver" \
    "$data_home/applications" "$systemd_dir"

cmake -S "$source_dir" -B "$app_dir/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$app_dir/build" --parallel

if [[ ! -x "$app_dir/venv/bin/python" ]]; then
    python3 -m venv --system-site-packages "$app_dir/venv"
fi
"$app_dir/venv/bin/python" -m pip install --quiet --disable-pip-version-check -r "$source_dir/requirements.txt"

systemctl --user stop kde-ascii-saver.service 2>/dev/null || true
install -m 0755 "$app_dir/build/kde-ascii-saver-watcher" "$app_dir/kde-ascii-saver-watcher"
install -m 0755 "$source_dir/app.py" "$app_dir/app.py"
install -m 0755 "$source_dir/ctl.py" "$app_dir/ctl.py"
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

install -m 0644 "$source_dir/kde-ascii-saver.service" "$systemd_dir/kde-ascii-saver.service"
systemctl --user daemon-reload
systemctl --user enable --now kde-ascii-saver.service

printf '\nKDE ASCII Saver installed.\n'
printf 'The idle watcher will arm after your next keyboard or pointer input.\n'
printf 'Start now:  %s/kde-ascii-saverctl start\n' "$bin_dir"
printf 'Edit art:   %s/kde-ascii-saverctl edit\n' "$bin_dir"
printf 'Set delay:  %s/kde-ascii-saverctl delay 180\n' "$bin_dir"
