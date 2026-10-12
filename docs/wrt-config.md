# wrt_config: Save UCI configuration in one state

## Available calls

### wrt_config.apply: Direct execution

```python
wrt_config.apply(name, sections, replace=False, sensitive=False, test=False)
```

Use this function for a direct change or preview.
It returns a change dictionary. It returns `{}` if the configuration already matches.
An invalid declaration or failed operation raises an exception.

Preview a change to the existing `dhcp.lan` section:

```sh
salt openwrt-test wrt_config.apply dhcp \
  'sections={"lan":{"options":{"limit":"50"}}}' test=True
```

To save the change, omit `test=True`:

```sh
salt openwrt-test wrt_config.apply dhcp \
  'sections={"lan":{"options":{"limit":"50"}}}'
```

### wrt_config.managed: Salt state

```python
wrt_config.managed(name, sections, replace=False, sensitive=False)
```

Use this state to maintain configuration through an SLS file.
It changes, verifies, and commits the declared values in one operation.
Use `state.apply ... test=True` to preview the state.
The next example shows a complete SLS file.

### Parameters

| Parameter | Meaning |
| --- | --- |
| `name` | Required configuration name. For example, `dhcp` selects `/etc/config/dhcp`. |
| `sections` | Required mapping of named sections and their declared values. |
| `replace` | Defaults to `false`. When true, removes undeclared sections and options. See [replacement limits](#declaration-rules). |
| `sensitive` | Defaults to `false`. When true, redacts non-null values in reported changes. |
| `test` | Execution function only. Defaults to `false`. When true, plans changes without writing them. |

Use your minion ID instead of `openwrt-test` in all commands.

## Example: Change the LAN DHCP pool

This example manages the existing `lan` section in `/etc/config/dhcp`.
It changes the pool start, address count, and lease time.
It preserves the interface setting, other options, and other sections.
The fields follow the [OpenWrt DHCP configuration](https://github.com/openwrt/openwrt/blob/openwrt-24.10/package/network/services/dnsmasq/files/dhcp.conf).

Create `/srv/salt/lan-dhcp.sls` on the master:

```yaml
lan-dhcp:
  wrt_config.managed:
    - name: dhcp
    - sections:
        lan:
          type: dhcp
          options:
            start: '100'
            limit: '50'
            leasetime: '12h'
```

`name: dhcp` selects `/etc/config/dhcp`. It is not a file path.
`lan` is the named section. Its existing type must be `dhcp`.
Quote UCI values, including numbers, so that YAML reads them as strings.

If the existing section uses `interface 'lan'`, its saved data include:

```uci
config dhcp 'lan'
    option interface 'lan'
    option start '100'
    option limit '50'
    option leasetime '12h'
```

Other existing options remain. UCI can change spacing, quoting, and comments.
Use pool values suitable for your LAN subnet.

### Preview and apply

Replace `openwrt-test` with your minion ID:

```sh
salt openwrt-test state.apply lan-dhcp test=True
salt openwrt-test state.apply lan-dhcp
```

The preview does not write files or pending changes.
Apply saves and verifies the declared values.
A repeated matching run returns empty `changes` and does not commit again.
Saving the file alone does not apply the settings to dnsmasq.

### Reload a service after a saved change

Add this state to the same SLS file:

```yaml
apply-lan-dhcp:
  service.running:
    - name: dnsmasq
    - reload: true
    - require:
      - wrt_config: lan-dhcp
    - watch:
      - wrt_config: lan-dhcp
```

This requires `minion-service` and a procd dnsmasq script with `reload_service()`.
If dnsmasq is running, a saved change requests a reload.
If dnsmasq is stopped, Salt starts it.
If the configuration state fails, `require` prevents the service step.
An unchanged configuration does not request a reload.

A failed reload does not undo the commit.
An init script's reload handler can restart processes internally.
Existing automatic UCI triggers can also cause an additional reload.
See [service/procd](service.md#status-timeouts-and-reload-limits) for these limits.

## Use pillar for values that differ between routers

Assign this pillar data to the minion:

```yaml
lan_dhcp:
  start: '100'
  limit: '50'
  leasetime: '12h'
```

In the `lan-dhcp` state, replace the `options` mapping with:

```yaml
options:
  start: {{ salt['pillar.get']('lan_dhcp:start') | tojson }}
  limit: {{ salt['pillar.get']('lan_dhcp:limit') | tojson }}
  leasetime: {{ salt['pillar.get']('lan_dhcp:leasetime') | tojson }}
```

The `tojson` filter keeps the rendered YAML valid.
All three pillar values must be strings and must exist.
For secrets, add `sensitive: true` at the same level as `name` and `sections`.
This also redacts removed values.
It does not encrypt files or redact Salt pillar, rendered states, or job caches.

## Declaration rules

Put related changes for one configuration in one `wrt_config.managed` state.
Use the following fields inside each named section:

| Field | Use |
| --- | --- |
| `type` | Required for a new section. Optional for an existing section. Cannot change an existing type. |
| `options` | Set scalar options to nonempty strings. |
| `lists` | Replace complete lists of strings. Order and duplicates are significant. `[]` removes an option; `['']` keeps one empty item. |
| `absent` | Remove the listed option names. |
| `replace: true` | Remove undeclared options from this section. |

Do not declare the same option in `options`, `lists`, and `absent`.
Null values, numeric values, boolean values, and unknown fields are rejected.
The [UCI input rules](uci.md#input-rules-and-limits) apply.

**At state level, `replace: true` removes all undeclared sections and options,
including anonymous sections.** Do not use it for the partial DHCP example above.
It would remove the anonymous dnsmasq section in a standard configuration.
A nested `replace: false` is invalid in that mode.

By default, `sections: {}` preserves existing data. With state-level replacement,
it removes all sections. The module can create a missing configuration file with
owner `root:root` and mode `0600`. It keeps existing file permissions.
It can preview a missing file, but it cannot declare anonymous sections.

## Requirements and recovery

Install `minion-uci` on the minion. The master uses standard Salt.
Use [UCI requirements](uci.md#requirements) for module availability and permissions.
The examples require an existing `dhcp` configuration with a named `lan` section.
The module does not reload services automatically.

Resolve pending UCI changes before you apply the state.
This includes changes prepared through `uci.*` by the same minion.
A nonempty `/var/run/uci/<name>` override must also be resolved first.

On success, the state reports verified saved changes.
On failure, it returns `result: false` and empty `changes`.
**Empty `changes` after a failure does not mean that the files are unchanged.**
There is no automatic rollback. A failed write can leave the ownership record blocked.

Use the [UCI recovery procedure](uci.md#pending-changes-and-recovery).
For this example, the default record is `/var/cache/salt/minion/uci/dhcp.json`.
Verify the saved file, pending changes, and override before removing only that record.
Reverting pending changes does not undo a completed commit.

Salt locks its own operations. It cannot lock out LuCI or Foris.
Several configuration states do not form one atomic transaction.
