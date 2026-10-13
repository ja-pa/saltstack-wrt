# UCI: Configuration with an explicit commit

The `uci` module reads and changes OpenWrt and Turris OS configuration.
Use it to manage named sections, scalar options, and lists.
Write operations prepare pending changes. A separate commit saves those changes.

Use [wrt_config](wrt-config.md) if one state must manage and save a configuration.
Use `uci` if you need separate change and commit steps.
Neither module reloads a service automatically.

This guide describes the local implementation for Salt 3008.3.

## Requirements

- Install `minion-uci` on the minion. The `minion-openwrt` metapackage includes it.
  The add-on requires matching releases of the base Salt packages.
- Make sure that the `uci` executable is available in `PATH`.
- Set the `os` or `os_family` grain to `OpenWrt`, `TurrisOS`, or `Turris`.
  The module ignores letter case for this check.
- Give the minion permission to read and write the configuration and pending files.
- Create the configuration file in `/etc/config` before you use `uci` write operations.

After an add-on change, reload the minion's modules or restart the minion.
The master uses standard Salt. It does not need the add-on.

## Supported operations

| Operation | Execution function | State |
| --- | --- | --- |
| List configuration names | `uci.configs()` | None. |
| Read a configuration | `uci.show(config, sensitive=False)` | None. |
| Read a named section or option | `uci.get(config, section, option=None, default=None, sensitive=False)` | None. |
| Create a named section | `uci.set_section(config, section, section_type, test=False)` | `uci.section_present` |
| Set a scalar option | `uci.set(config, section, option, value, sensitive=False, test=False)` | `uci.option_present` |
| Replace a complete list | `uci.set_list(config, section, option, values, sensitive=False, test=False)` | `uci.list_present` |
| Remove an option | `uci.delete(config, section, option, sensitive=False, test=False)` | `uci.option_absent` |
| Save one configuration | `uci.commit(config, test=False)` | `uci.committed` |

Write functions return a dictionary of actual changes.
If the requested values already match, they return `{}`.
The functions do not commit or reload a service unless you call the separate operation.

## Read configuration

Execute these commands on the master:

```sh
salt openwrt-test uci.configs
salt openwrt-test uci.show network
salt openwrt-test uci.get network lan ipaddr
salt openwrt-test uci.get network lan
```

Use your minion ID instead of `openwrt-test`.
On the router, use the same functions through `salt-call --local`.

`uci.configs` returns sorted names of regular configuration files.
`uci.show` returns a `sections` list. Each section has `name`, `type`, and `options`.
An anonymous section has `name: null`.
Option values are strings or lists of strings.
A list with one item remains a list.

`uci.get` returns a named section if you omit `option`.
For a missing section or option, it returns `default`, which defaults to `None`.
A missing configuration file or invalid configuration causes an error.

## Salt state examples

The examples use the master's `/srv/salt` directory and minion ID `openwrt-test`.
Use the paths and ID from your configuration.
The configuration `salt_uci_demo` is a demonstration file.

### Create sections and options, then commit

Create `/srv/salt/demo-uci.sls` with this content:

```yaml
/etc/config/salt_uci_demo:
  file.managed:
    - contents: ''
    - replace: false
    - mode: '0600'

demo-section:
  uci.section_present:
    - name: main
    - config: salt_uci_demo
    - section_type: settings
    - require:
      - file: /etc/config/salt_uci_demo

demo-label:
  uci.option_present:
    - name: label
    - config: salt_uci_demo
    - section: main
    - value: 'My device'
    - require:
      - uci: demo-section

demo-peers:
  uci.list_present:
    - name: peers
    - config: salt_uci_demo
    - section: main
    - values: ['server-a', 'server-b']
    - require:
      - uci: demo-section

demo-obsolete:
  uci.option_absent:
    - name: obsolete
    - config: salt_uci_demo
    - section: main
    - require:
      - uci: demo-section

save-demo:
  uci.committed:
    - name: salt_uci_demo
    - require:
      - uci: demo-section
      - uci: demo-label
      - uci: demo-peers
      - uci: demo-obsolete
```

`file.managed` creates an empty file if it is missing.
`replace: false` preserves the contents of an existing file.
The example sets the file mode to `0600`.

After a successful commit, an initially empty `/etc/config/salt_uci_demo`
contains these data:

```uci
config settings 'main'
    option label 'My device'
    list peers 'server-a'
    list peers 'server-b'
```

The `obsolete` option is absent.
If the file already contained other sections or options, those data remain.
UCI can change quoting and spacing. The example shows the saved values, not exact formatting.

Use `name` to separate the state ID from the UCI section, option, or configuration name.
For `uci.section_present`, `name` is the section name.
For option and list states, `name` is the option name.
For `uci.committed`, `name` is the configuration name.

`require` prevents a commit if a required change fails.
The commit state checks for pending changes that belong to Salt.
It does nothing if there are no pending changes.
This also lets a later run save changes left by an interrupted run.

You can add `onchanges` to commit only after a preceding state reports changes.
However, matching pending values report no new changes.
After an interrupted run, `onchanges` can therefore prevent the required commit.
The example uses `require` alone to avoid this condition.

### Set a value from pillar

Put these values in a pillar assigned to the minion:

```yaml
demo:
  label: 'My device'
  password: 'example-only'
```

After the `demo-section` state, use these option states.
Add their IDs to the commit state's `require` list:

```yaml
demo-label:
  uci.option_present:
    - name: label
    - config: salt_uci_demo
    - section: main
    - value: {{ salt['pillar.get']('demo:label') | tojson }}
    - require:
      - uci: demo-section

demo-password:
  uci.option_present:
    - name: password
    - config: salt_uci_demo
    - section: main
    - value: {{ salt['pillar.get']('demo:password') | tojson }}
    - sensitive: true
    - require:
      - uci: demo-section
```

The `tojson` filter keeps quotes and special characters valid in the rendered YAML.
Pillar values must still be strings.
Use your secret storage instead of the example password.

### Preview and apply

For a configuration file that already exists, preview the complete change sequence:

```sh
salt openwrt-test state.apply demo-uci test=True
salt openwrt-test state.apply demo-uci
```

`test=True` does not write configuration, pending data, or ownership records.
The UCI states share an in-memory preview within one state run.
An option state can therefore use a section planned by an earlier UCI state.
Salt resets this preview for the next state run.

The configuration file must exist even during a preview.
`file.managed test=True` does not create a missing file for the later UCI states.
Use [wrt_config](wrt-config.md) to preview a configuration that does not yet exist.

## Direct write operations

These commands require an existing `/etc/config/salt_uci_demo` file:

```sh
salt openwrt-test uci.set_section salt_uci_demo main settings
salt openwrt-test uci.set salt_uci_demo main label 'My device'
salt openwrt-test uci.set_list salt_uci_demo main peers '["server-a", "server-b"]'
salt openwrt-test uci.delete salt_uci_demo main obsolete
salt openwrt-test uci.commit salt_uci_demo
```

Each write prepares pending changes. The final command saves them.
The commit applies to one configuration only.
Use `test=True` on a write function to return its planned changes.
Separate direct calls do not share the state preview.

## Input rules and limits

- Configuration names use ASCII letters, digits, `_`, and `-`.
  The first character cannot be `-`.
- Section names, option names, and section types use ASCII letters, digits, and `_`.
- Anonymous selectors, such as `@rule[0]`, are not valid write targets.
- Configuration, override, and pending paths must be regular files, not symbolic links.
- Scalar values must be nonempty strings. Quote numbers and booleans in YAML.
  Use `uci.option_absent` or `uci.delete` to remove an option.
- List values must be lists of strings. Order and explicit duplicates are significant.
  An empty list removes the option. An empty string is valid inside a list.
- Values can contain spaces, tabs, Unicode, quotes, backslashes, and shell characters.
  Write operations reject NUL, carriage return, and line feed characters.
- An existing section cannot change its type through this interface.

The module does not provide public functions to rename sections, create anonymous
sections, append individual list items, remove complete sections, or revert changes.
It does not provide a global commit or automatic service reload.
Use [service/procd](service.md) for an explicit reload after a successful commit.

## Pending changes and recovery

Salt uses `/etc/config`, `/var/run/uci`, and `/tmp/.uci`.
It records ownership of the complete pending file for each configuration.
The record survives separate Salt jobs and belongs to the minion.

The record is `<cachedir>/uci/<config>.json`.
The default path for this example is `/var/cache/salt/minion/uci/salt_uci_demo.json`.
The record contains hashes and status, not configuration values.
The directory mode is `0700`. The record mode is `0600`.

Before a write or commit, Salt checks the saved file, runtime override, and pending data.
It refuses foreign pending changes, detected external changes, and blocked ownership records.
These checks also apply to a preview.

Salt blocks the ownership record before each write.
It clears the block only after successful verification.
A process failure, UCI error, or failed verification can leave the record blocked.
There is no automatic rollback.

For manual recovery:

1. Stop concurrent edits to the affected configuration.
2. Inspect and back up `/etc/config/salt_uci_demo` and any runtime override.
3. Inspect `uci changes salt_uci_demo` and `uci export salt_uci_demo` locally.
   The output can contain secrets.
4. Decide which pending changes to keep.
   Use `uci commit salt_uci_demo` to save them, or `uci revert salt_uci_demo` to discard them.
5. Verify the saved configuration and confirm that `uci changes salt_uci_demo` is empty.
6. Remove only the ownership record for `salt_uci_demo`.
   Use the actual configured cache directory.
7. Apply the required state again.

A revert does not undo a completed commit.
Do not remove the complete pending directory or all Salt ownership records.

Salt serializes its own operations with a configuration lock.
LuCI, Foris, and other writers do not use that lock.
An external change between a check and a write remains possible.
Operations across several configurations are not one atomic transaction.
UCI can change file formatting and remove comments when it saves data.

## Sensitive values

Use `sensitive=True` for reads or `sensitive: true` for option and list states.
The module replaces returned option values with `<redacted>`.
It passes write values through standard input without a shell.
It suppresses command logging and removes configuration values from provider errors.

This option does not encrypt configuration or pending files.
It does not redact pillar data, rendered state data, or Salt job caches.
A value in a direct CLI call can be recorded before the provider receives it.
Use pillar and `state.apply` for secrets.
Keep secrets out of state IDs and option names.

## Implementation reference

The execution module is `openwrt/feed/python-salt/files/uci.py`.
The state module is `openwrt/feed/python-salt/files/uci_state.py`.
Both use the shared backend in `openwrt/feed/python-salt/files/wrt_uci.py`.
