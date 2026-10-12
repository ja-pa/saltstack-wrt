# wrt_config: Configuration with an automatic commit

Use `wrt_config.managed` to manage one UCI configuration in one Salt state.
The state validates the declaration, prepares changes, verifies the result,
and saves the configuration with one commit.

The module is part of `minion-uci`.
It shares the requirements and ownership checks of the [UCI module](uci.md).
The existing `uci.*` functions remain available.
The module does not reload services automatically.

This guide describes the local implementation for Salt 3008.3.

## Supported operations

| Operation | Behavior |
| --- | --- |
| Create a configuration | Creates a missing file in `/etc/config` with owner `root:root` and mode `0600`. |
| Manage selected values | Changes declared options and lists. Preserves other data by default. |
| Create named sections | Requires a section type for each new section. |
| Remove options | Removes options named in `absent` or lists declared as `[]`. |
| Replace section contents | Removes undeclared options in a section with `replace: true`. |
| Replace a complete configuration | Removes undeclared sections and options, including all anonymous sections. |
| Save and verify | Performs one commit when changes are necessary. Verifies saved data and empty pending changes. |
| Preview changes | Plans the result without writing files, pending data, or ownership records. |

## Salt state examples

The examples use the master's `/srv/salt` directory and minion ID `openwrt-test`.
Use the paths and ID from your configuration.
They manage the demonstration configuration `salt_wrt_demo`.

### Manage selected sections and values

Create `/srv/salt/demo-config.sls` with this content:

```yaml
demo-config:
  wrt_config.managed:
    - name: salt_wrt_demo
    - sections:
        main:
          type: settings
          options:
            enabled: '1'
            label: 'My device'
          lists:
            peers: ['server-a', 'server-b']
          absent: [obsolete]
```

The state creates the configuration file if it is missing.
It creates the named section `main` if necessary.
It sets two scalar options and replaces the complete `peers` list.
It removes `obsolete` if that option exists.
It then verifies and commits the changes.

The state ID `demo-config` is independent of the configuration name `salt_wrt_demo`.
Other sections and undeclared options remain unchanged.
An existing `main` section must have type `settings`.
You can omit `type` when the section already exists.

### Use pillar for a sensitive value

Put this data in a pillar assigned to the minion:

```yaml
demo:
  password: 'example-only'
```

Use this state instead of the previous example:

```yaml
demo-config:
  wrt_config.managed:
    - name: salt_wrt_demo
    - sensitive: true
    - sections:
        main:
          type: settings
          options:
            enabled: '1'
            password: {{ salt['pillar.get']('demo:password') | tojson }}
```

Use your secret storage instead of the example password.
The `tojson` filter produces a valid YAML value.
The pillar value must be a nonempty string.

`sensitive: true` redacts all non-null values in the planned and reported changes.
This includes values removed by the state.
It does not encrypt files or redact Salt pillar, rendered states, or job caches.

### Replace the contents of one section

```yaml
demo-config:
  wrt_config.managed:
    - name: salt_wrt_demo
    - sections:
        main:
          type: settings
          replace: true
          options:
            enabled: '1'
```

This declaration keeps only `enabled` in the `main` section.
It removes all other options and lists from that section.
It preserves other sections.

### Replace the complete configuration

```yaml
demo-config:
  wrt_config.managed:
    - name: salt_wrt_demo
    - replace: true
    - sections:
        main:
          type: settings
          options:
            enabled: '1'
```

**Configuration-level `replace: true` removes every undeclared section,
including all anonymous sections.**
It also removes undeclared options from the declared sections.
A nested `replace: false` is not valid with configuration-level replacement.

Use this mode only when the declaration describes the complete required configuration.
The module cannot declare anonymous sections.

### Reload a service after a saved change

Add this state after `demo-config`:

```yaml
demo-service:
  service.running:
    - name: my-service
    - reload: true
    - require:
      - wrt_config: demo-config
    - watch:
      - wrt_config: demo-config
```

Use the actual name of a procd service with an explicit reload handler.
This example requires `minion-service`.
See [service/procd](service.md) for reload requirements and limits.

`require` prevents the service step if the configuration state fails.
For an already running service, `watch` requests a reload after a saved change.
For a stopped service, `service.running` starts the service.
A failed reload does not undo the saved configuration.

### Preview and apply

```sh
salt openwrt-test state.apply demo-config test=True
salt openwrt-test state.apply demo-config
salt openwrt-test state.apply demo-config
```

The preview also works when the configuration file does not yet exist.
It does not write the file, pending data, or ownership records.
The state returns `result: null` when it plans changes.
It returns `result: true` with empty `changes` when the configuration already matches.

A successful application returns `result: true`.
A failed application returns `result: false`.
A repeated matching application does not commit again.

Each state has its own change and commit cycle.
Put related changes for one configuration in one state.

## Interface and declaration rules

State interface:

```python
wrt_config.managed(name, sections, replace=False, sensitive=False)
```

Execution interface:

```python
wrt_config.apply(name, sections, replace=False, sensitive=False, test=False)
```

`name` is a configuration name, not a path.
`sections` is a required mapping of named sections.
The execution function returns a change dictionary and raises an exception on failure.
The state uses Salt's global `test=True` setting for a preview.

For a direct preview, execute:

```sh
salt openwrt-test wrt_config.apply salt_wrt_demo 'sections={"main":{"type":"settings","options":{"enabled":"1"}}}' test=True
```

Omit `test=True` to apply and save the declaration.
The configuration name and declaration must meet the same rules as the state.

| Section field | Accepted value | Behavior |
| --- | --- | --- |
| `type` | A valid UCI section type. | Required for a new section. A different existing type is rejected. |
| `replace` | A boolean. | Removes undeclared options from this section when true. |
| `options` | A mapping of option names to nonempty strings. | Sets scalar values. |
| `lists` | A mapping of option names to lists of strings. | Replaces complete lists, including order and duplicates. |
| `absent` | A list of option names. | Removes the specified options. |

An option cannot appear in more than one of `options`, `lists`, and `absent`.
Unknown fields and invalid declarations are rejected before a write.
Quote numbers and booleans used as UCI values in YAML.
Null values are not accepted.
The [UCI input rules](uci.md#input-rules-and-limits) also apply here.

An empty list, `[]`, removes the option.
A list containing an empty string, `['']`, remains a list with one item.
Lists with one item do not become scalar values.

With partial management, `sections: {}` preserves existing data.
With configuration-level replacement, it removes all sections.
Either mode creates an empty file if the configuration does not exist.
The state does not change an existing file's permissions.

Existing section order is preserved. New sections follow declaration order.
UCI can change formatting and remove comments when it saves the file.

## Pending changes and recovery

Resolve pending changes before you use `wrt_config`.
The module rejects all pending changes, including changes prepared through `uci.*`
by the same minion.
Inspect those changes before you save or discard them.
When migrating from `uci.*`, use a separate `uci.commit` after that inspection.

A nonempty runtime override in `/var/run/uci/<name>` is also rejected.
Resolve the override before you manage the persistent configuration.

The module shares the UCI configuration lock and ownership records.
It blocks the record before its first change.
The record remains blocked until the commit passes verification.
A process failure or write error requires manual recovery.
The module does not perform an automatic rollback.

**A failed state returns empty `changes`. Files or pending data can still have changed.**

Use the [UCI recovery procedure](uci.md#pending-changes-and-recovery) for the affected configuration.
For this example, the default record is
`/var/cache/salt/minion/uci/salt_wrt_demo.json`.
If a new-file operation failed, also check whether the file was created.
Verify the saved data, pending data, and runtime override before you remove the record.
A revert does not undo a completed commit.

The lock serializes Salt operations. It does not lock out LuCI or Foris.
External writes remain possible between checks and operations.
Several configurations do not form one atomic transaction.

## Changes and limits

Changes use `configuration.section.option` keys with `old` and `new` values.
Section creation or removal reports the section type.
File creation has a separate entry under the configuration name.
Removed options are reported separately.
Removed anonymous sections use their original `@type[index]` addresses in the report.
These report addresses are not valid declaration targets.

The module does not rename sections, change existing section types, declare anonymous
sections, reload services, or restore an earlier configuration automatically.
Values are passed through standard input, not process arguments or a shell.
Provider comments and errors do not include configuration values.

## Implementation reference

The execution module is `openwrt/feed/python-salt/files/wrt_config.py`.
The state module is `openwrt/feed/python-salt/files/wrt_config_state.py`.
The shared implementation is `openwrt/feed/python-salt/files/wrt_uci.py`.
