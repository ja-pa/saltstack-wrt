#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cache_dir="${SALT_BUILD_CACHE:-$project_dir/.cache}"
output_dir="${SALT_BUILD_OUTPUT:-$project_dir/openwrt/output/x86_64}"
mkdir -p "$cache_dir" "$output_dir"
cache_dir="$(cd -- "$cache_dir" && pwd -P)"
output_dir="$(cd -- "$output_dir" && pwd -P)"
jobs="${1:-4}"
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] && ((jobs <= 64)) || { echo 'Jobs must be 1..64' >&2; exit 2; }
image=wrt-salt-sdk-x86_64:24.10.8
volume=wrt-salt-sdk-x86_64-24.10.8
archive=openwrt-sdk-24.10.8-x86-64_gcc-13.3.0_musl.Linux-x86_64.tar.zst
sha=ac4a0405d2eea821b06f93c14ba13ffa90ad0457648903df7dde02570027ab21
mkdir -p "$cache_dir" "$output_dir"
rm -f "$output_dir/build-info.txt"
exec > >(tee "$output_dir/build.log") 2>&1
docker info >/dev/null
docker build -t "$image" "$project_dir/openwrt/docker"
if [[ ! -f "$cache_dir/$archive" ]]; then
    curl -fL --retry 3 "https://downloads.openwrt.org/releases/24.10.8/targets/x86/64/$archive" -o "$cache_dir/$archive.part"
    mv "$cache_dir/$archive.part" "$cache_dir/$archive"
fi
echo "$sha  $cache_dir/$archive" | sha256sum -c -
docker volume create "$volume" >/dev/null
docker run --rm --user root -v "$volume:/sdk" -v "$cache_dir:/input:ro" \
    --entrypoint bash "$image" -ec '
    if [ ! -f /sdk/.salt-sdk ]; then
        if [ -n "$(ls -A /sdk)" ]; then echo "Unrecognized/partial x86_64 SDK volume" >&2; exit 1; fi
        tar --zstd -xf /input/openwrt-sdk-24.10.8-x86-64_gcc-13.3.0_musl.Linux-x86_64.tar.zst -C /sdk --strip-components=1
        echo OpenWrt-24.10.8-x86_64 > /sdk/.salt-sdk
        chown -R 1000:1000 /sdk
    fi
    test "$(cat /sdk/.salt-sdk)" = OpenWrt-24.10.8-x86_64'
docker run --rm --cpus "$jobs" -e "JOBS=$jobs" -v "$volume:/sdk" -v "$project_dir:/source:ro" \
    -v "$output_dir:/output" --entrypoint bash "$image" /source/scripts/build-sdk-x86_64.sh
