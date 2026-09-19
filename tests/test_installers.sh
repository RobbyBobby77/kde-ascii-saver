#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
test_dir=$(mktemp -d "${TMPDIR:-/tmp}/kde-ascii-saver-installer-test.XXXXXX")
delayed_watcher_pid=
cleanup() {
    if [[ -n "$delayed_watcher_pid" ]]; then
        kill -KILL "$delayed_watcher_pid" 2>/dev/null || true
        wait "$delayed_watcher_pid" 2>/dev/null || true
    fi
    rm -rf -- "$test_dir"
}
trap cleanup EXIT INT TERM HUP

fail() {
    printf 'installer test failed: %s\n' "$1" >&2
    exit 1
}

version=9.8.7
package_root="$test_dir/package/kde-ascii-saver-$version"
release_root="$test_dir/releases"
specific_dir="$release_root/download/v$version"
latest_dir="$release_root/latest/download"
marker="$test_dir/installer-ran"
args_file="$test_dir/installer-args"
mkdir -p "$package_root" "$specific_dir" "$latest_dir" "$test_dir/download-tmp"

cat >"$package_root/install.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@" >"$TEST_INSTALL_ARGS"
printf 'yes\n' >"$TEST_INSTALL_MARKER"
EOF
chmod 0755 "$package_root/install.sh"
tar -czf "$specific_dir/kde-ascii-saver-$version.tar.gz" \
    -C "$test_dir/package" "kde-ascii-saver-$version"
(
    cd -- "$specific_dir"
    sha256sum "kde-ascii-saver-$version.tar.gz" \
        >"kde-ascii-saver-$version.tar.gz.sha256"
)
cp -- "$specific_dir/kde-ascii-saver-$version.tar.gz" "$latest_dir/kde-ascii-saver.tar.gz"
(
    cd -- "$latest_dir"
    sha256sum kde-ascii-saver.tar.gz >kde-ascii-saver.tar.gz.sha256
)

TEST_INSTALL_MARKER="$marker" TEST_INSTALL_ARGS="$args_file" \
KDE_ASCII_SAVER_RELEASE_BASE_URL="file://$release_root" TMPDIR="$test_dir/download-tmp" \
    "$project_dir/install-online.sh" --version "v$version" --yes --no-start --non-interactive
[[ -f "$marker" ]] || fail 'verified versioned archive did not run its installer'
mapfile -t forwarded_args <"$args_file"
[[ "${forwarded_args[*]}" == '--yes --no-start --non-interactive' ]] || \
    fail 'bootstrap did not forward installer options'
if find "$test_dir/download-tmp" -mindepth 1 -print -quit | grep -q .; then
    fail 'bootstrap left its temporary download directory behind'
fi

rm -f -- "$marker" "$args_file"
TEST_INSTALL_MARKER="$marker" TEST_INSTALL_ARGS="$args_file" \
KDE_ASCII_SAVER_RELEASE_BASE_URL="file://$release_root" TMPDIR="$test_dir/download-tmp" \
    "$project_dir/install-online.sh"
[[ -f "$marker" ]] || fail 'latest release alias did not run its installer'

rm -f -- "$marker"
printf '%064d  %s\n' 0 "kde-ascii-saver-$version.tar.gz" \
    >"$specific_dir/kde-ascii-saver-$version.tar.gz.sha256"
if TEST_INSTALL_MARKER="$marker" TEST_INSTALL_ARGS="$args_file" \
    KDE_ASCII_SAVER_RELEASE_BASE_URL="file://$release_root" \
    "$project_dir/install-online.sh" --version "$version" >/dev/null 2>&1; then
    fail 'bootstrap accepted a bad checksum'
fi
[[ ! -e "$marker" ]] || fail 'installer ran after checksum failure'

# Exercise an upgrade and rollback without building or contacting the live
# session. The fakes only replace the expensive build/venv steps.
fake_bin="$test_dir/fake-bin"
install_home="$test_dir/install-home"
install_data="$test_dir/install-data"
install_config="$test_dir/install-config"
mkdir -p "$fake_bin" "$install_data/kde-ascii-saver" \
    "$install_config/kde-ascii-saver" "$install_home/.local/bin"
cat >"$fake_bin/cmake" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
    -S)
        for argument in "$@"; do
            case "$argument" in
                -DCMAKE_INSTALL_PREFIX=*) printf '%s\n' "${argument#*=}" >"$TEST_CMAKE_STATE" ;;
            esac
        done
        ;;
    --build) ;;
    --install)
        prefix=$(head -n 1 "$TEST_CMAKE_STATE")
        mkdir -p "$prefix"
        printf '%s\n' '#!/bin/sh' 'exit 0' >"$prefix/kde-ascii-saver-watcher"
        chmod 0755 "$prefix/kde-ascii-saver-watcher"
        ;;
    *) exit 2 ;;
esac
EOF
cat >"$fake_bin/python3" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == - ]]; then
    while IFS= read -r _line; do :; done
elif [[ "${1:-}" == -m && "${2:-}" == venv ]]; then
    destination=${!#}
    mkdir -p "$destination/bin"
    cp -- "$0" "$destination/bin/python"
    chmod 0755 "$destination/bin/python"
elif [[ "${1:-}" == -m && "${2:-}" == pip ]]; then
    printf '%s\n' '#!/nonexistent/staged/python' >"$(dirname -- "$0")/tte"
    chmod 0755 "$(dirname -- "$0")/tte"
else
    exit 2
fi
EOF
cat >"$fake_bin/sed" <<'EOF'
#!/usr/bin/env bash
if [[ "${TEST_SED_FAIL:-0}" == 1 ]]; then
    exit 1
fi
exec /usr/bin/sed "$@"
EOF
cat >"$fake_bin/systemctl" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == --user && "${2:-}" == show-environment ]]; then
    exit 1
fi
exit 0
EOF
chmod 0755 "$fake_bin/cmake" "$fake_bin/python3" "$fake_bin/sed" "$fake_bin/systemctl"

printf 'old application\n' >"$install_data/kde-ascii-saver/old-marker"
printf 'custom art\n' >"$install_config/kde-ascii-saver/logo.txt"
printf '{"idle_delay": 777}\n' >"$install_config/kde-ascii-saver/config.json"
printf 'old launcher\n' >"$install_home/.local/bin/kde-ascii-saver"

install_env=(
    HOME="$install_home"
    XDG_DATA_HOME="$install_data"
    XDG_CONFIG_HOME="$install_config"
    XDG_RUNTIME_DIR="$test_dir/no-systemd-runtime"
    KDE_ASCII_SAVER_NO_SESSION=1
    TEST_CMAKE_STATE="$test_dir/cmake-prefix"
    PATH="$fake_bin:$PATH"
)
if env "${install_env[@]}" TEST_SED_FAIL=1 "$project_dir/install.sh" >/dev/null 2>&1; then
    fail 'installer did not report a staged upgrade failure'
fi
[[ -f "$install_data/kde-ascii-saver/old-marker" ]] || fail 'failed upgrade did not restore old app'
[[ $(<"$install_home/.local/bin/kde-ascii-saver") == 'old launcher' ]] || \
    fail 'failed upgrade did not restore managed launcher'

# A replacement XDG watcher that exits before claiming its PID must make the
# install fail and roll back instead of reporting a successful upgrade.
mkdir -p "$test_dir/no-systemd-runtime"
session_install_env=(
    HOME="$install_home"
    XDG_DATA_HOME="$install_data"
    XDG_CONFIG_HOME="$install_config"
    XDG_RUNTIME_DIR="$test_dir/no-systemd-runtime"
    TEST_CMAKE_STATE="$test_dir/cmake-prefix"
    PATH="$fake_bin:$PATH"
)
if env "${session_install_env[@]}" "$project_dir/install.sh" >/dev/null 2>&1; then
    fail 'installer accepted an XDG watcher that exited during startup'
fi
[[ -f "$install_data/kde-ascii-saver/old-marker" ]] || \
    fail 'watcher startup failure did not restore the old application'
[[ $(<"$install_home/.local/bin/kde-ascii-saver") == 'old launcher' ]] || \
    fail 'watcher startup failure did not restore the old launcher'

env "${install_env[@]}" "$project_dir/install.sh" >/dev/null
[[ ! -e "$install_data/kde-ascii-saver/old-marker" ]] || fail 'successful upgrade kept old app payload'
[[ -x "$install_data/kde-ascii-saver/uninstall.sh" ]] || \
    fail 'successful install did not include the hardened uninstaller'
[[ -x "$install_home/.local/bin/kde-ascii-saver-settings" ]] || \
    fail 'successful install did not include the settings launcher'
[[ -f "$install_data/applications/io.github.robbybobby77.KdeAsciiSaver.desktop" ]] || \
    fail 'successful install did not include the control-panel desktop entry'
[[ -f "$install_data/metainfo/io.github.robbybobby77.KdeAsciiSaver.metainfo.xml" ]] || \
    fail 'successful install did not include AppStream metadata'
[[ $(<"$install_config/kde-ascii-saver/logo.txt") == 'custom art' ]] || \
    fail 'upgrade overwrote custom art'
[[ $(<"$install_config/kde-ascii-saver/config.json") == '{"idle_delay": 777}' ]] || \
    fail 'upgrade overwrote configuration'
grep -q 'python" -m terminaltexteffects' "$install_data/kde-ascii-saver/venv/bin/tte" || \
    fail 'staged TTE launcher was not made relocatable'

# A second successful run covers the normal idempotent-upgrade path.
env "${install_env[@]}" "$project_dir/install.sh" >/dev/null

# The uninstaller must wait for a non-systemd watcher to release its executable
# before removing the application directory. This reproduces the same lock race
# that the upgrader must avoid before starting a replacement watcher.
wait_home="$test_dir/wait-home"
wait_data="$test_dir/wait-data"
wait_config="$test_dir/wait-config"
wait_runtime="$test_dir/wait-runtime"
mkdir -p "$wait_home/.local/bin" "$wait_data/kde-ascii-saver" \
    "$wait_config/kde-ascii-saver" "$wait_runtime"
cp -- /bin/bash "$wait_data/kde-ascii-saver/kde-ascii-saver-watcher"
"$wait_data/kde-ascii-saver/kde-ascii-saver-watcher" -c \
    'trap "sleep 0.4; exit 0" TERM; while :; do sleep 1; done' &
delayed_watcher_pid=$!
printf '%s\n' "$delayed_watcher_pid" \
    >"$wait_runtime/kde-ascii-saver-watcher-$(id -u).pid"
HOME="$wait_home" XDG_DATA_HOME="$wait_data" XDG_CONFIG_HOME="$wait_config" \
XDG_RUNTIME_DIR="$wait_runtime" PATH="$fake_bin:$PATH" "$project_dir/uninstall.sh" >/dev/null
if kill -0 "$delayed_watcher_pid" 2>/dev/null; then
    fail 'uninstaller returned before the XDG watcher exited'
fi
wait "$delayed_watcher_pid" 2>/dev/null || true
delayed_watcher_pid=

isolated_home="$test_dir/home"
isolated_data="$test_dir/data"
isolated_config="$test_dir/config"
mkdir -p "$isolated_home/.local/bin" "$isolated_data/kde-ascii-saver" \
    "$isolated_data/applications" "$isolated_data/metainfo" \
    "$isolated_data/icons/hicolor/scalable/apps" "$isolated_config/kde-ascii-saver" \
    "$isolated_config/systemd/user" "$isolated_config/autostart"
printf 'custom art\n' >"$isolated_config/kde-ascii-saver/logo.txt"
printf '{}\n' >"$isolated_config/kde-ascii-saver/config.json"
touch "$isolated_data/kde-ascii-saver/app.py" \
    "$isolated_data/applications/io.github.kde_ascii_saver.KdeAsciiSaver.desktop" \
    "$isolated_data/applications/io.github.robbybobby77.KdeAsciiSaver.desktop" \
    "$isolated_data/metainfo/io.github.robbybobby77.KdeAsciiSaver.metainfo.xml" \
    "$isolated_data/icons/hicolor/scalable/apps/io.github.robbybobby77.KdeAsciiSaver.svg" \
    "$isolated_home/.local/bin/kde-ascii-saver" \
    "$isolated_home/.local/bin/kde-ascii-saverctl" \
    "$isolated_home/.local/bin/kde-ascii-saver-watcher" \
    "$isolated_home/.local/bin/kde-ascii-saver-settings" \
    "$isolated_config/systemd/user/kde-ascii-saver.service" \
    "$isolated_config/autostart/kde-ascii-saver-watcher.desktop"
touch "$isolated_config/autostart/io.github.robbybobby77.KdeAsciiSaver.Watcher.desktop"

HOME="$isolated_home" XDG_DATA_HOME="$isolated_data" XDG_CONFIG_HOME="$isolated_config" \
KDE_ASCII_SAVER_NO_SESSION=1 "$project_dir/uninstall.sh"
[[ ! -e "$isolated_data/kde-ascii-saver" ]] || fail 'uninstaller left application data behind'
[[ -f "$isolated_config/kde-ascii-saver/logo.txt" ]] || fail 'uninstaller removed custom art'
[[ -f "$isolated_config/kde-ascii-saver/config.json" ]] || fail 'uninstaller removed configuration'

printf 'Installer tests passed.\n'
