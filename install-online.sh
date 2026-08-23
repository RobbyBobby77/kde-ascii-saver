#!/usr/bin/env bash
set -euo pipefail

repository=${KDE_ASCII_SAVER_REPOSITORY:-RobbyBobby77/kde-ascii-saver}
requested_version=${KDE_ASCII_SAVER_VERSION:-latest}
release_base_url=${KDE_ASCII_SAVER_RELEASE_BASE_URL:-"https://github.com/$repository/releases"}
installer_args=()
temporary_dir=

usage() {
    cat <<'EOF'
Usage: install-online.sh [OPTIONS] [-- INSTALL_OPTIONS]

Download a KDE ASCII Saver GitHub release, verify its SHA-256 checksum, and run
its user-local installer. With no options, the latest stable release is used.

Options:
  --version VERSION   Install a specific release (for example 0.1.0 or v0.1.0)
  --no-start          Pass --no-start to the downloaded installer
  --non-interactive   Pass --non-interactive to the downloaded installer
  -h, --help          Show this help

Environment overrides:
  KDE_ASCII_SAVER_VERSION           Release version, or "latest"
  KDE_ASCII_SAVER_REPOSITORY        GitHub owner/repository
  KDE_ASCII_SAVER_RELEASE_BASE_URL  Release URL base (intended for testing)
  KDE_ASCII_SAVER_NO_SESSION=1      Prevent installer service/process actions
EOF
}

while (($#)); do
    case "$1" in
        --version)
            if (($# < 2)); then
                printf '%s\n' '--version requires a value' >&2
                exit 2
            fi
            requested_version=$2
            shift
            ;;
        --no-start|--non-interactive)
            installer_args+=("$1")
            ;;
        --)
            shift
            installer_args+=("$@")
            break
            ;;
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

for command in curl python3; do
    if ! command -v "$command" >/dev/null; then
        printf 'Required download command not found: %s\n' "$command" >&2
        exit 1
    fi
done
if command -v sha256sum >/dev/null; then
    checksum_tool=sha256sum
elif command -v shasum >/dev/null; then
    checksum_tool=shasum
else
    printf 'A SHA-256 tool is required (sha256sum or shasum).\n' >&2
    exit 1
fi

case "$release_base_url" in
    https://*) curl_protocol='=https' ;;
    file://*) curl_protocol='=file' ;;
    *)
        printf 'Release URL must use HTTPS (or file:// for local testing).\n' >&2
        exit 2
        ;;
esac

if [[ "$requested_version" == latest ]]; then
    archive_name=kde-ascii-saver.tar.gz
    download_base="$release_base_url/latest/download"
else
    version=${requested_version#v}
    if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]]; then
        printf 'Invalid release version: %s\n' "$requested_version" >&2
        exit 2
    fi
    archive_name="kde-ascii-saver-$version.tar.gz"
    download_base="$release_base_url/download/v$version"
fi
checksum_name="$archive_name.sha256"

temporary_dir=$(mktemp -d "${TMPDIR:-/tmp}/kde-ascii-saver-download.XXXXXX")
chmod 0700 "$temporary_dir"
cleanup() {
    local status=$?
    trap - EXIT INT TERM HUP
    if [[ -n "$temporary_dir" && -d "$temporary_dir" ]]; then
        rm -rf -- "$temporary_dir"
    fi
    exit "$status"
}
trap cleanup EXIT INT TERM HUP

printf 'Downloading KDE ASCII Saver %s...\n' "$requested_version"
curl --fail --silent --show-error --location --proto "$curl_protocol" \
    --proto-redir "$curl_protocol" --tlsv1.2 \
    "$download_base/$archive_name" --output "$temporary_dir/$archive_name"
curl --fail --silent --show-error --location --proto "$curl_protocol" \
    --proto-redir "$curl_protocol" --tlsv1.2 \
    "$download_base/$checksum_name" --output "$temporary_dir/$checksum_name"

checksum_line=$(head -n 1 "$temporary_dir/$checksum_name")
if [[ ! "$checksum_line" =~ ^([[:xdigit:]]{64})[[:space:]][[:space:]\*]([^/]+)$ ]] || \
    [[ "${BASH_REMATCH[2]}" != "$archive_name" ]]; then
    printf 'Invalid checksum file received; refusing to install.\n' >&2
    exit 1
fi
expected_checksum=${BASH_REMATCH[1],,}
if [[ "$checksum_tool" == sha256sum ]]; then
    actual_checksum=$(sha256sum "$temporary_dir/$archive_name" | awk '{print $1}')
else
    actual_checksum=$(shasum -a 256 "$temporary_dir/$archive_name" | awk '{print $1}')
fi
if [[ "$actual_checksum" != "$expected_checksum" ]]; then
    printf 'SHA-256 verification failed; refusing to install.\n' >&2
    exit 1
fi
printf 'SHA-256 verified.\n'

mkdir "$temporary_dir/source"
# Release archives contain only regular files and directories. Reject links,
# device nodes, absolute names, and parent traversal before extracting.
if ! python3 - "$temporary_dir/$archive_name" "$temporary_dir/source" <<'PY'
import pathlib
import shutil
import sys
import tarfile

archive, destination = sys.argv[1:]
destination_path = pathlib.Path(destination)
with tarfile.open(archive, "r:gz") as release:
    members = release.getmembers()
    if len(members) > 10_000 or sum(member.size for member in members) > 100 * 1024 * 1024:
        raise SystemExit("release archive exceeds safety limits")
    for member in members:
        path = pathlib.PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
            raise SystemExit(f"unsafe archive member: {member.name}")
        target = destination_path.joinpath(*path.parts)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            target.chmod(0o755)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        source = release.extractfile(member)
        if source is None:
            raise SystemExit(f"could not read archive member: {member.name}")
        with source, target.open("wb") as output:
            shutil.copyfileobj(source, output)
        target.chmod(0o755 if member.mode & 0o111 else 0o644)
PY
then
    printf 'Release archive failed safety validation; refusing to install.\n' >&2
    exit 1
fi
mapfile -t roots < <(find "$temporary_dir/source" -mindepth 1 -maxdepth 1 -type d -print)
if [[ ${#roots[@]} -ne 1 || ! -x "${roots[0]}/install.sh" ]]; then
    printf 'Release archive does not contain one installable source directory.\n' >&2
    exit 1
fi

"${roots[0]}/install.sh" "${installer_args[@]}"
