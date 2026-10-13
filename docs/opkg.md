# opkg: Package management

The `opkg` module connects the OpenWrt and Turris OS package manager to Salt's
standard `pkg` interface. Use it to inspect installed packages, update feed
indexes, install missing packages, and remove packages.

Use `pkg.installed` and `pkg.removed` in Salt state files.
Use `pkg.install` and `pkg.remove` for direct function calls.
The `opkg` provider executes these operations on the minion.
It does not provide an `opkg.installed` state.

This guide describes the local implementation for Salt 3008.3.

## Requirements

Make sure that the minion meets these requirements:

- The `minion-opkg` package is installed on OpenWrt or Turris OS.
  The `minion-openwrt` metapackage includes this package.
  The base `salt-minion` package does not require it.
- The `opkg` executable is available in `PATH`.
- The `os` or `os_family` grain is `OpenWrt`, `TurrisOS`, or `Turris`.
  The provider ignores letter case for this check.
- The minion can write to the system and the opkg package database.
- For installation from feeds, the minion has configured feeds and can access them.

Salt loads the provider automatically as `pkg` when these conditions are met.
Manual `providers` configuration is not required.
The master uses standard Salt states. It does not need the opkg add-on.

## Supported operations

| Operation | Salt interface | Behavior |
| --- | --- | --- |
| List installed packages | `pkg.list_pkgs` | Returns package names and installed versions. |
| Read an installed version | `pkg.version` | Returns the installed version. Returns an empty string for a missing package. |
| Update feed indexes | `pkg.refresh_db` | Executes `opkg update` for the configured feeds. |
| Install from feeds | `pkg.install`, `pkg.installed` | Installs missing packages by name. Opkg resolves dependencies. |
| Install an IPK file | `pkg.install`, `pkg.installed` with `sources` | Accepts an absolute path on the minion or a `salt://` URL. See the version limits below. |
| Remove packages | `pkg.remove`, `pkg.removed` | Removes installed packages by exact name. |
| Read an available version | `pkg.latest_version` | Reads feed indexes. Does not update installed packages. |
| Compare versions | `pkg.version_cmp` | Uses `opkg compare-versions`. Returns `-1`, `0`, or `1`. |

Installation by name skips packages that are already installed.
Removal skips packages that are already absent.
In these cases, direct function calls return `{}`.
A state that already meets the requirement returns empty `changes`.

## Salt state examples

Each example is a separate SLS file.
The examples use `/srv/salt` as the master's `file_roots` directory.
The minion ID is `openwrt-test`.
Use the paths and minion ID from your configuration.

The configured feeds must contain `curl` and `jq` for the target system.

### Install one package from a feed

Create `/srv/salt/packages.sls` with this content:

```yaml
curl:
  pkg.installed: []
```

Salt uses the state ID, `curl`, as the package name.
To use a different state ID, specify `name`:

```yaml
http-client:
  pkg.installed:
    - name: curl
```

Both examples make sure that `curl` is installed.
They keep an older version if it is already installed.

### Install several packages and update feed indexes

```yaml
diagnostic-tools:
  pkg.installed:
    - pkgs:
      - curl
      - jq
    - refresh: true
```

Use `refresh: true` to request a feed index update before installation.
Use `refresh: false` to disable the index update for that call.

If you omit `refresh`, `pkg.installed` uses Salt's standard refresh marker.
A successful update clears the marker for later package states in the same run.
A failed update does not clear the marker.

The direct `pkg.install` function defaults to `refresh=False`.

### Install an IPK file from the Salt fileserver

Put the IPK file in `/srv/salt/packages/my-app_1.0-r1_all.ipk`.
Create a state file with this content:

```yaml
my-app:
  pkg.installed:
    - sources:
      - my-app: salt://packages/my-app_1.0-r1_all.ipk
    - refresh: false
```

Salt downloads the file to the minion's cache.
The key `my-app` must match the `Package` field in the IPK metadata.
The file name does not determine the package name.

The `salt://` URL uses `saltenv`, which defaults to `base`.
The IPK file and its dependencies must be suitable for the target system.

Use `refresh: false` if the minion has the necessary indexes or all dependencies
are already installed. Otherwise, use `refresh: true`.

**This state checks package presence. It does not check the IPK version.**
If `my-app` is already installed, a newer IPK file on the master does not cause
an automatic update.
The provider does not implement `lowpkg.bin_pkg_info`.
The standard Salt state needs that function to compare installed and IPK versions.

### Install an IPK file stored on the minion

If the file is already on the router, use an absolute path:

```yaml
my-app:
  pkg.installed:
    - sources:
      - my-app: /tmp/my-app_1.0-r1_all.ipk
    - refresh: false
```

The path refers to the **minion**.
The file must exist before Salt executes the state.
The same version limits apply as for a `salt://` source.

### Remove a package

```yaml
remove-jq:
  pkg.removed:
    - name: jq
```

To remove several packages, use `pkgs`:

```yaml
remove-diagnostic-tools:
  pkg.removed:
    - pkgs:
      - curl
      - jq
```

Opkg keeps its dependency checks enabled.
It can refuse to remove a package that another installed package needs.
The provider does not force removal or automatically remove unused dependencies.

### Manage a file after package installation

Use the standard Salt `require` requisite to set the execution order:

```yaml
curl:
  pkg.installed: []

/root/.curlrc:
  file.managed:
    - mode: '0600'
    - contents: |
        connect-timeout = 10
        max-time = 60
    - require:
      - pkg: curl
```

Salt manages the file only after the package state succeeds.
This example manages the complete content of `/root/.curlrc`.

### Preview and apply a state file

For `/srv/salt/packages.sls`, execute these commands on the master.
First, preview the changes:

```sh
salt openwrt-test state.apply packages test=True
```

Then, apply the state file:

```sh
salt openwrt-test state.apply packages
```

`test=True` shows planned changes. It does not install or remove packages.
A preview does not confirm that installation or dependency resolution will succeed.

For installation by name, the preview reads available versions from existing indexes.
The examples above do not update indexes during a preview, even with `refresh: true`.
If you need current indexes, execute `pkg.refresh_db` before the preview.

On the router, use `salt-call state.apply packages` to apply the same state file.
For `salt-call --local state.apply packages`, put the SLS file in the local `file_roots`.
Put any `salt://` IPK files there as well.
The `--local` option does not use the master's fileserver.

## Direct function calls

Use direct function calls for individual operations and diagnostics.
Use state files to maintain a required package configuration.

```sh
salt openwrt-test pkg.list_pkgs
salt openwrt-test pkg.list_pkgs versions_as_list=True
salt openwrt-test pkg.list_pkgs use_context=False
salt openwrt-test pkg.version curl
salt openwrt-test pkg.version curl jq
salt openwrt-test pkg.refresh_db
salt openwrt-test pkg.install curl refresh=True
salt openwrt-test pkg.install 'pkgs=["curl", "jq"]'
salt openwrt-test pkg.remove jq
salt openwrt-test pkg.latest_version curl refresh=False
salt openwrt-test pkg.version_cmp '1.0-r2' '1.0-r10'
```

You can call the same functions locally.
For example, use `salt-call --local pkg.list_pkgs` on the router.

### Package information

`pkg.list_pkgs` returns a dictionary in the form `{name: version}`.
With `versions_as_list=True`, each value is a list of versions.
Use `use_context=False` to read the database again instead of using the cached inventory.

`pkg.version` returns a string for one package name.
For several package names, it returns a dictionary.

`pkg.latest_version` returns the highest available version for a missing package
or a package with an older installed version.
It returns `''` if the package is unknown or already up to date.
For several package names, it returns a dictionary.
The function does not update installed packages.

Version comparison uses opkg's ordering, including release and prerelease suffixes.

### Direct IPK installation

```sh
salt openwrt-test pkg.install 'sources=[{"my-app":"/tmp/my-app_1.0-r1_all.ipk"}]'
salt openwrt-test pkg.install 'sources=[{"my-app":"salt://packages/my-app_1.0-r1_all.ipk"}]' saltenv=base
```

The direct `pkg.install sources=...` call reads the IPK metadata and compares versions.
It skips the file if the installed version is the same.
If the version differs, it passes the file to opkg.
Opkg determines whether the installation succeeds. The provider does not force a downgrade.

The provider checks all source files before it starts installation.

## Unsupported operations and limits

| Operation or option | Limit |
| --- | --- |
| Keep the latest installed version | The `pkg.latest` state is not supported. `pkg.latest_version` only reads version information. |
| Upgrade all packages or the system | `pkg.upgrade` is not implemented. Installation by name skips installed packages. |
| Select a feed version | The provider does not support `version` or version values in `pkgs`. |
| Force reinstallation or a downgrade | The provider does not support `reinstall=True` or force options. |
| Purge packages or hold versions | The provider does not support `pkg.purge`, `pkg.purged`, or version holds. |
| Select a feed for one call | The provider does not support `fromrepo`. It uses the minion's opkg configuration. |
| Disable signature checks | The provider does not support `skip_verify=True`. It uses opkg's verification configuration. |
| Install an IPK from an HTTP URL | `sources` accepts absolute paths and `salt://` URLs. It does not accept `http://` or `https://` URLs. |
| Install another package format | The provider accepts OpenWrt IPK files with an outer tar archive and `control.tar.gz`. It does not accept Debian ar archives. |
| Remove by wildcard or version | Removal requires exact package names without a version selection. |
| Use another root or arbitrary opkg options | The provider does not support `root` or general forwarding of opkg command options. |
| Roll back a failed operation | Operations with several packages are not atomic. The provider does not undo partial changes. |
| Manage Turris Updater policy | Opkg installation and removal do not change the Updater's persistent rules. |

Use either `pkgs` or `sources` in one call. Do not combine them.

Package names must start with an ASCII letter or digit.
The remaining characters can be ASCII letters, digits, `+`, `_`, `.`, or `-`.
The provider executes opkg without a shell.

The provider rejects unsupported options.
However, a standard Salt state can report success without calling the provider
if the requested condition is already met.
That result does not mean that the provider supports the option.

## Changes and errors

After installation or removal, the provider reads the installed package inventory again.
It returns the actual changes, including dependency changes.
For example:

```yaml
jq:
  old: ''
  new: 1.7.1-r1
```

The version is an example. The actual version depends on the target feed.
For removal, `old` contains the previous version and `new` is an empty string.

An opkg error includes the exit code, standard output, error output, and detected
partial changes.
If the first package installs and the second package fails, the first package
can remain installed.
The provider does not automatically undo that change.

An invalid IPK file causes an error before installation.
A `Package` field that differs from the requested name also causes an error
before installation.

## Implementation reference

This guide is based on `openwrt/feed/python-salt/files/opkg.py` in this repository.
