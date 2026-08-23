#!/usr/bin/env bash
set -euo pipefail

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
output_dir=${1:-"$source_dir/dist"}
version=$(head -n 1 "$source_dir/VERSION")

if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]]; then
    printf 'VERSION is not a supported release version: %s\n' "$version" >&2
    exit 1
fi
if ! command -v git >/dev/null || ! command -v gzip >/dev/null || ! command -v sha256sum >/dev/null; then
    printf 'Building a release requires git, gzip, and sha256sum.\n' >&2
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

git -C "$source_dir" archive --format=tar --prefix="kde-ascii-saver-$version/" HEAD | \
    gzip -n -9 >"$output_dir/$archive_name"
cp -- "$output_dir/$archive_name" "$output_dir/$generic_name"

(
    cd -- "$output_dir"
    sha256sum "$archive_name" >"$archive_name.sha256"
    sha256sum "$generic_name" >"$generic_name.sha256"
)

printf 'Created release artifacts in %s:\n' "$output_dir"
printf '  %s\n' "$archive_name" "$archive_name.sha256" "$generic_name" "$generic_name.sha256"
