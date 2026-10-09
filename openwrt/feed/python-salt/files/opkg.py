"""OpenWrt/Turris package management using opkg (no system upgrades).

Supports repository names and OpenWrt tar-format IPKs via ``sources``.
Package states use the upstream Salt pkg state unchanged.
"""
import copy
import io
import os
import re
import tarfile

import salt.utils.data
import salt.utils.path
import salt.utils.pkg
from salt.exceptions import CommandExecutionError, SaltInvocationError

__virtualname__ = "pkg"
_CACHE = "opkg.list_pkgs"
_NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9+_.-]*\Z")


def __virtual__():
    systems = {str(__grains__.get(k, "")).lower() for k in ("os", "os_family")}
    if not systems.intersection({"openwrt", "turrisos", "turris"}):
        return False, "opkg provider is only available on OpenWrt/Turris"
    if not salt.utils.path.which("opkg"):
        return False, "opkg executable not found"
    return __virtualname__


def _name(value):
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise SaltInvocationError("Invalid opkg package name: {!r}".format(value))
    return value


def _options(kwargs):
    # Generic pkg states pass these defaults even when the feature is unused.
    defaults = {"fromrepo": (None, ""), "skip_verify": (False, None),
                "reinstall": (False, None), "update_holds": (False, None),
                "hold": (False, None), "allow_updates": (False, None),
                "ignore_epoch": (None, False), "split_arch": (False, True),
                "normalize": (False, True), "saltenv": None,
                "refresh": (False, None), "version": (None, "")}
    for key, value in kwargs.items():
        if key.startswith("__pub_"):
            continue
        if key not in defaults or (defaults[key] is not None and value not in defaults[key]):
            raise SaltInvocationError("opkg provider does not support {}={!r}".format(key, value))


def _run(args):
    executable = salt.utils.path.which("opkg")
    if not executable:
        raise CommandExecutionError("opkg executable not found")
    return __salt__["cmd.run_all"](
        [executable] + args, python_shell=False, env={"LC_ALL": "C"},
        output_loglevel="trace")


def _error(action, result, changes=None):
    raise CommandExecutionError(
        "opkg {} failed (exit {}): {}".format(
            action, result["retcode"],
            "\n".join(filter(None, (result.get("stdout"), result.get("stderr"))))),
        info={"changes": changes or {}, "retcode": result["retcode"],
              "stdout": result.get("stdout", ""), "stderr": result.get("stderr", "")})


def list_pkgs(versions_as_list=False, use_context=True, **kwargs):
    """Return installed names and versions; never expose the cached dictionary."""
    # These are Debian selection states; opkg has no corresponding inventory.
    if salt.utils.data.is_true(kwargs.get("removed")) or salt.utils.data.is_true(kwargs.get("purge_desired")):
        return {}
    if not salt.utils.data.is_true(use_context) or _CACHE not in __context__:
        result = _run(["list-installed"])
        if result["retcode"]:
            _error("list-installed", result)
        packages = {}
        for line in result.get("stdout", "").splitlines():
            if not line.strip():
                continue
            parts = line.split(" - ", 2)
            if len(parts) < 2 or not _NAME.fullmatch(parts[0]) or not parts[1].strip():
                raise CommandExecutionError("Unexpected opkg list-installed output: {!r}".format(line))
            packages[parts[0]] = [parts[1].strip()]
        __context__[_CACHE] = packages
    packages = copy.deepcopy(__context__[_CACHE])
    if salt.utils.data.is_true(versions_as_list):
        return packages
    return {key: ",".join(value) for key, value in packages.items()}


def version(*names, **kwargs):
    """Return installed versions using Salt's standard scalar/dictionary API."""
    return __salt__["pkg_resource.version"](*names, **kwargs)


def version_cmp(ver1, ver2, ignore_epoch=False):
    """Compare versions using opkg's ordering, returning -1, 0 or 1."""
    values = [str(ver1), str(ver2)]
    if salt.utils.data.is_true(ignore_epoch):
        values = [value.split(":", 1)[-1] for value in values]
    for value in values:
        if value.startswith("-") or not re.fullmatch(r"[0-9A-Za-z.+:~_-]+", value):
            raise SaltInvocationError("Invalid opkg version: {!r}".format(value))
    for operator, comparison in (("=", 0), ("<<", -1)):
        result = _run(["compare-versions", values[0], operator, values[1]])
        if result["retcode"] == 0:
            return comparison
        if result["retcode"] != 1:
            _error("compare-versions", result)
    return 1


def latest_version(*names, refresh=False, **kwargs):
    """Read available versions, required even by pkg.installed test=True.

    This does not enable version-selected installs or the pkg.latest state.
    Return an empty string for missing or already up-to-date packages.
    """
    _options(kwargs)
    for name in names:
        _name(name)
    if salt.utils.pkg.check_refresh(__opts__, refresh):
        refresh_db()
    installed = list_pkgs()
    versions = {}
    for name in names:
        result = _run(["list", name])
        if result["retcode"]:
            _error("list", result)
        best = ""
        for line in result.get("stdout", "").splitlines():
            fields = line.split(" - ", 2)
            if len(fields) >= 2 and fields[0] == name:
                candidate = fields[1].strip()
                if not best or version_cmp(candidate, best) > 0:
                    best = candidate
        if best and name in installed and version_cmp(installed[name], best) >= 0:
            best = ""
        versions[name] = best
    return versions.get(names[0], "") if len(names) == 1 else versions


def refresh_db(**kwargs):
    """Refresh configured feeds; clear the Salt refresh marker only on success."""
    _options(kwargs)
    result = _run(["update"])
    __context__.pop(_CACHE, None)
    if result["retcode"]:
        _error("update", result)
    salt.utils.pkg.clear_rtag(__opts__)
    return True


def _mutate(action, arguments, before):
    try:
        result = _run([action] + arguments)
    finally:
        __context__.pop(_CACHE, None)
    after = list_pkgs(use_context=False)
    changes = salt.utils.data.compare_dicts(before, after)
    if result["retcode"]:
        _error(action, result, changes)
    return changes


def _ipk_identity(path, expected):
    # Read metadata only. Never extract an untrusted archive into the filesystem.
    try:
        with tarfile.open(path) as outer:
            member = next(m for m in outer if m.name.removeprefix("./") == "control.tar.gz")
            if not member.isfile() or member.size > 4 * 1024 * 1024:
                raise ValueError("invalid control archive")
            with tarfile.open(fileobj=io.BytesIO(outer.extractfile(member).read())) as control:
                member = next(m for m in control if m.name.removeprefix("./") == "control")
                if not member.isfile() or member.size > 1024 * 1024:
                    raise ValueError("invalid control record")
                fields = dict(line.split(": ", 1) for line in
                              control.extractfile(member).read().decode().splitlines()
                              if ": " in line and not line.startswith(" "))
        if fields.get("Package") != expected or not fields.get("Version"):
            raise ValueError("Package/Version does not match requested name " + expected)
        return fields["Version"]
    except (OSError, tarfile.TarError, StopIteration, ValueError, UnicodeError) as exc:
        raise CommandExecutionError("Invalid OpenWrt IPK {}: {}".format(path, exc)) from exc


def install(name=None, pkgs=None, sources=None, refresh=False, version=None,
            saltenv="base", normalize=True, **kwargs):
    """Install missing repository packages or explicit local/salt:// IPKs.

    Repository version selection and force/reinstall options are unsupported.
    ``sources`` must map actual package names to OpenWrt tar-format IPKs.
    """
    _options(dict(kwargs, version=version))
    if pkgs is not None and sources is not None:
        raise SaltInvocationError("Use either pkgs or sources, not both")
    source_map = None
    if sources is not None:
        source_map = __salt__["pkg_resource.pack_sources"](sources, normalize=False)
        if not source_map:
            raise SaltInvocationError("sources must contain package-to-IPK mappings")
        for package, path in source_map.items():
            _name(package)
            if not isinstance(path, str) or not (os.path.isabs(path) or path.startswith("salt://")):
                raise SaltInvocationError("IPK sources must be absolute paths or salt:// URLs")
    targets, kind = __salt__["pkg_resource.parse_targets"](
        name, pkgs, sources, saltenv=saltenv, normalize=False)
    if not targets:
        raise SaltInvocationError("No valid package targets supplied")
    if kind == "repository":
        for package, requested_version in targets.items():
            _name(package)
            if requested_version is not None:
                raise SaltInvocationError("opkg repository version selection is unsupported")
    elif kind != "file":
        raise SaltInvocationError("Unsupported package target type")
    # Validate every source before starting any installation.
    identities = []
    if kind == "file":
        identities = [(package, _ipk_identity(path, package), path)
                      for package, path in zip(source_map, targets)]
    if salt.utils.pkg.check_refresh(__opts__, refresh):
        refresh_db()
    before = list_pkgs(use_context=False)
    if kind == "repository":
        arguments = [package for package in targets if package not in before]
    else:
        arguments = [path for package, ver, path in identities if before.get(package) != ver]
    if not arguments:
        return {}
    return _mutate("install", arguments, before)


def remove(name=None, pkgs=None, **kwargs):
    """Remove exact package names, preserving opkg's normal dependency checks."""
    _options(kwargs)
    targets, kind = __salt__["pkg_resource.parse_targets"](name, pkgs, normalize=False)
    if not targets or kind != "repository":
        raise SaltInvocationError("No valid package names supplied")
    for package, requested_version in targets.items():
        _name(package)
        if requested_version is not None:
            raise SaltInvocationError("Version-specific removal is unsupported")
    before = list_pkgs(use_context=False)
    arguments = [package for package in targets if package in before]
    if not arguments:
        return {}
    return _mutate("remove", arguments, before)
