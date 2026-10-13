![OpenWrt + Salt Project: Salt minion for OpenWrt. Unofficial community package.](docs/assets/salt-minion-openwrt.png)

# Salt minion packages for OpenWrt and Turris OS

Experimental package definitions and reproducible SDK build helpers for Salt
3008.3 on OpenWrt and Turris OS. The local feed includes the Salt minion,
router integrations, and compatibility dependencies needed by the builds.
The Salt master runs on a separate computer.

The packages use **TCP transport**, which has worked well in our verification.
They do not include ZeroMQ support. See the official
[Salt TCP transport documentation](https://docs.saltproject.io/en/3008/topics/transports/tcp.html).

## Package definitions

Recipes are in [openwrt/feed](openwrt/feed/). The roles below describe their use
in these builds; not every recipe is absent from the upstream OpenWrt feed.

| Recipe | Role | Purpose |
| --- | --- | --- |
| [`python-salt`](openwrt/feed/python-salt/Makefile) | Main package recipe | Builds the Salt runtime, minion, and router add-ons listed below. |
| [`python-looseversion`](openwrt/feed/python-looseversion/Makefile) | Build and runtime dependency | Version comparison during the build and on the router. |
| [`python-importlib-metadata`](openwrt/feed/python-importlib-metadata/Makefile) | Host build dependency | Python distribution metadata for building Salt. |
| [`python-zipp`](openwrt/feed/python-zipp/Makefile) | Host build dependency, indirect | ZIP helpers required by host `importlib-metadata`. |
| [`rust`](openwrt/feed/rust/Makefile) | Build tool, Omnia only | Pinned Rust host compiler and ARM target libraries for native Python dependencies. The x86_64 build uses upstream Rust. |

Host build dependencies run on the build computer. Their recipes also define
Python runtime packages, but `python3-importlib-metadata` and `python3-zipp`
are not required by the Salt runtime in this build. Rust is not installed on
the router.

## Salt packages

The `python-salt` recipe produces these six installable packages:

| Package | Required? | Purpose |
| --- | --- | --- |
| `python3-salt` | Yes | Shared Salt Python runtime. |
| `salt-minion` | Yes | `salt-minion`, `salt-call`, configuration, and procd init script. |
| `minion-opkg` | Optional | OpenWrt package management through `pkg.*` and package states. |
| `minion-uci` | Optional | UCI execution functions, UCI states, and declarative `wrt_config` states. |
| `minion-service` | Optional | Service management through procd and ubus. |
| `minion-openwrt` | Optional | Metapackage that installs the minion and all three router add-ons. |

The installation example below uses the complete profile. For a minimal
installation, select `python3-salt`, `salt-minion`, and their dependencies;
add only the integrations you need and omit `minion-openwrt` when omitting
an add-on. Add-ons must match the base Salt package release.

## Build & deploy

### 1. Build - build computer

Use Linux or WSL with Docker, Git, curl, sha256sum, and Python 3. Run the build
from the root of this package repository; the test repository is not required.

| Target | System | Build command | Package output |
| --- | --- | --- | --- |
| Turris Omnia | Turris OS 9.1.1, ARM Cortex-A9 | `bash build-omnia.sh` | `openwrt/output/omnia/` |
| x86_64 | OpenWrt 24.10.8 | `bash build-x86_64.sh` | `openwrt/output/x86_64/` |

The optional first argument sets parallel jobs (1-64, default 4), for example
`bash build-omnia.sh 8`. SDK volumes are persistent and separate for each
target. The first x86_64 build also bootstraps Rust/LLVM and takes substantially
longer than subsequent builds.

Outputs include IPKs, `install-local.txt`, `install-all.txt`, checksums, build
logs, and `build-manifest.json` with package versions, dependencies, and build
identity. Downloads are cached in `.cache/`.
`SALT_BUILD_CACHE` and `SALT_BUILD_OUTPUT` can override these directories;
relative overrides are resolved from the caller's working directory.

### 2. Copy packages - build computer

First check the router's system, package architecture, and free space:

```sh
ssh root@192.168.1.1 'cat /etc/os-release; opkg print-architecture; df -h /overlay /tmp'
```

Select the matching build output and copy the local packages listed in its
manifest. Run this block in Bash from the package repository root:

```bash
target=omnia                       # or x86_64
router=root@192.168.1.1
output="openwrt/output/$target"

(
    set -e
    ssh "$router" 'mkdir -p /tmp/salt-ipk'
    packages=()
    while IFS= read -r ipk; do
        [ -z "$ipk" ] || packages+=("$output/$ipk")
    done < "$output/install-local.txt"
    [ "${#packages[@]}" -gt 0 ]
    scp "${packages[@]}" "$output/install-local.txt" "$router:/tmp/salt-ipk/"
)
```

`install-local.txt` selects the local feed packages, including any needed
local Python dependencies. Existing system dependencies come from the router's
configured feeds. Do not install every exported IPK with `opkg install *.ipk`:
`install-all.txt` describes the full dependency export for build and test use.

### 3. Configure TCP - master

On a computer with Salt master installed, create
`/etc/salt/master.d/tcp.conf` as root:

```sh
mkdir -p /etc/salt/master.d
cat > /etc/salt/master.d/tcp.conf <<'EOF'
transport: tcp
publish_port: 4505
ret_port: 4506
EOF
systemctl restart salt-master
```

The restart command assumes a systemd host. The router must be able to reach
the master's **TCP ports 4505 and 4506**.

This example configures a dedicated TCP master. For a master that serves both
TCP and ZeroMQ minions, see the
[installation guide](https://saltstack-wrt.pages.dev/): the test/playground
configuration uses TCP ports 4605/4606 instead.

### 4. Configure the minion - router

Before installing the packages, connect to the router and create its local
configuration as root. Replace the master address and choose a unique minion ID:

```sh
mkdir -p /etc/salt/minion.d
cat > /etc/salt/minion.d/local.conf <<'EOF'
master: 192.168.1.10
id: openwrt-test
transport: tcp
master_port: 4506
EOF
```

This file overrides the shipped defaults, which use request port 4606 for
the test repository's mixed-transport master. Keep `transport: tcp` and match
`master_port` to your master.

### 5. Install and start - router

For an upgrade, stop the existing minion before installing:
`/etc/init.d/salt-minion stop`. Install the base packages and all installed
add-ons together so their exact release dependencies are updated consistently.

On the router, install the transferred packages in one opkg call:

```sh
(
    set -e
    cd /tmp/salt-ipk
    opkg update
    set --
    while IFS= read -r ipk; do
        [ -z "$ipk" ] || set -- "$@" "$ipk"
    done < install-local.txt
    [ "$#" -gt 0 ]
    opkg install "$@"
)
```

Continue only if installation succeeds. Do not bypass dependency checks with
force options.

OpenWrt enables and starts the minion during a fresh installation. Turris OS
uses `/etc/services_wanted` and its normal service policy, so an unlisted,
disabled service can remain disabled. After installation, check the local
runtime, enable the service, and restart it to load the configuration and add-ons:

```sh
salt-call --local test.ping
/etc/init.d/salt-minion enable
/etc/init.d/salt-minion restart
/etc/init.d/salt-minion status
```

### 6. Accept the key and verify - router and master

**On the router**, read the minion key fingerprint:

```sh
salt-call --local key.finger
```

**On the master**, inspect the key for the same minion ID:

```sh
salt-key -f openwrt-test
```

Compare the fingerprints. If they match, accept that key and test the connection:

```sh
salt-key -a openwrt-test
salt openwrt-test test.ping
```

A successful ping returns `True`. For connection problems, inspect `logread`
and `/var/log/salt/minion` on the router.

## Documentation

Read the **[project documentation](https://saltstack-wrt.pages.dev/)** for the
installation guide and Salt state examples.

- [opkg](docs/opkg.md): package management.
- [UCI](docs/uci.md): configuration with an explicit commit step.
- [wrt_config](docs/wrt-config.md): declarative configuration with automatic commit.
- [service/procd](docs/service.md): service management and configuration reloads.
- [Documentation tools](docs/documentation.md): build or preview the documentation locally.

Salt is packaged as adjacent `.pyc` bytecode with unused integrations removed.
Source inspection such as `baredoc` and source lines in tracebacks are unavailable;
imported docstrings are retained. Recipes, pruning rules, and patches are in
[python-salt](openwrt/feed/python-salt/).

Playgrounds, regression tests, and detailed packaging and verification reports
live in the companion [saltstack-wrt-tests](https://github.com/ja-pa/saltstack-wrt-tests)
repository. It pins this package repository as a submodule and is not required
to build the packages. Access to private repositories requires GitHub authorization.
