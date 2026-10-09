#!/usr/bin/env bash
set -euo pipefail
cd /sdk
exec 9>/sdk/.salt-build.lock
flock -n 9 || { echo 'Another build is using this Salt SDK volume' >&2; exit 1; }
base_rev=5204715d14207efa956553d9d7079f6fa1aaea40
packages_rev=23abaa6f3b0fdfd76b570031107e5718476ff0c8
printf '%s\n' \
    "src-git-full base https://openwrt.turris.cz/openwrt/openwrt.git^$base_rev" \
    "src-git-full packages https://openwrt.turris.cz/feed/packages.git^$packages_rev" \
    'src-link salt /source/openwrt/feed' > feeds.conf
git config --global http.version HTTP/1.1
for feed in base packages; do
    if [ ! -d "feeds/$feed/.git" ]; then ./scripts/feeds update "$feed"; fi
done
test "$(git -C feeds/base rev-parse HEAD)" = "$base_rev"
test "$(git -C feeds/packages rev-parse HEAD)" = "$packages_rev"
# The SDK cannot rebuild kernel modules. Python's optional Bluetooth headers
# otherwise pull bluez -> libusb -> kmod-usb-core and an unavailable kernel tree.
if grep -q '^PKG_BUILD_DEPENDS:=bluez ' feeds/packages/lang/python/python3/Makefile; then
    sed -i 's/PKG_BUILD_DEPENDS:=bluez /PKG_BUILD_DEPENDS:=/' feeds/packages/lang/python/python3/Makefile
fi
# feeds uses the caller PID as a scan cookie; containers reuse PIDs. Invalidate
# only generated metadata so newly added local recipes are always discovered.
if [ -d /sdk/package/feeds ]; then
    for obsolete in python-pyzmq python-scikit-build-core; do
        # Remove stale generated symlinks even after their recipes vanish.
        find /sdk/package/feeds -mindepth 2 -maxdepth 2 -type l -name "$obsolete" -delete
    done
fi
rm -rf /sdk/feeds/salt.tmp /sdk/tmp/info
rm -f /sdk/tmp/.packageinfo /sdk/tmp/.packagedeps
./scripts/feeds update salt
./scripts/feeds install -p base openssl zlib ca-certificates libffi bzip2 libreadline libexpat libuuid libgmp opkg procd ubus
# -f only overrides core packages, not already installed packages from another
# feed. Replace those generated symlinks explicitly when a local recipe exists.
for recipe in /source/openwrt/feed/*; do
    find /sdk/package/feeds -mindepth 2 -maxdepth 2 -type l -name "$(basename "$recipe")" -delete
done
./scripts/feeds install -f -p salt rust python-zipp python-importlib-metadata python-looseversion python-salt
# Only selected package dependencies are compiled.
./scripts/feeds install python3 python-packaging python-tornado python-msgpack python-jinja2 python-yaml python-distro python-cryptography python-requests python-dateutil python-psutil python-jmespath python-importlib-metadata
sed -i '/^config PACKAGE_/,/^$/ s/^\([[:space:]]*default\) [my]$/\1 n/' Config-build.in
cat > .config <<'EOF'
CONFIG_TARGET_mvebu=y
CONFIG_TARGET_mvebu_cortexa9=y
CONFIG_TARGET_mvebu_cortexa9_DEVICE_cznic_turris-omnia=y
# CONFIG_ALL is not set
# CONFIG_ALL_KMODS is not set
# CONFIG_ALL_NONSHARED is not set
CONFIG_PACKAGE_salt-minion=m
CONFIG_PACKAGE_minion-opkg=m
CONFIG_PACKAGE_minion-uci=m
CONFIG_PACKAGE_minion-service=m
CONFIG_PACKAGE_minion-openwrt=m
CONFIG_PACKAGE_python3-salt=m
CONFIG_PACKAGE_python3=m
# uclient's build dependency needs an explicitly selected TLS variant in an SDK.
# Reuse the OpenSSL already selected by Python rather than defaulting to mbedTLS.
CONFIG_PACKAGE_libustream-openssl=m
CONFIG_PACKAGE_procd=y
CONFIG_PACKAGE_ubus=y
EOF
make defconfig
python3 /source/scripts/prepare-sdk-infrastructure.py /sdk omnia
# A reused SDK may retain old ZeroMQ artifacts, but none may be selected here.
if grep -Eq '^CONFIG_PACKAGE_(python3-pyzmq|libzmq[^=]*)=[my]' .config; then
    echo 'Unexpected ZeroMQ dependency in TCP-only configuration' >&2; exit 1
fi
make -j"${JOBS:-4}" package/compile V=s
python3 /source/scripts/export-packages.py /sdk /output omnia
find /source/openwrt/feed /source/scripts /source/openwrt/docker -type f -not -path '*/__pycache__/*' -print0 | sort -z | xargs -0 sha256sum > /output/recipe-checksums.txt
{
    echo sdk=TurrisOS-9.1.1-omnia
    echo sdk_sha256=d3e48600fcb1f53bea679c53b26158e2cd4357e6fa9e46c77627ce443275ba29
    echo base_revision="$base_rev"
    echo packages_revision="$packages_rev"
    echo salt=3008.3
    echo profile=minion-openwrt
    echo transport=tcp
    echo python_sdk_patch=omit-optional-bluez-build-dependency
    echo rust_host=official-1.90.0-x86_64-with-armv7-musleabihf-std
    date -u +built_at_utc=%FT%TZ
    cd /output
    sha256sum ./*.ipk > SHA256SUMS
} > /output/build-info.txt
