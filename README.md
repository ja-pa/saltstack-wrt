![OpenWrt + Salt Project: Salt minion for OpenWrt. Unofficial community package.](docs/assets/salt-minion-openwrt.png)

# Salt minion packages for OpenWrt and Turris OS

Experimental Salt 3008.3 minion packages, router integrations, and SDK build
helpers. The packages require **TCP transport**, which worked well in our
verification. Run the Salt master on a separate computer.

## Package definitions

Local recipes in [openwrt/feed](openwrt/feed/):

| Recipe | Role | Purpose |
| --- | --- | --- |
| [`python-salt`](openwrt/feed/python-salt/Makefile) | Main recipe | Salt runtime, minion, and router add-ons. |
| [`python-looseversion`](openwrt/feed/python-looseversion/Makefile) | Build + runtime dependency | Version comparison. |
| [`python-importlib-metadata`](openwrt/feed/python-importlib-metadata/Makefile) | Host build dependency | Python distribution metadata. |
| [`python-zipp`](openwrt/feed/python-zipp/Makefile) | Indirect host build dependency | ZIP helpers for `importlib-metadata`. |
| [`rust`](openwrt/feed/rust/Makefile) | Build tool, Omnia only | Rust compiler and ARM target libraries. x86_64 uses upstream Rust. |

## Salt packages

| Package | Purpose |
| --- | --- |
| `python3-salt` | Required Salt Python runtime. |
| `salt-minion` | Required minion, `salt-call`, configuration, and init script. |
| `minion-opkg` | Optional package management through `pkg.*`. |
| `minion-uci` | Optional UCI functions, states, and `wrt_config`. |
| `minion-service` | Optional procd/ubus service management. |
| `minion-openwrt` | Metapackage for the minion and all three add-ons. |

## Build & deploy

### 1. Build (build computer)

Requires Linux/WSL, Docker, Git, curl, sha256sum, and Python 3.
Run from this repository's root:

| Target | System | Command | Output |
| --- | --- | --- | --- |
| Omnia | Turris OS 9.1.1, ARM Cortex-A9 | `bash build-omnia.sh` | `openwrt/output/omnia/` |
| x86_64 | OpenWrt 24.10.8 | `bash build-x86_64.sh` | `openwrt/output/x86_64/` |

An optional argument sets parallel jobs (default 4): `bash build-omnia.sh 8`.
Builds reuse the SDK cache; the first x86_64 build also compiles Rust/LLVM.

### 2. Copy packages (build computer)

The examples install all add-ons and the local `python3-looseversion` dependency.
Choose the target and architecture matching your router; keep one package
version per target in the source and destination directories.

```sh
router=root@192.168.1.1
target=omnia                       # x86_64 for OpenWrt x86_64
arch=arm_cortex-a9_vfpv3-d16         # x86_64 for OpenWrt x86_64

cd "openwrt/output/$target"
ssh "$router" 'mkdir -p /tmp/salt-ipk'
scp python3-looseversion_*_${arch}.ipk \
    python3-salt_*_${arch}.ipk \
    salt-minion_*_${arch}.ipk \
    minion-opkg_*_${arch}.ipk \
    minion-uci_*_${arch}.ipk \
    minion-service_*_${arch}.ipk \
    minion-openwrt_*_${arch}.ipk \
    "$router:/tmp/salt-ipk/"
```

### 3. Configure salt-master (master computer)

Create **`/etc/salt/master.d/tcp.conf`** as root (create the directory if needed):

```yaml
transport: tcp
publish_port: 4505
ret_port: 4506
```

Restart the master (systemd) and allow the router to reach TCP ports **4505/4506**:

```sh
systemctl restart salt-master
```

### 4. Configure salt-minion (router)

Before installation, create **`/etc/salt/minion.d/local.conf`** as root
(create the directory if needed). Set your master's address and a unique minion ID:

```yaml
master: 192.168.1.10
id: openwrt-test
transport: tcp
master_port: 4506
```

This overrides the packaged default port 4606 with the dedicated TCP master's 4506.

### 5. Install and start (router)

For upgrades, first run `/etc/init.d/salt-minion stop`.
Install matching base and add-on releases together; system dependencies come
from the router's configured feeds.

```sh
arch=arm_cortex-a9_vfpv3-d16         # x86_64 for OpenWrt x86_64
cd /tmp/salt-ipk
opkg update && opkg install \
    python3-looseversion_*_${arch}.ipk \
    python3-salt_*_${arch}.ipk \
    salt-minion_*_${arch}.ipk \
    minion-opkg_*_${arch}.ipk \
    minion-uci_*_${arch}.ipk \
    minion-service_*_${arch}.ipk \
    minion-openwrt_*_${arch}.ipk
```

After successful installation:

```sh
salt-call --local test.ping
/etc/init.d/salt-minion enable
/etc/init.d/salt-minion restart
/etc/init.d/salt-minion status
```

OpenWrt starts the service on fresh installation; Turris follows
`/etc/services_wanted` and may leave it disabled until enabled manually.

### 6. Accept the key and verify

**Router** - read the key fingerprint:

```sh
salt-call --local key.finger
```

**Master** - inspect the same minion's fingerprint:

```sh
salt-key -f openwrt-test
```

If the fingerprints match, accept the key and test:

```sh
salt-key -a openwrt-test
salt openwrt-test test.ping
```

Expected result: `True`. Router logs: `logread` and `/var/log/salt/minion`.

## Documentation

**[Full documentation and examples](https://saltstack-wrt.pages.dev/)**

- Modules: [opkg](docs/opkg.md), [UCI](docs/uci.md), [wrt_config](docs/wrt-config.md), [service/procd](docs/service.md).
- [Documentation tools](docs/documentation.md) for local previews.
- [Salt TCP transport](https://docs.saltproject.io/en/3008/topics/transports/tcp.html).
- [Tests and playgrounds](https://github.com/ja-pa/saltstack-wrt-tests) (private repository).

Packages use pruned `.pyc` bytecode; source inspection and traceback source lines
are unavailable. See the [recipe and patches](openwrt/feed/python-salt/).
Release r10 includes [TCP authentication recovery](openwrt/feed/python-salt/patches/050-tcp-auth-retry-on-disconnect.patch)
after disconnects or master restarts.
