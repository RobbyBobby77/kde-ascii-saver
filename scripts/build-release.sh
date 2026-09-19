#!/usr/bin/env bash
set -euo pipefail

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
output_dir=${1:-"$source_dir/dist"}
version=$(head -n 1 "$source_dir/VERSION")
vendor_dir=${KDE_ASCII_SAVER_VENDOR_DIR:-}

if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]]; then
    printf 'VERSION is not a supported release version: %s\n' "$version" >&2
    exit 1
fi
if ! command -v git >/dev/null || ! command -v gzip >/dev/null || \
    ! command -v sha256sum >/dev/null || ! command -v tar >/dev/null; then
    printf 'Building a release requires git, tar, gzip, and sha256sum.\n' >&2
    exit 1
fi
if ! git -C "$source_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    printf 'Release archives must be built from a Git checkout.\n' >&2
    exit 1
fi

mkdir -p "$output_dir"
output_dir=$(cd -- "$output_dir" && pwd)
archive_name="kde-ascii-saver-$version.tar.gz"
generic_name=kde-ascii-saver.tar.gz
stage_dir=$(mktemp -d "${TMPDIR:-/tmp}/kde-ascii-saver-release.XXXXXX")
cleanup() {
    local status=$?
    trap - EXIT INT TERM HUP
    rm -rf -- "$stage_dir"
    exit "$status"
}
trap cleanup EXIT INT TERM HUP
package_root="$stage_dir/kde-ascii-saver-$version"
mkdir -p "$package_root"

git -C "$source_dir" archive --format=tar HEAD | tar -xf - -C "$package_root"
if [[ -n "$vendor_dir" ]]; then
    vendor_dir=$(cd -- "$vendor_dir" && pwd)
    mapfile -t wheels < <(
        find "$vendor_dir" -maxdepth 1 -type f -name 'terminaltexteffects-*.whl' -print
    )
    if [[ ${#wheels[@]} -ne 1 ]]; then
        printf 'Expected exactly one TerminalTextEffects wheel in %s.\n' "$vendor_dir" >&2
        exit 1
    fi
    mkdir -p "$package_root/vendor"
    cp -- "${wheels[0]}" "$package_root/vendor/"
fi

source_epoch=$(git -C "$source_dir" show -s --format=%ct HEAD)

tar -c --sort=name --mtime="@$source_epoch" --owner=0 --group=0 --numeric-owner \
    --format=ustar -C "$stage_dir" "kde-ascii-saver-$version" | \
    gzip -n -9 >"$output_dir/$archive_name"
cp -- "$output_dir/$archive_name" "$output_dir/$generic_name"

(
    cd -- "$output_dir"
    sha256sum "$archive_name" >"$archive_name.sha256"
    sha256sum "$generic_name" >"$generic_name.sha256"
)

printf 'Created release artifacts in %s:\n' "$output_dir"
printf '  %s\n' "$archive_name" "$archive_name.sha256" "$generic_name" "$generic_name.sha256"
