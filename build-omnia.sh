#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cache_dir="${SALT_BUILD_CACHE:-$project_dir/.cache}"
output_dir="${SALT_BUILD_OUTPUT:-$project_dir/openwrt/output/omnia}"
mkdir -p "$cache_dir" "$output_dir"
cache_dir="$(cd -- "$cache_dir" && pwd -P)"
output_dir="$(cd -- "$output_dir" && pwd -P)"
jobs="${1:-4}"
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] && ((jobs <= 64)) || { echo 'Jobs must be 1..64' >&2; exit 2; }
image=wrt-salt-sdk:9.1.1
volume=wrt-salt-sdk-9.1.1
archive=sdk-omnia-9.1.1.tar.zst
sha=d3e48600fcb1f53bea679c53b26158e2cd4357e6fa9e46c77627ce443275ba29
mkdir -p "$cache_dir" "$output_dir"
rm -f "$output_dir/build-info.txt"
exec > >(tee "$output_dir/build.log") 2>&1
docker info >/dev/null
docker build -t "$image" "$project_dir/openwrt/docker"
if [[ ! -f "$cache_dir/$archive" ]]; then
    curl -fL --retry 3 https://repo.turris.cz/archive/9.1.1/omnia/packages/sdk-omnia-x86-64.tar.zst -o "$cache_dir/$archive.part"
    mv "$cache_dir/$archive.part" "$cache_dir/$archive"
fi
echo "$sha  $cache_dir/$archive" | sha256sum -c -
docker volume create "$volume" >/dev/null
docker run --rm --user root -v "$volume:/sdk" -v "$cache_dir:/input:ro" \
    --entrypoint bash "$image" -ec '
    if [ ! -f /sdk/.salt-sdk ]; then
        if [ -n "$(ls -A /sdk)" ]; then echo "Unrecognized/partial SDK volume" >&2; exit 1; fi
        tar --zstd -xf /input/sdk-omnia-9.1.1.tar.zst -C /sdk --strip-components=1
        echo TurrisOS-9.1.1 > /sdk/.salt-sdk
        chown -R 1000:1000 /sdk
    fi
    test "$(cat /sdk/.salt-sdk)" = TurrisOS-9.1.1'
docker run --rm -e "JOBS=$jobs" -v "$volume:/sdk" -v "$project_dir:/source:ro" \
    -v "$output_dir:/output" --entrypoint bash "$image" /source/scripts/build-sdk-omnia.sh
