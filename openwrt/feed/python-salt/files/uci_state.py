"""Idempotent named UCI configuration, with separate explicit commit states."""
from salt.exceptions import CommandExecutionError, SaltInvocationError

__virtualname__ = 'uci'


def __virtual__():
    return __virtualname__ if 'uci.set' in __salt__ else (False, 'UCI execution module unavailable')


def mod_init(low):
    # Dry-run section creation must be visible to subsequent option states,
    # without touching files or leaking a preview into the next highstate.
    __context__['uci.state_preview'] = {}
    return True


def _call(name, function, **kwargs):
    result = {'name': name, 'result': True, 'changes': {}, 'comment': 'UCI is already in the requested state'}
    dry = __opts__.get('test', False)
    try:
        changes = __salt__['uci.' + function](
            test=dry, _preview=__context__.setdefault('uci.state_preview', {}) if dry else None,
            **kwargs)
        result['changes'] = changes
        if changes:
            result['result'] = None if dry else True
            result['comment'] = 'UCI would change' if dry else 'UCI changes applied'
    except (CommandExecutionError, SaltInvocationError, OSError):
        # Do not copy exception text from a lower layer into a state result.
        result.update(result=False, comment='UCI operation refused or failed; check ownership, inputs and configuration')
    return result


def section_present(name, config, section_type):
    return _call(name, 'set_section', config=config, section=name, section_type=section_type)


def option_present(name, config, section, value, sensitive=False):
    return _call(name, 'set', config=config, section=section, option=name, value=value,
                 sensitive=sensitive)


def option_absent(name, config, section, sensitive=False):
    return _call(name, 'delete', config=config, section=section, option=name,
                 sensitive=sensitive)


def list_present(name, config, section, values, sensitive=False):
    return _call(name, 'set_list', config=config, section=section, option=name, values=values,
                 sensitive=sensitive)


def committed(name):
    return _call(name, 'commit', config=name)
