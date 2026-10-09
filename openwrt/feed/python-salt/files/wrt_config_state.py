"""One state owns the complete read/change/commit cycle."""
from salt.exceptions import CommandExecutionError, SaltInvocationError

__virtualname__ = 'wrt_config'


def __virtual__():
    return __virtualname__ if 'wrt_config.apply' in __salt__ else (False, 'wrt_config unavailable')


def managed(name, sections, replace=False, sensitive=False):
    result = {'name': name, 'result': True, 'changes': {},
              'comment': 'Configuration is already saved in the requested state'}
    dry = __opts__.get('test', False)
    try:
        changes = __salt__['wrt_config.apply'](
            name, sections, replace=replace, sensitive=sensitive, test=dry)
        if changes:
            result.update(changes=changes, result=None if dry else True,
                          comment='Configuration would change' if dry else 'Configuration saved and verified')
    except (CommandExecutionError, SaltInvocationError, OSError):
        result.update(result=False, comment='Configuration refused or failed; check inputs, pending changes and ownership journal; incomplete writes require manual recovery')
    return result
