"""Declarative, committed UCI configurations."""
import salt.utils.path
from salt.utils.wrt_uci import Backend, managed as _managed

__virtualname__ = 'wrt_config'


def __virtual__():
    return __virtualname__ if 'uci.show' in __salt__ else (False, 'UCI unavailable')


def apply(name, sections, replace=False, sensitive=False, test=False):
    """Validate, plan and persist one configuration without reloading services."""
    return _managed(Backend(__opts__, __salt__), name, sections, replace, sensitive, test)
