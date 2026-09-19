#!/usr/bin/env bash
set -euo pipefail

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}
app_dir="$data_home/kde-ascii-saver"
bin_dir="$HOME/.local/bin"
systemd_dir="$config_home/systemd/user"
autostart_dir="$config_home/autostart"
applications_dir="$data_home/applications"
metainfo_dir="$data_home/metainfo"
icons_dir="$data_home/icons/hicolor/scalable/apps"
manage_session=true
check_only=false
install_dependencies=true
assume_yes=false
non_interactive=false
dependencies_attempted=false
has_user_systemd=false
transaction_dir=
staged_app=
backup_app=
swap_complete=false
old_app_moved=false
install_complete=false
service_was_active=false
watcher_was_running=false
session_touched=false
started_watcher_pid=

usage() {
    cat <<'EOF'
Usage: ./install.sh [OPTIONS]

Build and install KDE ASCII Saver for the current user.

Options:
  --check             Check required system dependencies without installing
  --yes               Install missing system dependencies without confirmation
  --no-install-deps   Print dependency guidance instead of offering to install it
  --no-start          Do not stop, enable, start, or reload session services
  --non-interactive   Never prompt; combine with --yes to install dependencies
  -h, --help          Show this help

Set KDE_ASCII_SAVER_NO_SESSION=1 for the same behavior as --no-start. This is
useful with an isolated HOME/XDG environment in package and installer tests.
EOF
}

while (($#)); do
    case "$1" in
        --check) check_only=true ;;
        --yes) assume_yes=true ;;
        --no-install-deps) install_dependencies=false ;;
        --no-start) manage_session=false ;;
        --non-interactive) non_interactive=true ;;
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

show_dependency_help() {
    "$source_dir/scripts/dependency-hint.sh" >&2
}

check_dependencies() {
    local missing=false
    local command
    for command in python3 cmake c++; do
        if ! command -v "$command" >/dev/null; then
            printf 'Missing required command: %s\n' "$command" >&2
            missing=true
        fi
    done
    if "$missing"; then
        return 1
    fi

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
        return 1
    fi
}

install_system_dependencies() {
    local distro_id=unknown
    local distro_like=
    local answer=
    local needs_apt_update=false
    local ID=
    local ID_LIKE=
    local -a command=()
    if [[ -r /etc/os-release ]]; then
        # OS-provided values select a known package-manager command.
        source /etc/os-release
        distro_id=${ID:-unknown}
        distro_like=${ID_LIKE:-}
    fi

    case " $distro_id $distro_like " in
        *" fedora "*|*" rhel "*)
            if "$assume_yes"; then
                command=(sudo dnf --assumeyes install)
            else
                command=(sudo dnf install)
            fi
            command+=(gcc-c++ cmake qt6-qtbase-devel kf6-kidletime-devel python3
                python3-pip python3-devel python3-gobject gtk4 vte291-gtk4
                gtk4-layer-shell desktop-file-utils)
            ;;
        *" debian "*|*" ubuntu "*)
            if ! command -v sudo >/dev/null || ! command -v apt-get >/dev/null; then
                show_dependency_help
                return 1
            fi
            needs_apt_update=true
            if "$assume_yes"; then
                command=(sudo apt-get -y install)
            else
                command=(sudo apt-get install)
            fi
            command+=(build-essential cmake qt6-base-dev libkf6idletime-dev python3
                python3-gi python3-venv gir1.2-gtk-4.0 gir1.2-vte-3.91
                gir1.2-gtk4layershell-1.0 desktop-file-utils)
            ;;
        *" arch "*)
            if "$assume_yes"; then
                command=(sudo pacman --noconfirm -S --needed)
            else
                command=(sudo pacman -S --needed)
            fi
            command+=(base-devel cmake qt6-base kidletime python python-gobject gtk4
                vte4 gtk4-layer-shell desktop-file-utils)
            ;;
        *" opensuse "*|*" suse "*)
            if "$assume_yes"; then
                command=(sudo zypper --non-interactive install)
            else
                command=(sudo zypper install)
            fi
            command+=(gcc-c++ cmake qt6-base-devel kf6-kidletime-devel python3
                python3-gobject typelib-1_0-Gtk-4_0 typelib-1_0-Vte-3_91
                desktop-file-utils)
            ;;
        *)
            printf 'Automatic dependency installation is unavailable for this distribution.\n' >&2
            show_dependency_help
            return 1
            ;;
    esac

    if ! command -v sudo >/dev/null; then
        printf 'sudo is required to install system dependencies automatically.\n' >&2
        show_dependency_help
        return 1
    fi

    printf 'Missing system dependencies. Proposed command:\n  '
    if "$needs_apt_update"; then
        printf 'sudo apt-get update\n  '
    fi
    printf '%q ' "${command[@]}"
    printf '\n'
    if ! "$assume_yes"; then
        if "$non_interactive" || [[ ! -r /dev/tty || ! -w /dev/tty ]]; then
            printf 'Rerun interactively, pass --yes, or install the dependencies above.\n' >&2
            return 1
        fi
        printf 'Install these packages now? [Y/n] ' >/dev/tty
        read -r answer </dev/tty || return 1
        case "$answer" in
            n|N|no|NO|No) return 1 ;;
        esac
    fi
    if "$needs_apt_update"; then
        if [[ -r /dev/tty ]]; then
            sudo apt-get update </dev/tty
        else
            sudo apt-get update
        fi
    fi
    dependencies_attempted=true
    if [[ -r /dev/tty ]]; then
        "${command[@]}" </dev/tty
    else
        "${command[@]}"
    fi
}

wait_for_watcher_exit() {
    local watcher_pid=$1
    local expected_exe=$2
    local current_exe=
    local attempt
    for ((attempt=0; attempt<100; attempt++)); do
        if [[ ! -e "/proc/$watcher_pid/exe" ]]; then
            return 0
        fi
        current_exe=$(readlink -f -- "/proc/$watcher_pid/exe" 2>/dev/null || true)
        if [[ -z "$current_exe" || "$current_exe" != "$expected_exe" ]]; then
            return 0
        fi
        sleep 0.05
    done
    return 1
}

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
                # Resolve the executable again immediately before signaling to
                # reduce the PID-reuse window without matching arbitrary argv.
                if [[ $(readlink -f -- "/proc/$watcher_pid/exe" 2>/dev/null || true) == "$expected_exe" ]]; then
                    watcher_was_running=true
                    kill "$watcher_pid" 2>/dev/null || true
                    if ! wait_for_watcher_exit "$watcher_pid" "$expected_exe"; then
                        printf 'The existing idle watcher did not stop within five seconds.\n' >&2
                        return 1
                    fi
                fi
            fi
        fi
        rm -f -- "$pid_file"
    fi
}

wait_for_watcher_start() {
    local launched_pid=$1
    local pid_file=
    local recorded_pid=
    local watcher_exe=
    local expected_exe=
    local attempt
    if [[ -z "${XDG_RUNTIME_DIR:-}" ]]; then
        return 1
    fi
    pid_file="$XDG_RUNTIME_DIR/kde-ascii-saver-watcher-$(id -u).pid"
    expected_exe=$(readlink -f -- "$app_dir/kde-ascii-saver-watcher" 2>/dev/null || true)
    for ((attempt=0; attempt<100; attempt++)); do
        if [[ -r "$pid_file" ]]; then
            read -r recorded_pid <"$pid_file" || recorded_pid=
            if [[ "$recorded_pid" =~ ^[0-9]+$ ]]; then
                watcher_exe=$(readlink -f -- "/proc/$recorded_pid/exe" 2>/dev/null || true)
                if [[ -n "$watcher_exe" && "$watcher_exe" == "$expected_exe" ]]; then
                    return 0
                fi
            fi
        fi
        if ! kill -0 "$launched_pid" 2>/dev/null; then
            return 1
        fi
        sleep 0.05
    done
    return 1
}

stop_existing_processes() {
    session_touched=true
    if [[ -x "$bin_dir/kde-ascii-saverctl" ]]; then
        "$bin_dir/kde-ascii-saverctl" stop >/dev/null 2>&1 || true
    fi
    if "$has_user_systemd"; then
        if systemctl --user is-active --quiet kde-ascii-saver.service; then
            service_was_active=true
        fi
        systemctl --user stop kde-ascii-saver.service 2>/dev/null || true
    fi
    if [[ -n "${XDG_RUNTIME_DIR:-}" ]]; then
        stop_watcher_pid_file "$XDG_RUNTIME_DIR/kde-ascii-saver-watcher-$(id -u).pid"
    fi
    # Older releases fell back to /tmp; reap a leftover PID file on upgrade.
    stop_watcher_pid_file "/tmp/kde-ascii-saver-watcher-$(id -u).pid"
}

managed_paths=()
managed_backups=()
managed_existed=()

remember_managed_file() {
    local target=$1
    local index=${#managed_paths[@]}
    local backup="$transaction_dir/managed-backup/$index"
    if [[ -e "$target" && ! -f "$target" && ! -L "$target" ]]; then
        printf 'Refusing to replace unexpected managed path: %s\n' "$target" >&2
        return 1
    fi
    managed_paths+=("$target")
    managed_backups+=("$backup")
    if [[ -e "$target" || -L "$target" ]]; then
        mkdir -p "$(dirname -- "$backup")"
        cp -a -- "$target" "$backup"
        managed_existed+=(1)
    else
        managed_existed+=(0)
    fi
}

install_managed_file() {
    local source=$1
    local target=$2
    local mode=$3
    local temporary
    temporary=$(mktemp "$(dirname -- "$target")/.kde-ascii-saver-file.XXXXXX")
    if ! install -m "$mode" "$source" "$temporary"; then
        rm -f -- "$temporary"
        return 1
    fi
    mv -fT -- "$temporary" "$target"
}

write_managed_file() {
    local target=$1
    local mode=$2
    local temporary
    temporary=$(mktemp "$(dirname -- "$target")/.kde-ascii-saver-file.XXXXXX")
    if ! cat >"$temporary"; then
        rm -f -- "$temporary"
        return 1
    fi
    chmod "$mode" "$temporary"
    mv -fT -- "$temporary" "$target"
}

restore_managed_files() {
    local index target
    for ((index=${#managed_paths[@]} - 1; index >= 0; index--)); do
        target=${managed_paths[$index]}
        rm -f -- "$target"
        if [[ "${managed_existed[$index]}" == 1 ]]; then
            mkdir -p "$(dirname -- "$target")"
            cp -a -- "${managed_backups[$index]}" "$target"
        fi
    done
}

cleanup() {
    local status=$?
    trap - EXIT INT TERM HUP
    if [[ "$install_complete" != true && -n "$started_watcher_pid" ]] && \
        kill -0 "$started_watcher_pid" 2>/dev/null; then
        kill "$started_watcher_pid" 2>/dev/null || true
        wait "$started_watcher_pid" 2>/dev/null || true
    fi
    if [[ "$install_complete" != true && ( "$swap_complete" == true || "$old_app_moved" == true ) ]]; then
        printf 'Installation did not complete; restoring the previous version.\n' >&2
        if [[ "$swap_complete" == true ]]; then
            restore_managed_files
            rm -rf -- "$app_dir"
        fi
        if [[ -d "$backup_app" ]]; then
            mv -- "$backup_app" "$app_dir"
        fi
    fi
    if [[ "$install_complete" != true ]] && "$manage_session" && "$session_touched"; then
        if "$has_user_systemd"; then
            systemctl --user daemon-reload >/dev/null 2>&1 || true
            if "$service_was_active"; then
                systemctl --user start kde-ascii-saver.service >/dev/null 2>&1 || true
            fi
        elif "$watcher_was_running" && [[ -x "$bin_dir/kde-ascii-saver-watcher" ]]; then
            nohup "$bin_dir/kde-ascii-saver-watcher" >/dev/null 2>&1 &
        fi
    fi
    if [[ -n "$transaction_dir" && -d "$transaction_dir" ]]; then
        rm -rf -- "$transaction_dir"
    fi
    exit "$status"
}
trap cleanup EXIT INT TERM HUP

if ! check_dependencies; then
    if "$check_only" || ! "$install_dependencies"; then
        show_dependency_help
        exit 1
    fi
    if ! install_system_dependencies || ! check_dependencies; then
        printf 'Required dependencies are still unavailable.\n' >&2
        show_dependency_help
        exit 1
    fi
fi
if "$check_only"; then
    printf 'Required GTK/VTE runtime and build commands are available.\n'
    exit 0
fi

if "$manage_session" && command -v systemctl >/dev/null && \
    systemctl --user show-environment >/dev/null 2>&1; then
    has_user_systemd=true
elif ! "$manage_session" && command -v systemctl >/dev/null && \
    [[ -n "${XDG_RUNTIME_DIR:-}" && -S "$XDG_RUNTIME_DIR/systemd/private" ]]; then
    # In --no-start mode detect the normal integration without contacting the
    # live manager. All files still honor the supplied HOME/XDG paths.
    has_user_systemd=true
fi

mkdir -p "$data_home" "$config_home"
transaction_dir=$(mktemp -d "$data_home/.kde-ascii-saver-install.XXXXXX")
chmod 0700 "$transaction_dir"
staged_app="$transaction_dir/app"
backup_app="$transaction_dir/previous-app"
build_dir="$transaction_dir/build"
mkdir -p "$staged_app"

configure_watcher() {
    cmake -S "$source_dir" -B "$build_dir" \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$staged_app" \
        -DCMAKE_INSTALL_BINDIR=.
}

if ! configure_watcher; then
    if "$install_dependencies" && ! "$dependencies_attempted" && \
        install_system_dependencies && configure_watcher; then
        :
    else
        printf 'Unable to configure the Qt 6/KF6 watcher build.\n' >&2
        show_dependency_help
        exit 1
    fi
fi
if ! cmake --build "$build_dir" --parallel; then
    printf 'Unable to build the Qt 6/KF6 watcher.\n' >&2
    exit 1
fi
if ! cmake --install "$build_dir"; then
    printf 'Unable to stage the Qt 6/KF6 watcher.\n' >&2
    exit 1
fi

if ! python3 -m venv --system-site-packages "$staged_app/venv"; then
    printf 'Unable to create a Python virtual environment.\n' >&2
    show_dependency_help
    exit 1
fi
pip_args=(--quiet --disable-pip-version-check --require-hashes -r "$source_dir/requirements.txt")
if [[ -d "$source_dir/vendor" ]] && \
    find "$source_dir/vendor" -maxdepth 1 -type f -name 'terminaltexteffects-*.whl' -print -quit \
        | grep -q .; then
    pip_args+=(--no-index --no-deps --find-links "$source_dir/vendor")
fi
if ! "$staged_app/venv/bin/python" -m pip install "${pip_args[@]}"; then
    printf 'Unable to install TerminalTextEffects. Check network access and Python packaging support.\n' >&2
    exit 1
fi

install -m 0755 "$source_dir/app.py" "$staged_app/app.py"
install -m 0755 "$source_dir/ctl.py" "$staged_app/ctl.py"
install -m 0755 "$source_dir/settings.py" "$staged_app/settings.py"
install -m 0755 "$source_dir/uninstall.sh" "$staged_app/uninstall.sh"
install -m 0644 "$source_dir/helpers.py" "$staged_app/helpers.py"
install -m 0644 "$source_dir/VERSION" "$staged_app/VERSION"

# Console scripts created in a staging venv contain an absolute staging path.
# Make the one runtime script relocatable before the atomic directory swap.
if [[ -f "$staged_app/venv/bin/tte" || -L "$staged_app/venv/bin/tte" ]]; then
    rm -f -- "$staged_app/venv/bin/tte"
    printf '%s\n' '#!/bin/sh' \
        'script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)' \
        'exec "$script_dir/python" -m terminaltexteffects "$@"' \
        >"$staged_app/venv/bin/tte"
    chmod 0755 "$staged_app/venv/bin/tte"
else
    printf 'TerminalTextEffects installed without its tte console script.\n' >&2
    exit 1
fi

mkdir -p "$bin_dir" "$config_home/kde-ascii-saver" "$applications_dir" \
    "$metainfo_dir" "$icons_dir"
if "$has_user_systemd"; then
    mkdir -p "$systemd_dir"
else
    mkdir -p "$autostart_dir"
fi

remember_managed_file "$bin_dir/kde-ascii-saver"
remember_managed_file "$bin_dir/kde-ascii-saverctl"
remember_managed_file "$bin_dir/kde-ascii-saver-watcher"
remember_managed_file "$bin_dir/kde-ascii-saver-settings"
remember_managed_file "$applications_dir/io.github.robbybobby77.KdeAsciiSaver.desktop"
remember_managed_file "$applications_dir/io.github.kde_ascii_saver.KdeAsciiSaver.desktop"
remember_managed_file "$metainfo_dir/io.github.robbybobby77.KdeAsciiSaver.metainfo.xml"
remember_managed_file "$icons_dir/io.github.robbybobby77.KdeAsciiSaver.svg"
remember_managed_file "$systemd_dir/kde-ascii-saver.service"
remember_managed_file "$autostart_dir/io.github.robbybobby77.KdeAsciiSaver.Watcher.desktop"
remember_managed_file "$autostart_dir/kde-ascii-saver-watcher.desktop"

if [[ -e "$app_dir" || -L "$app_dir" ]]; then
    if [[ -L "$app_dir" || ! -d "$app_dir" ]]; then
        printf 'Refusing to replace unexpected application path: %s\n' "$app_dir" >&2
        exit 1
    fi
fi

if "$manage_session"; then
    stop_existing_processes
fi

if [[ -e "$app_dir" || -L "$app_dir" ]]; then
    mv -- "$app_dir" "$backup_app"
    old_app_moved=true
fi
mv -- "$staged_app" "$app_dir"
swap_complete=true

install_managed_file "$source_dir/bin/kde-ascii-saver" "$bin_dir/kde-ascii-saver" 0755
install_managed_file "$source_dir/bin/kde-ascii-saverctl" "$bin_dir/kde-ascii-saverctl" 0755
install_managed_file "$source_dir/bin/kde-ascii-saver-watcher" "$bin_dir/kde-ascii-saver-watcher" 0755
install_managed_file "$source_dir/bin/kde-ascii-saver-settings" \
    "$bin_dir/kde-ascii-saver-settings" 0755

if [[ ! -e "$config_home/kde-ascii-saver/config.json" && \
    ! -L "$config_home/kde-ascii-saver/config.json" ]]; then
    install_managed_file "$source_dir/config/config.json" \
        "$config_home/kde-ascii-saver/config.json" 0644
fi
if [[ ! -e "$config_home/kde-ascii-saver/logo.txt" && \
    ! -L "$config_home/kde-ascii-saver/logo.txt" ]]; then
    install_managed_file "$source_dir/config/logo.txt" \
        "$config_home/kde-ascii-saver/logo.txt" 0644
fi

escaped_settings=$(printf '%s' "$bin_dir/kde-ascii-saver-settings" | sed 's/[&|]/\\&/g')
sed "s|@SETTINGS@|$escaped_settings|" \
    "$source_dir/io.github.robbybobby77.KdeAsciiSaver.desktop.in" \
    | write_managed_file \
        "$applications_dir/io.github.robbybobby77.KdeAsciiSaver.desktop" 0644
install_managed_file "$source_dir/io.github.robbybobby77.KdeAsciiSaver.metainfo.xml" \
    "$metainfo_dir/io.github.robbybobby77.KdeAsciiSaver.metainfo.xml" 0644
install_managed_file "$source_dir/resources/io.github.robbybobby77.KdeAsciiSaver.svg" \
    "$icons_dir/io.github.robbybobby77.KdeAsciiSaver.svg" 0644
rm -f -- "$applications_dir/io.github.kde_ascii_saver.KdeAsciiSaver.desktop"
update-desktop-database "$applications_dir" 2>/dev/null || true

if "$has_user_systemd"; then
    install_managed_file "$source_dir/kde-ascii-saver.service" \
        "$systemd_dir/kde-ascii-saver.service" 0644
    rm -f -- "$autostart_dir/io.github.robbybobby77.KdeAsciiSaver.Watcher.desktop" \
        "$autostart_dir/kde-ascii-saver-watcher.desktop"
    integration='systemd user service'
    if "$manage_session"; then
        systemctl --user daemon-reload
        systemctl --user enable --now kde-ascii-saver.service
    fi
else
    rm -f -- "$systemd_dir/kde-ascii-saver.service"
    escaped_watcher=$(printf '%s' "$bin_dir/kde-ascii-saver-watcher" | sed 's/[&|]/\\&/g')
    sed "s|@WATCHER@|$escaped_watcher|" \
        "$source_dir/io.github.robbybobby77.KdeAsciiSaver.Watcher.desktop.in" \
        | write_managed_file \
            "$autostart_dir/io.github.robbybobby77.KdeAsciiSaver.Watcher.desktop" 0644
    rm -f -- "$autostart_dir/kde-ascii-saver-watcher.desktop"
    integration='XDG session autostart'
    if "$manage_session"; then
        nohup "$bin_dir/kde-ascii-saver-watcher" >/dev/null 2>&1 &
        started_watcher_pid=$!
        if ! wait_for_watcher_start "$started_watcher_pid"; then
            printf 'The XDG idle watcher did not start successfully.\n' >&2
            exit 1
        fi
    fi
fi

install_complete=true
rm -rf -- "$backup_app"

printf '\nKDE ASCII Saver %s installed.\n' "$(head -n 1 "$app_dir/VERSION")"
printf 'Idle integration: %s\n' "$integration"
if "$manage_session"; then
    printf 'The idle watcher will arm after your next keyboard or pointer input.\n'
else
    printf 'Session integration was installed but not started (--no-start).\n'
fi
printf 'Start now:  %s/kde-ascii-saverctl start\n' "$bin_dir"
printf 'Control:    %s/kde-ascii-saverctl prefs\n' "$bin_dir"
printf 'Edit art:   %s/kde-ascii-saverctl edit\n' "$bin_dir"
printf 'Set delay:  %s/kde-ascii-saverctl delay 180\n' "$bin_dir"
printf 'If those commands are not found, add %s to PATH.\n' "$bin_dir"

if "$manage_session" && ! "$non_interactive" && ! "$assume_yes" && \
    [[ -r /dev/tty && -w /dev/tty ]]; then
    printf 'Open a windowed preview now? [Y/n] ' >/dev/tty
    read -r preview_answer </dev/tty || preview_answer=n
    case "$preview_answer" in
        n|N|no|NO|No) ;;
        *) "$bin_dir/kde-ascii-saverctl" preview || true ;;
    esac
fi
