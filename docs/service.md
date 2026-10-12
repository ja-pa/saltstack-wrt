# service: procd service management

The `openwrt_service` provider connects procd and ubus to Salt's standard
`service` interface. Use it to inspect, start, stop, restart, reload, enable,
and disable services on OpenWrt or Turris OS.

Use `service.running` and `service.dead` in state files.
Use `service.start`, `service.status`, and related functions for direct calls.
The master uses standard Salt service states.
It does not need the provider add-on.

This guide describes the local implementation for Salt 3008.3.

## Requirements and provider selection

- Install `minion-service` on the minion.
  The `minion-openwrt` metapackage includes this add-on.
- Install matching releases of the base Salt packages.
- Make sure that procd is running and the ubus `service` object is accessible.
- Make sure that the `ubus` executable is available in `PATH`.
- Set the `os` or `os_family` grain to `OpenWrt`, `TurrisOS`, or `Turris`.
  The provider ignores letter case for this check.
- Give the minion permission to execute service actions.

The package installs `/etc/salt/minion.d/20-openwrt-service.conf`:

```yaml
providers:
  service: openwrt_service
```

This configuration selects the provider explicitly.
The file belongs to the add-on and is removed with it.
Do not edit the package-owned file. Later custom configuration can override it.

After an add-on installation, upgrade, or removal, restart the minion locally:

```sh
/etc/init.d/salt-minion restart
```

Reloading Python modules alone does not load the provider configuration.
Upgrade the base Salt packages and installed add-ons together to keep their releases matched.

## Supported operations

| Operation | Salt function | Behavior |
| --- | --- | --- |
| List service names | `service.get_all` | Lists executable regular init scripts. |
| Check script availability | `service.available`, `service.missing` | Checks whether an executable regular init script exists. |
| Read process status | `service.status` | Returns true if at least one procd instance is running. |
| Start or stop | `service.start`, `service.stop` | Executes the action and waits for the requested procd state. |
| Restart | `service.restart` | Waits for running instances. For a running service, the PID set must change. |
| Reload | `service.reload` | Requires an explicit reload handler and a running service. |
| Enable or disable startup | `service.enable`, `service.disable` | Uses the init script and verifies the resulting enabled status. |
| Read startup status | `service.enabled`, `service.disabled` | Reads the init script's enabled status. |
| Execute a supported action | `service.run` | Accepts only `start`, `stop`, `restart`, `reload`, `enable`, or `disable`. |

Status and lifecycle operations require a procd init script with `USE_PROCD=1`.
The script must be an executable regular file in `/etc/init.d`.
The provider rejects symbolic links, paths, and wildcard names.

The name must start with an ASCII letter, digit, or `_`.
The remaining characters can also include `.` and `-`.
The provider executes the script without a shell command string.

`get_all` can include legacy scripts whose status is not supported.
Script availability alone does not confirm support for lifecycle operations.

## Salt state examples

The examples use the master's `/srv/salt` directory and minion ID `openwrt-test`.
Replace `my-service` with the actual init script name.
For example, `/etc/init.d/my-service` has the service name `my-service`.

### Keep a service running and enabled

Create `/srv/salt/demo-service.sls` with this content:

```yaml
demo-service:
  service.running:
    - name: my-service
    - enable: true
```

Salt starts a stopped service and enables startup.
A repeated matching state returns empty `changes`.

### Keep a service stopped and disabled

Use this state instead of the previous example:

```yaml
demo-service:
  service.dead:
    - name: my-service
    - enable: false
```

Salt stops a running service and disables startup.
Do not declare both running and stopped states for the same service in one run.

### Reload after a file change

Put the required configuration file in `/srv/salt/my-service.conf`.
Use this state file:

```yaml
/etc/my-service.conf:
  file.managed:
    - source: salt://my-service.conf

demo-service:
  service.running:
    - name: my-service
    - reload: true
    - require:
      - file: /etc/my-service.conf
    - watch:
      - file: /etc/my-service.conf
```

Use the actual configuration path expected by the service.
The init script must contain an explicit `reload_service()` handler.

For an already running service, the file change requests a reload.
For a stopped service, `service.running` starts the service.
Without `reload: true`, standard Salt `watch` requests a restart.
The provider does not replace a failed reload with a restart.

### Reload after a UCI commit

The configuration file `/etc/config/salt_uci_demo` and named section `main`
must already exist.
The service must read this configuration and support an explicit reload:

```yaml
demo-value:
  uci.option_present:
    - name: value
    - config: salt_uci_demo
    - section: main
    - value: 'example'

save-demo:
  uci.committed:
    - name: salt_uci_demo
    - require:
      - uci: demo-value

demo-service:
  service.running:
    - name: my-service
    - reload: true
    - require:
      - uci: save-demo
    - watch:
      - uci: save-demo
```

This example requires both `minion-uci` and `minion-service`.
The commit state reports changes only when it saves pending changes.
Use `require` to prevent the service step after a failed commit.
A reload failure does not undo the commit.

For one state that manages and saves configuration, use the
[wrt_config reload example](wrt-config.md#reload-a-service-after-a-saved-change).

The provider does not coordinate automatic procd UCI triggers with Salt reloads.
If the service already reloads through a trigger, an explicit Salt reload can cause
a second reload.

### Preview and apply

```sh
salt openwrt-test state.apply demo-service test=True
salt openwrt-test state.apply demo-service
```

`test=True` does not execute service actions or change startup links.
The preview still needs a working ubus connection to read service status.

## Direct function calls

```sh
salt openwrt-test service.get_all
salt openwrt-test service.available my-service
salt openwrt-test service.missing my-service
salt openwrt-test service.status my-service
salt openwrt-test service.start my-service timeout=15
salt openwrt-test service.stop my-service
salt openwrt-test service.restart my-service
salt openwrt-test service.reload my-service
salt openwrt-test service.enable my-service
salt openwrt-test service.disable my-service
salt openwrt-test service.enabled my-service
salt openwrt-test service.disabled my-service
salt openwrt-test service.run my-service reload
```

Use the same functions locally through `salt-call --local`.
For example, use `salt-call --local service.status my-service`.
Starting an already running service or stopping an already stopped service succeeds
without executing the init action.

## Status, timeouts, and reload limits

The provider reads status from `ubus call service list`.
A successful response without the requested service registration means that the service
is stopped.
A failed command, missing bus object, unavailable socket, or invalid response causes an error.
The provider does not report these failures as a stopped service.

For a service with several instances, one running instance is sufficient for `status=True`.
This does not confirm that all instances are healthy or that the application is ready.
It does not detect a crash loop.

Start, stop, restart, and reload wait for procd status after the init action.
The default wait is 15 seconds.
The `timeout` parameter accepts a number greater than 0 and at most 120 seconds.
Each init command has a separate 30-second limit.
Each ubus query has a 5-second limit.
The `timeout` parameter is therefore not a limit for the complete Salt job.

A restart of a running service requires a different set of running PIDs.
A reload requires a successful init command and a running process.
It does not confirm that the application accepted the new configuration.

Reload fails if the service is stopped or the explicit handler is missing.
The provider does not use rc.common's restart fallback.
The handler itself determines the action and can implement a restart internally.

## Unsupported operations

- Lifecycle management of `salt-minion` itself.
- Status or lifecycle operations for legacy scripts without `USE_PROCD=1`.
- A guarantee that a oneshot process remains running.
- Process-name signatures through `service.status sig=...`.
- Arbitrary init script actions through `service.run`.
- Management of individual procd instances.
- Application readiness checks or crash-loop health checks.
- Automatic coordination of UCI triggers and reloads.

Enable and disable use the init script's startup interface.
They do not infer startup settings from the process state.

## Implementation reference

The provider is `openwrt/feed/python-salt/files/openwrt_service.py`.
Its package configuration is `openwrt/feed/python-salt/files/service-provider.conf`.
It uses standard Salt service states without a custom service state module.
