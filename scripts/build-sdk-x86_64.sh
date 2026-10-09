#!/usr/bin/env bash
set -euo pipefail
cd /sdk
exec 9>/sdk/.salt-build.lock
flock -n 9 || { echo 'Another build is using this x86_64 SDK volume' >&2; exit 1; }
base_rev=443ec4032a78cbeb52c5761b7702033904fa6a11
packages_rev=23abaa6f3b0fdfd76b570031107e5718476ff0c8
# A generated feed view excludes the Omnia-only Rust replacement. Recipes
# themselves always point to the unchanged source feed, mounted read-only.
mkdir -p /sdk/salt-feed-x86_64
for recipe in /source/openwrt/feed/*; do
    [ "$(basename "$recipe")" = rust ] && continue
    ln -sfn "$recipe" "/sdk/salt-feed-x86_64/$(basename "$recipe")"
done
printf '%s\n' \
    "src-git-full base https://github.com/openwrt/openwrt.git^$base_rev" \
    "src-git-full packages https://github.com/openwrt/packages.git^$packages_rev" \
    'src-link salt /sdk/salt-feed-x86_64' > feeds.conf
git config --global http.version HTTP/1.1
for feed in base packages; do
    if [ ! -d "feeds/$feed/.git" ]; then ./scripts/feeds update "$feed"; fi
done
test "$(git -C feeds/base rev-parse HEAD)" = "$base_rev"
test "$(git -C feeds/packages rev-parse HEAD)" = "$packages_rev"
# Same SDK-only workaround as Omnia: no kernel tree for optional Bluetooth.
if grep -q '^PKG_BUILD_DEPENDS:=bluez ' feeds/packages/lang/python/python3/Makefile; then
    sed -i 's/PKG_BUILD_DEPENDS:=bluez /PKG_BUILD_DEPENDS:=/' feeds/packages/lang/python/python3/Makefile
fi
rm -rf /sdk/feeds/salt.tmp /sdk/tmp/info
rm -f /sdk/tmp/.packageinfo /sdk/tmp/.packagedeps
./scripts/feeds update salt
./scripts/feeds install -p base openssl zlib ca-certificates libffi bzip2 libreadline libexpat libuuid libgmp opkg procd ubus
for recipe in /sdk/salt-feed-x86_64/*; do
    find /sdk/package/feeds -mindepth 2 -maxdepth 2 -type l -name "$(basename "$recipe")" -delete
done
./scripts/feeds install -p packages rust
./scripts/feeds install -f -p salt python-zipp python-importlib-metadata python-looseversion python-salt
./scripts/feeds install python3 python-packaging python-tornado python-msgpack python-jinja2 python-yaml python-distro python-cryptography python-requests python-dateutil python-psutil python-jmespath python-importlib-metadata
sed -i '/^config PACKAGE_/,/^$/ s/^\([[:space:]]*default\) [my]$/\1 n/' Config-build.in
cat > .config <<'EOF'
CONFIG_TARGET_x86=y
CONFIG_TARGET_x86_64=y
CONFIG_TARGET_x86_64_DEVICE_generic=y
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
CONFIG_PACKAGE_libustream-openssl=m
CONFIG_PACKAGE_procd=y
CONFIG_PACKAGE_ubus=y
EOF
make defconfig
python3 /source/scripts/prepare-sdk-infrastructure.py /sdk x86_64
if grep -Eq '^CONFIG_PACKAGE_(python3-pyzmq|libzmq[^=]*)=[my]' .config; then
    echo 'Unexpected ZeroMQ dependency in TCP-only configuration' >&2; exit 1
fi
if ! compgen -G '/sdk/build_dir/target-*/pypi/salt-*/ipkg-install/usr/lib/python*/site-packages/salt/minion.py' >/dev/null; then
    # Also recover SDK caches created before retaining the audit reference.
    make package/feeds/salt/python-salt/clean V=s
fi
make -j"${JOBS:-4}" package/compile V=s
python3 /source/scripts/export-packages.py /sdk /output x86_64
find /source/openwrt/feed /source/scripts /source/openwrt/docker -type f -not -path '*/__pycache__/*' -print0 | sort -z | xargs -0 sha256sum > /output/recipe-checksums.txt
{
    echo sdk=OpenWrt-24.10.8-x86_64
    echo sdk_sha256=ac4a0405d2eea821b06f93c14ba13ffa90ad0457648903df7dde02570027ab21
    echo base_revision="$base_rev"
    echo packages_revision="$packages_rev"
    echo salt=3008.3
    echo profile=minion-openwrt
    echo transport=tcp
    echo python_sdk_patch=omit-optional-bluez-build-dependency
    echo rust_host=upstream-packages-feed
    date -u +built_at_utc=%FT%TZ
    cd /output
    sha256sum ./*.ipk > SHA256SUMS
} > /output/build-info.txt
