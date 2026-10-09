"""UCI named sections and options, with guarded, explicitly committed deltas.

The journal owns a complete pending file, not individual lines. It detects
pre-existing/intervening changes but cannot lock out external LuCI writers.
"""
import copy
import os
from pathlib import Path
import re

import salt.utils.path
from salt.exceptions import CommandExecutionError, SaltInvocationError

from salt.utils.wrt_uci import Backend, _identifier, _value, _quote, _parse, _bytes, _hash

__virtualname__ = "uci"
_CONFDIR = Path('/etc/config')
_OVERRIDES = Path('/var/run/uci')
_SAVEDIR = Path('/tmp/.uci')
_IDENT = re.compile(r'[A-Za-z0-9_]+\Z')
_CONFIG = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_-]*\Z')
_MASK = '<redacted>'


def __virtual__():
    systems = {str(__grains__.get(key, '')).lower() for key in ('os', 'os_family')}
    if not systems.intersection({'openwrt', 'turrisos', 'turris'}):
        return False, 'UCI is only supported on OpenWrt/Turris'
    return __virtualname__ if salt.utils.path.which('uci') else (False, 'uci not found')


def _run(arguments, stdin=None):
    return _backend()._run(arguments, stdin=stdin)


def _snapshot(config):
    return _backend()._snapshot(config)


def _read(config):
    _identifier(config, config=True)
    _snapshot(config)
    return _parse(_run(['-N', 'export', config]))


def _section(document, name):
    return next((item for item in document['sections'] if item['name'] == name), None)


def configs():
    """List regular configuration files, without reading their values."""
    return sorted(p.name for p in _CONFDIR.iterdir()
                  if _CONFIG.fullmatch(p.name) and p.is_file() and not p.is_symlink())


def show(config, sensitive=False):
    """Return sections with typed scalar/list options; anonymous names are None."""
    document = _read(config)
    if sensitive:
        for section in document['sections']:
            section['options'] = {key: _MASK for key in section['options']}
    return document


def get(config, section, option=None, default=None, sensitive=False):
    """Read a named section or option. Only absence returns the default."""
    _identifier(section)
    if option is not None:
        _identifier(option)
    item = _section(show(config, sensitive=sensitive), section)
    return default if item is None else (item if option is None else item['options'].get(option, default))


def _directory():
    return _backend()._directory()


def _secure_directory():
    return _backend()._secure_directory()


def _lock(config, test=False):
    return _backend()._lock(config, test=test)


def _journal(config):
    return _backend()._journal(config)


def _save(config, snapshot, blocked):
    return _backend()._save(config, snapshot, blocked)


def _guard(config):
    snapshot, journal = _snapshot(config), _journal(config)
    if journal:
        if journal['blocked']:
            raise CommandExecutionError('UCI configuration is blocked; manual recovery required')
        if journal['base'] != snapshot['base'] or journal['delta'] != snapshot['delta']:
            raise CommandExecutionError('UCI configuration or pending changes changed outside Salt')
    elif snapshot['pending']:
        raise CommandExecutionError('Foreign UCI pending changes; refusing to write or commit')
    return snapshot


def _difference(path, old, new, sensitive):
    if old == new and type(old) is type(new):
        return {}
    return {path: {'old': _MASK if sensitive and old is not None else old,
                   'new': _MASK if sensitive and new is not None else new}}


def _apply(config, section, action, value=None, option=None, sensitive=False,
           test=False, _preview=None):
    _identifier(config, config=True)
    _identifier(section)
    if action != 'section':
        _identifier(option)
    with _lock(config, test=test):
        before = _guard(config)
        actual = _read(config)
        preview = _preview.get(config) if test and _preview is not None else None
        wanted = copy.deepcopy(preview['view'] if preview else actual)
        item = _section(wanted, section)
        path = config + '.' + section + ('.' + option if option else '')
        commands = []
        if action == 'section':
            if item and item['type'] != value:
                raise CommandExecutionError('Existing UCI section has a different type')
            old, new = (item['type'] if item else None), value
            if item is None:
                wanted['sections'].append({'name': section, 'type': value, 'options': {}})
                commands.append('set ' + path + '=' + _quote(value))
        else:
            if item is None:
                raise CommandExecutionError('Named UCI section does not exist')
            old = item['options'].get(option)
            new = None if action == 'delete' or (action == 'list' and not value) else value
            if new is None:
                item['options'].pop(option, None)
            else:
                item['options'][option] = copy.deepcopy(new)
            if old is not None:
                commands.append('delete ' + path)
            if new is not None:
                commands.extend(('add_list ' if action == 'list' else 'set ') + path + '=' + _quote(v)
                                for v in (new if action == 'list' else [new]))
        changes = _difference(path, old, new, sensitive)
        if not changes:
            return {}
        if test:
            if _preview is not None:
                _preview[config] = {'view': wanted, 'pending': True}
            return changes
        # Write-ahead blocked marker: a crash or failed readback must fail closed.
        _save(config, before, blocked=True)
        try:
            _run(['batch'], stdin='\n'.join(commands) + '\n')
            after = _snapshot(config)
            if after['base'] != before['base'] or _read(config) != wanted or not after['pending']:
                raise CommandExecutionError('UCI write verification failed; configuration blocked')
            _save(config, after, blocked=False)
        except Exception:
            raise CommandExecutionError('UCI write incomplete; configuration blocked, inspect manually') from None
        return changes


def set_section(config, section, section_type, test=False, _preview=None):
    """Stage a named section, refusing type conflicts."""
    _identifier(section_type)
    return _apply(config, section, 'section', value=section_type, test=test, _preview=_preview)


def set(config, section, option, value, sensitive=False, test=False, _preview=None):
    """Stage a scalar; no implicit commit or reload."""
    if value == '':
        raise SaltInvocationError('UCI treats empty scalar values as deletion; use uci.delete instead')
    return _apply(config, section, 'scalar', value=_value(value), option=option,
                  sensitive=sensitive, test=test, _preview=_preview)


def set_list(config, section, option, values, sensitive=False, test=False, _preview=None):
    """Replace the complete ordered list; an empty list removes the option."""
    if not isinstance(values, list):
        raise SaltInvocationError('UCI list values must be a list of strings')
    for value in values:
        _value(value)
    return _apply(config, section, 'list', value=values, option=option,
                  sensitive=sensitive, test=test, _preview=_preview)


def delete(config, section, option, sensitive=False, test=False, _preview=None):
    """Remove an option only, keeping its section and unrelated options."""
    return _apply(config, section, 'delete', option=option,
                  sensitive=sensitive, test=test, _preview=_preview)


def commit(config, test=False, _preview=None):
    """Commit one configuration only if its complete pending file belongs to Salt."""
    _identifier(config, config=True)
    with _lock(config, test=test):
        before = _guard(config)
        preview = _preview.get(config) if test and _preview is not None else None
        if not (preview['pending'] if preview else before['pending']):
            return {}
        changes = {config: {'old': 'pending', 'new': 'committed'}}
        if test:
            if _preview is not None:
                _preview[config] = {'view': preview['view'] if preview else _read(config),
                                    'pending': False}
            return changes
        expected = _read(config)
        _save(config, before, blocked=True)
        try:
            _run(['commit', config])
            if _snapshot(config)['pending'] or _read(config) != expected:
                raise CommandExecutionError('Commit verification failed')
            (_directory() / (config + '.json')).unlink()
        except Exception:
            raise CommandExecutionError('UCI commit incomplete; configuration blocked, inspect manually') from None
        return changes


def _backend():
    return Backend(__opts__, __salt__, _CONFDIR, _OVERRIDES, _SAVEDIR)
