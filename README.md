# Salt minion packages for OpenWrt and Turris OS

Package definitions and reproducible SDK build helpers for Salt 3008.3.
This repository can be built on its own; it does not depend on the test repository.

## Bytecode packaging

Both Omnia and x86_64 build Salt packages as `3008.3-r10`, using the target
SDK Python and OpenWrt's adjacent `.pyc` layout (`compileall -b`). Sources are
removed after compilation from the runtime and opkg/UCI/procd addons.
The existing prune list and dependencies are unchanged.

Patch 030 allows the Salt loader to discover adjacent bytecode, retaining
source precedence, `__pycache__` support and importlib's bytecode validation.
Patch 040 reads the SSH bootstrap shim from a text resource when its `.py`
source is absent. This one script must remain source text (13,528 bytes),
because Salt transmits it to a remote interpreter rather than importing it;
it is packaged as `ssh_py_shim.txt`. TCP minion startup also imports this code.

Source inspection such as `baredoc` cannot inspect the removed sources, and
tracebacks cannot show their source lines. This is a minion package, not a promise
of compatibility with every source-reading Salt feature or Salt SSH thin
generation. Normal imported docstrings remain in unoptimized bytecode.
Build with the target script below; regression tests are in the companion
test repository (`bash test-omnia.sh` and `bash test-x86_64.sh`).

## TCP authentication recovery (r10)

Patch 050 retries authentication when the master closes the TCP request stream.
Upstream 3008.3 lets `StreamClosedError` escape the authentication coroutine,
leaving its shared future pending and preventing later authentication attempts.
The patch uses the existing retry/backoff and `auth_retries` limit; cancellation
and permanent `SaltClientError` failures keep their existing behavior.
The companion tests exercise a real socket disconnect against installed bytecode,
retry exhaustion and cancellation, then restart and recreate an upstream master
while checking that the ARM daemon PID/starttime and accepted keys remain intact.

The package uses the standard OpenWrt/Turris maintainer scripts. OpenWrt
fresh installs enable and start salt-minion. Turris 9.1.1 enables services
listed in `/etc/services_wanted` and restarts enabled services on live
installs; an unlisted, disabled minion stays disabled. This also controls
activation in Turris image roots. Configure the master before installing
and use the platform's normal service enable/start commands as needed.

| Target | System | Build | Output |
| --- | --- | --- | --- |
| Omnia | Turris OS 9.1.1, ARM Cortex-A9 | `bash build-omnia.sh` | `openwrt/output/omnia/` |
| x86_64 | OpenWrt 24.10.8 | `bash build-x86_64.sh` | `openwrt/output/x86_64/` |

Run from Linux or WSL with Docker, Git, curl, sha256sum and Python 3.
The optional first argument sets parallel jobs (1–64, default 4).
SDK volumes are persistent and separate for each target. The first x86_64
build also bootstraps Rust/LLVM and takes substantially longer.

- `openwrt/feed/`: package recipes, patches and OpenWrt Salt providers.
- `openwrt/docker/`: SDK build image.
- `scripts/`: SDK setup, package export and build metadata.

Outputs include IPKs, dependency-ordered installation manifests, checksums,
build metadata and `build-manifest.json` (schema 2: versions, architectures,
dependencies, sizes, checksums and content-based build identity). SDK downloads are cached
in `.cache/`. Build outputs and caches are ignored by Git.
`SALT_BUILD_CACHE` and `SALT_BUILD_OUTPUT` optionally override these directories;
relative overrides are resolved from the caller's working directory.

Loader verification, size analysis, historical baselines and comparison reports
belong to the test repository. They are not required to build or export packages.

The minion uses TCP transport by default. Optional packages add opkg, UCI and
procd/ubus providers; `minion-openwrt` installs the complete set.

Playgrounds, automated tests, installation instructions and verification reports
live in [saltstack-wrt-tests](https://github.com/ja-pa/saltstack-wrt-tests).
That private repository pins this repository as its `saltstack-wrt/` submodule.
Both repositories require GitHub access when cloning.
