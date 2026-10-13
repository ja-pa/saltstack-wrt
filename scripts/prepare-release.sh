#!/usr/bin/env bash
# Package local-feed IPKs and checksums for a GitHub release.
# Usage: bash scripts/prepare-release.sh [omnia|x86_64] [version] [destination]
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
target="${1:-omnia}"
version="${2:-0.1.0}"
case "$target" in
    omnia) system=turrisos-9.1.1 ;;
    x86_64) system=openwrt-24.10.8 ;;
    *) echo "Usage: $0 [omnia|x86_64] [version] [destination]" >&2; exit 1 ;;
esac
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
    echo "Use a release version such as 0.1.0" >&2; exit 1;
}

source_dir="$project_dir/openwrt/output/$target"
destination="${3:-$project_dir/openwrt/output/release/$version}"
archive="saltstack-wrt-$version-$target-$system.tar.gz"
manifest="$source_dir/install-local.txt"
[[ -f "$manifest" ]] || { echo "Missing manifest: $manifest" >&2; exit 1; }

packages=()
while IFS= read -r ipk || [[ -n "$ipk" ]]; do
    ipk="${ipk%$'\r'}"
    [[ -n "$ipk" ]] || continue
    [[ "$ipk" != */* && "$ipk" == *.ipk && -f "$source_dir/$ipk" ]] || {
        echo "Invalid or missing package: $ipk" >&2; exit 1;
    }
    packages+=("$source_dir/$ipk")
done < "$manifest"
[[ ${#packages[@]} -gt 0 ]] || { echo "Package list is empty" >&2; exit 1; }

# Never replace an existing release archive.
[[ ! -e "$destination/$archive" ]] || { echo "Archive already exists: $destination/$archive" >&2; exit 1; }
mkdir -p -- "$destination"
destination="$(cd -- "$destination" && pwd -P)"
staging="$(mktemp -d /tmp/salt-release.XXXXXXXX)"
trap '[[ "$staging" == /tmp/salt-release.* ]] && rm -rf -- "$staging"' EXIT
cp -- "${packages[@]}" "$manifest" "$staging/"
files=("${packages[@]##*/}" install-local.txt)
if [[ -f "$source_dir/build-info.txt" ]]; then
    cp -- "$source_dir/build-info.txt" "$staging/"
    files+=(build-info.txt)
fi
(
    cd -- "$staging"
    sha256sum -- "${files[@]}" > SHA256SUMS
    tar -czf "$archive" -- "${files[@]}" SHA256SUMS
)
mv -- "$staging/$archive" "$destination/$archive"
(
    cd -- "$destination"
    sha256sum -- "$archive" >> SHA256SUMS
)
printf 'Created %s/%s (%s packages)\nChecksums: %s/SHA256SUMS\n' \
    "$destination" "$archive" "${#packages[@]}" "$destination"
