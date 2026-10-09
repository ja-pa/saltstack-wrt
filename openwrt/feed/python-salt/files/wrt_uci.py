"""UCI named sections and options, with guarded, explicitly committed deltas.

The journal owns a complete pending file, not individual lines. It detects
pre-existing/intervening changes but cannot lock out external LuCI writers.
"""
import contextlib
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import tempfile

import salt.utils.path
from salt.exceptions import CommandExecutionError, SaltInvocationError

_CONFDIR = Path('/etc/config')
_OVERRIDES = Path('/var/run/uci')
_SAVEDIR = Path('/tmp/.uci')
_IDENT = re.compile(r'[A-Za-z0-9_]+\Z')
_CONFIG = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_-]*\Z')
_MASK = '<redacted>'



def _identifier(value, config=False):
    if not isinstance(value, str) or not (_CONFIG if config else _IDENT).fullmatch(value):
        raise SaltInvocationError('Invalid UCI identifier; anonymous selectors are unsupported')
    return value


def _value(value):
    if not isinstance(value, str) or any(c in value for c in ('\x00', '\r', '\n')):
        raise SaltInvocationError('UCI values must be strings without NUL, CR or LF')
    return value


def _quote(value):
    return "'" + value.replace("'", "'\\''") + "'"


def _parse(text):
    """Parse canonical `uci -N export`; do not split quoted multiline values."""
    records, buffer, quote, escaped = [], [], None, False
    for char in text:
        if char == '\n' and quote is None and not escaped:
            records.append(''.join(buffer))
            buffer = []
            continue
        buffer.append(char)
        if escaped:
            escaped = False
        elif char == '\\' and quote != "'":
            escaped = True
        elif quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
    records.append(''.join(buffer))
    sections, current = [], None
    try:
        if quote or escaped:
            raise ValueError()
        for record in records:
            tokens = shlex.split(record, comments=True, posix=True)
            if not tokens:
                continue
            if tokens[0] == 'package' and len(tokens) == 2:
                continue
            if tokens[0] == 'config' and len(tokens) in (2, 3):
                current = {'name': tokens[2] if len(tokens) == 3 else None,
                           'type': tokens[1], 'options': {}}
                if current['name'] is not None and any(s['name'] == current['name'] for s in sections):
                    raise ValueError()
                sections.append(current)
            elif current is not None and tokens[0] in ('option', 'list') and len(tokens) == 3:
                if tokens[0] == 'option':
                    current['options'][tokens[1]] = tokens[2]
                else:
                    current['options'].setdefault(tokens[1], []).append(tokens[2])
            else:
                raise ValueError()
    except (ValueError, AttributeError):
        raise CommandExecutionError('Unable to parse UCI export (values suppressed)') from None
    return {'sections': sections}


def _bytes(path, required=False):
    try:
        mode = path.lstat().st_mode
        if not stat.S_ISREG(mode):
            raise CommandExecutionError('UCI files must be regular files, not symlinks')
        return path.read_bytes()
    except FileNotFoundError:
        if required:
            raise CommandExecutionError('UCI configuration does not exist') from None
        return b''


def _hash(value):
    return hashlib.sha256(value).hexdigest()


class Backend:
    def __init__(self, opts, functions, confdir=_CONFDIR, overrides=_OVERRIDES, savedir=_SAVEDIR):
        self.opts, self.functions = opts, functions
        self.confdir, self.overrides, self.savedir = confdir, overrides, savedir

    def _run(self, arguments, stdin=None):
        try:
            result = self.functions['cmd.run_all'](
                [salt.utils.path.which('uci'), *arguments], stdin=stdin,
                python_shell=False, output_loglevel='quiet', stdin_raw_newlines=True,
                env={'LC_ALL': 'C'})
        except Exception:
            raise CommandExecutionError('Unable to execute UCI (details suppressed)') from None
        # UCI batch returns zero even when a command fails. Never trust it alone.
        if result['retcode'] or result.get('stderr', '').strip():
            raise CommandExecutionError('UCI command failed (diagnostic values suppressed)')
        return result.get('stdout', '')

    def _snapshot(self, config):
        base = [_hash(_bytes(self.confdir / config, required=True)),
                _hash(_bytes(self.overrides / config))]
        delta = _bytes(self.savedir / config)
        return {'base': base, 'delta': _hash(delta), 'pending': bool(delta)}

    def _read(self, config):
        _identifier(config, config=True)
        self._snapshot(config)
        return _parse(self._run(['-N', 'export', config]))

    def _directory(self):
        return Path(self.opts['cachedir']) / 'uci'

    def _secure_directory(self):
        directory = self._directory()
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory.is_symlink() or directory.stat().st_uid != os.geteuid():
            raise CommandExecutionError('Unsafe UCI ownership directory')
        directory.chmod(0o700)
        return directory

    @contextlib.contextmanager
    def _lock(self, config, test=False):
        directory = self._directory()
        # A dry run never creates cache entries. If a writer already has a lock,
        # use that inode; otherwise the dry run is only an observational snapshot.
        path = directory / (config + '.lock')
        if test and not path.exists():
            yield
            return
        if not test:
            self._secure_directory()
        descriptor = os.open(path, os.O_RDWR | os.O_NOFOLLOW | (0 if test else os.O_CREAT), 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            os.close(descriptor)

    def _journal(self, config):
        path = self._directory() / (config + '.json')
        raw = _bytes(path)
        if not raw:
            return None
        try:
            record = json.loads(raw)
            if (record['schema'] != 1 or not isinstance(record['base'], list)
                    or len(record['base']) != 2 or not isinstance(record['blocked'], bool)
                    or not isinstance(record['delta'], str)):
                raise ValueError()
            return record
        except (KeyError, ValueError, TypeError):
            raise CommandExecutionError('Invalid UCI ownership journal; manual recovery required') from None

    def _save(self, config, snapshot, blocked):
        directory = self._secure_directory()
        record = {'schema': 1, 'base': snapshot['base'], 'delta': snapshot['delta'], 'blocked': blocked}
        descriptor, name = tempfile.mkstemp(prefix=config + '.', dir=directory)
        try:
            with os.fdopen(descriptor, 'w') as stream:
                json.dump(record, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, directory / (config + '.json'))
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def _guard(self, config):
        snapshot, journal = self._snapshot(config), self._journal(config)
        if journal:
            if journal['blocked']:
                raise CommandExecutionError('UCI configuration is blocked; manual recovery required')
            if journal['base'] != snapshot['base'] or journal['delta'] != snapshot['delta']:
                raise CommandExecutionError('UCI configuration or pending changes changed outside Salt')
        elif snapshot['pending']:
            raise CommandExecutionError('Foreign UCI pending changes; refusing to write or commit')
        return snapshot



def _validate(name, sections, replace, sensitive, test):
    _identifier(name, config=True)
    if any(type(flag) is not bool for flag in (replace, sensitive, test)):
        raise SaltInvocationError('Flags must be booleans')
    if not isinstance(sections, dict):
        raise SaltInvocationError('sections must be a mapping')
    for section, spec in sections.items():
        _identifier(section)
        if not isinstance(spec, dict) or set(spec) - {'type', 'replace', 'options', 'lists', 'absent'}:
            raise SaltInvocationError('Invalid section declaration')
        if 'type' in spec:
            _identifier(spec['type'])
        if 'replace' in spec and (type(spec['replace']) is not bool or (replace and not spec['replace'])):
            raise SaltInvocationError('Invalid section replace flag')
        options, lists, absent = (spec.get(key, default) for key, default in
                                  (('options', {}), ('lists', {}), ('absent', [])))
        if not isinstance(options, dict) or not isinstance(lists, dict) or not isinstance(absent, list):
            raise SaltInvocationError('Invalid option containers')
        for key in list(options) + list(lists) + absent:
            _identifier(key)
        if set(options) & set(lists) or set(absent) & (set(options) | set(lists)):
            raise SaltInvocationError('Conflicting option declarations')
        for value in options.values():
            if _value(value) == '':
                raise SaltInvocationError('Empty scalar is unsupported; use absent')
        for values in lists.values():
            if not isinstance(values, list):
                raise SaltInvocationError('Lists must contain strings')
            for value in values:
                _value(value)


def _plan(name, actual, sections, replace, sensitive):
    wanted = copy.deepcopy(actual)
    commands, changes = [], {}

    def change(path, old, new):
        if old != new or type(old) is not type(new):
            changes[path] = {'old': _MASK if sensitive and old is not None else old,
                             'new': _MASK if sensitive and new is not None else new}

    # UCI @type[index] counts named sections of that type as well.
    counters, addresses = {}, []
    for item in actual['sections']:
        kind = item['type']
        index = counters.get(kind, 0)
        counters[kind] = index + 1
        addresses.append(item['name'] if item['name'] is not None else '@{}[{}]'.format(kind, index))
    if replace:
        for item, address in reversed(list(zip(actual['sections'], addresses))):
            if item['name'] is None or item['name'] not in sections:
                if item['name'] is not None:
                    _identifier(item['name'])
                elif not re.fullmatch(r'[A-Za-z0-9_-]+', item['type']):
                    raise CommandExecutionError('Unsupported anonymous UCI section type')
                path = name + '.' + address
                commands.append('delete ' + path)
                change(path, item['type'], None)
                for key, value in item['options'].items():
                    change(path + '.' + key, value, None)
        wanted['sections'] = [item for item in wanted['sections'] if item['name'] in sections]
    for section, spec in sections.items():
        item = next((s for s in wanted['sections'] if s['name'] == section), None)
        path = name + '.' + section
        if item is None:
            if 'type' not in spec:
                raise SaltInvocationError('Missing section requires type')
            item = {'name': section, 'type': spec['type'], 'options': {}}
            wanted['sections'].append(item)
            commands.append('set ' + path + '=' + _quote(item['type']))
            change(path, None, item['type'])
        elif 'type' in spec and spec['type'] != item['type']:
            raise SaltInvocationError('Existing section has a different type')
        old = copy.deepcopy(item['options'])
        desired = {} if replace or spec.get('replace', False) else copy.deepcopy(old)
        desired.update(spec.get('options', {}))
        desired.update({key: list(value) for key, value in spec.get('lists', {}).items()})
        for key in spec.get('absent', []):
            desired.pop(key, None)
        desired = {key: value for key, value in desired.items() if value != []}
        for key in dict.fromkeys(list(old) + list(desired)):
            before, after = old.get(key), desired.get(key)
            if before == after and type(before) is type(after):
                continue
            _identifier(key)
            target = path + '.' + key
            change(target, before, after)
            if key in old:
                commands.append('delete ' + target)
            if after is not None:
                values = after if isinstance(after, list) else [after]
                commands.extend(('add_list ' if isinstance(after, list) else 'set ') + target + '=' + _quote(v)
                                for v in values)
        item['options'] = desired
    return wanted, commands, changes


def _managed_snapshot(backend, name):
    path = backend.confdir / name
    base = _bytes(path)
    delta = _bytes(backend.savedir / name)
    return {'base': [_hash(base), _hash(_bytes(backend.overrides / name))],
            'delta': _hash(delta),
            'pending': bool(delta), 'exists': path.exists()}


def managed(backend, name, sections, replace=False, sensitive=False, test=False):
    _validate(name, sections, replace, sensitive, test)
    with backend._lock(name, test=test):
        before = _managed_snapshot(backend, name)
        journal = backend._journal(name)
        if journal and (journal['blocked'] or journal['base'] != before['base'] or journal['delta'] != before['delta']):
            raise CommandExecutionError('Ownership journal requires manual recovery')
        if before['pending']:
            raise CommandExecutionError('Existing pending changes must be resolved before wrt_config')
        # An override can hide the persistent file from UCI. Do not claim to
        # have saved /etc/config while observing a different effective file.
        if _bytes(backend.overrides / name):
            raise CommandExecutionError('Runtime UCI override must be resolved before wrt_config')
        actual = backend._read(name) if before['exists'] else {'sections': []}
        wanted, commands, changes = _plan(name, actual, sections, replace, sensitive)
        if not before['exists']:
            changes[name] = {'old': None, 'new': 'created'}
        if _managed_snapshot(backend, name) != before:
            raise CommandExecutionError('Configuration changed while planning')
        if test or not changes:
            return changes
        backend._save(name, before, blocked=True)
        try:
            if _managed_snapshot(backend, name) != before:
                raise CommandExecutionError('Configuration changed before write')
            path = backend.confdir / name
            if not before['exists']:
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                try:
                    os.fchown(descriptor, 0, 0)
                    os.fchmod(descriptor, 0o600)
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                directory_fd = os.open(backend.confdir, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            staged_base = before['base']
            ready = backend._snapshot(name)
            if ready['base'] != staged_base or ready['pending']:
                raise CommandExecutionError('Configuration changed before staging')
            if commands:
                backend._run(['batch'], stdin='\n'.join(commands) + '\n')
            staged = backend._snapshot(name)
            if staged['base'] != staged_base or backend._read(name) != wanted:
                raise CommandExecutionError('Staged configuration verification failed')
            if backend._snapshot(name) != staged:
                raise CommandExecutionError('Configuration changed before commit')
            backend._run(['commit', name])
            after = backend._snapshot(name)
            if (after['pending'] or after['base'][1] != before['base'][1]
                    or backend._read(name) != wanted
                    or _parse(_bytes(path, required=True).decode('utf-8')) != wanted
                    or backend._snapshot(name) != after):
                raise CommandExecutionError('Saved configuration verification failed')
            (backend._directory() / (name + '.json')).unlink()
        except Exception:
            raise CommandExecutionError('Configuration write incomplete; journal blocked, manual recovery required') from None
        return changes
