"""OpenWrt rc.common actions and authoritative procd/ubus process status.

Only named procd scripts are supported for lifecycle operations. Readiness of
the application, respawn health and restarting Salt itself are outside the MVP.
"""
import json
import os
from pathlib import Path
import re
import time

import salt.utils.path
from salt.exceptions import CommandExecutionError, SaltInvocationError

__virtualname__ = 'service'
__func_alias__ = {'reload_': 'reload'}
_INIT = Path('/etc/init.d')
_NAME = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]*\Z')
_PROCD = re.compile(r'^\s*(?:export\s+)?USE_PROCD=[\"\']?1[\"\']?\s*(?:#.*)?$', re.M)
_RELOAD = re.compile(r'^\s*(?:function\s+)?reload_service\s*\(\s*\)\s*\{', re.M)


def __virtual__():
    systems = {str(__grains__.get(k, '')).lower() for k in ('os', 'os_family')}
    if not systems.intersection({'openwrt', 'turris', 'turrisos'}):
        return False, 'OpenWrt/Turris only'
    if not salt.utils.path.which('ubus'):
        return False, 'ubus executable missing'
    return __virtualname__


def _path(name, required=True):
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise SaltInvocationError('Invalid service name; paths and patterns are unsupported')
    path = _INIT / name
    # Reject aliases: rc.common uses their target name for ubus, which would
    # otherwise make the requested name disagree with the status query.
    if path.is_symlink():
        raise SaltInvocationError('Service script symlinks are unsupported')
    if not path.is_file() or not os.access(path, os.X_OK):
        if required:
            raise CommandExecutionError('Service init script does not exist or is not executable')
        return None
    return path


def _script(name):
    text = _path(name).read_text()
    if not _PROCD.search(text):
        raise CommandExecutionError('Status/lifecycle of legacy or oneshot services is unsupported; USE_PROCD=1 required')
    return text


def _command(argv, allowed=(0,)):
    result = __salt__['cmd.run_all'](argv, python_shell=False, output_loglevel='quiet',
                                   timeout=30)
    if result.get('retcode') not in allowed or result.get('stderr', '').strip():
        raise CommandExecutionError('Service command failed', info={
            'command': argv, 'retcode': result.get('retcode'),
            'stdout': result.get('stdout', ''), 'stderr': result.get('stderr', '')})
    return result


def _instances(name):
    _script(name)
    # Filtered queries return UBUS_STATUS_NOT_FOUND for an unregistered service,
    # indistinguishable from a missing service object. Query the healthy object
    # first and interpret absence only in its successful complete response.
    result = _command([salt.utils.path.which('ubus') or '/bin/ubus', '-t', '5',
                       'call', 'service', 'list', '{}'])
    try:
        data = json.loads(result['stdout'])
        if not isinstance(data, dict):
            raise ValueError()
        if name not in data:
            return {}  # A successful query with no registration means stopped.
        entry = data[name]
        instances = entry.get('instances', {})
        if not isinstance(instances, dict):
            raise ValueError()
        for instance in instances.values():
            if not isinstance(instance, dict) or type(instance.get('running')) is not bool:
                raise ValueError()
            if instance['running'] and (type(instance.get('pid')) is not int or instance['pid'] <= 0):
                raise ValueError()
        return instances
    except (ValueError, TypeError, AttributeError, KeyError):
        raise CommandExecutionError('Invalid procd service.list response; status is unknown') from None


def status(name, sig=None):
    """True if at least one procd instance runs; bus failures raise an error."""
    if sig is not None:
        raise SaltInvocationError('Process-name signatures are unsupported by procd status')
    return any(item['running'] for item in _instances(name).values())


def _pids(instances):
    return {item['pid'] for item in instances.values() if item['running']}


def _wait(name, running, timeout, previous=None):
    deadline = time.monotonic() + timeout
    while True:
        pids = _pids(_instances(name))
        if bool(pids) == running and (previous is None or pids != previous):
            return True
        if time.monotonic() >= deadline:
            raise CommandExecutionError('Service action accepted but procd did not reach the requested state before timeout')
        time.sleep(min(0.2, max(0, deadline - time.monotonic())))


def _action(name, action, timeout):
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 120:
        raise SaltInvocationError('timeout must be a number in (0, 120] seconds')
    text = _script(name)
    if name == 'salt-minion':
        raise CommandExecutionError('Managing the Salt minion itself is outside this provider MVP')
    before = _pids(_instances(name))
    if action == 'reload' and not _RELOAD.search(text):
        raise CommandExecutionError('Explicit reload_service function required; refusing rc.common fallback')
    if action == 'reload' and not before:
        raise CommandExecutionError('Cannot reload a stopped service')
    if (action == 'start' and before) or (action == 'stop' and not before):
        return True
    _command([str(_path(name)), action])
    return _wait(name, action != 'stop', timeout,
                 previous=before if action == 'restart' and before else None)


def start(name, timeout=15):
    return _action(name, 'start', timeout)


def stop(name, timeout=15):
    return _action(name, 'stop', timeout)


def restart(name, timeout=15):
    return _action(name, 'restart', timeout)


def reload_(name, timeout=15):
    return _action(name, 'reload', timeout)


def run(name, action):
    """Restricted replacement of linux_service.run; no arbitrary init actions."""
    actions = {'start': start, 'stop': stop, 'restart': restart, 'reload': reload_,
               'enable': enable, 'disable': disable}
    if action not in actions:
        raise SaltInvocationError('Unsupported service action')
    return actions[action](name)


def enabled(name, **kwargs):
    return _command([str(_path(name)), 'enabled'], allowed=(0, 1))['retcode'] == 0


def disabled(name):
    return not enabled(name)


def enable(name, **kwargs):
    _command([str(_path(name)), 'enable'])
    if not enabled(name):
        raise CommandExecutionError('Init script did not enable the service')
    return True


def disable(name, **kwargs):
    _command([str(_path(name)), 'disable'])
    if enabled(name):
        raise CommandExecutionError('Init script did not disable the service')
    return True


def available(name):
    return _path(name, required=False) is not None


def missing(name):
    return not available(name)


def get_all():
    """List executable regular init scripts, including unsupported legacy ones."""
    return sorted(p.name for p in _INIT.iterdir() if _NAME.fullmatch(p.name)
                  and not p.is_symlink() and p.is_file() and os.access(p, os.X_OK))
