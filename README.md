# NetBox Ansible Integration

**Date:** 2026-06-12

This repository contains a small NetBox-driven reconciliation prototype. NetBox is treated as the source of truth for the local staging Linux host: child interfaces on a trunk interface define VLANs, IP addresses attached to those child interfaces define Linux interface addresses, and a NetBox IP-address custom field can be used to generate local TCP service simulation configuration.

> **Security note:** the current files still contain a development NetBox token in plaintext. Before using this outside the lab, move secrets into environment variables, Ansible Vault, or another secret manager.

## Current Lab Setup

### NetBox Installation

- NetBox URL: `http://10.100.66.48:8000`
- Superuser: `gijs` / `123GjH#@!`
- API token: `RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ`

### Managed Linux Device

- NetBox device name used by the main reconciler: `staging-server`
- Older helper playbooks/scripts may still refer to device `debian` or device ID `1`.
- Linux trunk interface used by the main reconciler: `enp1s0`
- NetBox model expectation:
  - The Linux host is represented as a NetBox device.
  - `enp1s0` is represented as a parent/trunk interface on that device.
  - VLAN interfaces are represented as child interfaces of `enp1s0`.
  - Each child interface carries one or more tagged VLANs.
  - IP addresses are assigned to the child interfaces in NetBox.
  - The optional IP-address custom field `service_port` is used by the TCP simulator generator. Expected values are comma-separated service descriptors like `tcp-8080,tcp-8443`.

## Architecture Overview

At a high level, the system is a pull-based reconciliation loop:

```text
NetBox API
  |
  | 1. Query device, trunk interface, child VLAN interfaces, IPs, and service custom fields
  v
Ansible control logic on staging-server
  |
  | 2. Compare desired NetBox state with current Linux state
  v
Linux network namespace
  |
  | 3. Create/delete VLAN interfaces and assign IP addresses
  v
Persistence artifacts under /etc/netbox_reconcile
  |
  | 4. Generate reboot-time network script and TCP simulator config
  v
TCP simulator process
     5. Bind configured IP:port combinations and emit simple banners/logs
```

The primary entry point is `netbox_reconcile.yml`. It combines NetBox fetching, Linux VLAN reconciliation, Linux IP assignment, generation of persistence files, and TCP simulator configuration in one playbook.

## NetBox Data Retrieval

### How the current implementation fetches NetBox data

The current implementation does **not** use the standardized NetBox Ansible inventory plugin or NetBox Ansible collection modules for the main reconciliation path. Instead, it directly calls the NetBox REST API from either Ansible `uri` tasks or small Python scripts.

The main playbook, `netbox_reconcile.yml`, performs these API calls:

1. Query `/api/dcim/devices/?name={{ device_name }}` to find the NetBox device.
2. Query `/api/dcim/interfaces/?device_id={{ device.id }}` to get all interfaces on that device.
3. Select `{{ trunk_interface }}` from those interfaces as the parent/trunk interface.
4. Query `/api/dcim/interfaces/?parent_id={{ trunk_if.id }}` to find child interfaces below the trunk.
5. For child interfaces that have IP addresses, query `/api/ipam/ip-addresses/?interface_id=<child-interface-id>` using an Ansible URL lookup.
6. Build derived Ansible facts:
   - `child_interface_data`: child interface name, VLAN IDs, and IP/service data.
   - `nb_vlan_ids`: unique desired VLAN IDs.
   - `nb_ip_data`: desired IP addresses associated with VLAN IDs.

There are also helper scripts:

- `fetch_netbox_data.py` performs a similar REST walk and emits JSON for Ansible or debugging.
- `netbox_api.py` is a small generic API client wrapper.
- `netbox_inventory.py` is a custom dynamic inventory script, but it is not the official NetBox Ansible inventory plugin.

### Relationship to the standardized NetBox Ansible plugin

The standardized approach in the Ansible ecosystem is normally based on the `netbox.netbox` collection, especially the `netbox.netbox.nb_inventory` inventory plugin for inventory construction and the collection's NetBox modules for object CRUD. The current repo is therefore best described as a custom REST-based prototype rather than a plugin-based NetBox Ansible integration.

That is not automatically wrong for a lab prototype: direct REST calls make the data flow explicit and easy to debug. However, it creates more local code to maintain, bypasses built-in inventory grouping and host variable behavior, and makes it harder to scale toward many devices or device roles.

### Migration path toward the standardized NetBox Ansible plugin

A practical migration path would be incremental:

1. **Move secrets and endpoint configuration out of playbooks.** Use environment variables or Ansible Vault for `NETBOX_API`/`NETBOX_TOKEN` before introducing standard plugins.
2. **Introduce `netbox.netbox.nb_inventory` in `ansible.cfg`.** Replace or retire `netbox_inventory.py` once the official inventory plugin can return the Linux host and future network devices with useful hostvars.
3. **Model device roles and platforms in NetBox.** For example, identify Linux hosts separately from Cisco switches by NetBox role/platform so Ansible can target `linux_reconcilers` and `cisco_switches` groups rather than only `localhost`.
4. **Keep the reconciliation transformation explicit at first.** Even with `nb_inventory`, the current logic that converts child interfaces into VLAN IDs and IP/socket configuration can remain in roles or playbook tasks until the data model is stable.
5. **Refactor into roles.** Split the current monolithic playbook into reusable roles such as `netbox_facts`, `linux_vlan_reconcile`, `tcp_simulator`, and later `cisco_c1300_reconcile`.
6. **Replace custom API calls where collection modules are a better fit.** The reconciliation mostly reads NetBox and writes devices, so `nb_inventory` is the first high-value move. NetBox modules are more useful for creating or updating NetBox objects, not necessarily for configuring Linux networking.
7. **Add CI/test fixtures.** Capture example NetBox API JSON and test the transformation from NetBox child-interface data to intended Linux/Cisco configuration.

## Ansible Playbook Structure

### Current playbooks and scripts

- `netbox_reconcile.yml`: main end-to-end reconciliation playbook for VLANs, IPs, persistence files, and TCP service simulator config.
- `netbox_fetch.yml`: earlier/simple VLAN-only reconciliation playbook.
- `assign_vlan_ips.yml`: IP assignment focused playbook with a `test_mode` option.
- `fetch_netbox_data.py`: standalone NetBox data extraction helper.
- `get_vlan_ids.py`: local Linux helper that reads currently configured VLAN subinterfaces from `ip -o link show`.
- `tcp_simulator.py`: local Python TCP listener service that reads JSON service configuration.
- `inventory.ini`: currently only targets `localhost` with a local connection.

### Current targeting model

Today, the actual configuration target is the local Linux system. The inventory contains only:

```ini
localhost ansible_connection=local
```

The main playbook also declares:

```yaml
hosts: localhost
connection: local
gather_facts: false
```

That means the playbook is not yet structured as a multi-device network automation project. It is structured as a local reconciler running on the host that owns the trunk interface. The NetBox device name (`staging-server`) is a variable used for API lookup; it is not currently used as an Ansible inventory host.

### Linux reconciliation flow

`netbox_reconcile.yml` is organized into these logical blocks:

1. **Ensure persistence directory exists.** Creates `/etc/netbox_reconcile`.
2. **Fetch desired state from NetBox.** Reads device, parent trunk interface, child interfaces, VLAN IDs, IP addresses, and `service_port` custom fields.
3. **Inspect current Linux state.** Runs `get_vlan_ids.py` and `ip` commands to discover existing VLAN subinterfaces and interface state.
4. **Reconcile VLAN interfaces.** Creates missing `enp1s0.<vlan>` interfaces, removes extra ones, and brings desired ones up.
5. **Reconcile IP addresses.** Adds desired IP addresses to the VLAN interfaces.
6. **Generate persistence files.** Writes `/etc/netbox_reconcile/network-config.sh` and `/etc/netbox_reconcile/tcp_services.json`.
7. **Attempt to enable persistence service.** Calls Ansible `systemd` for `netbox-network`.
8. **Print a summary.** Shows VLAN/IP actions and generated paths.

### Readiness for adding a Cisco C1300-4G-24P switch

The current code is only partially ready for adding a second device such as a Cisco C1300-4G-24P switch connected to the trunk port.

What is already useful:

- NetBox is already the intended source of truth.
- VLAN IDs are derived from NetBox rather than hardcoded.
- The playbook already distinguishes desired state from current state.
- The concept of a trunk interface and child VLAN interfaces maps well to a downstream switch trunk/access-port design.

What is not ready yet:

- Inventory only contains `localhost`; there is no switch inventory host.
- The main play runs only with `connection: local` and Linux `ip` commands.
- There is no network OS selection, Cisco connection method, credentials, or Cisco collection usage.
- The desired switch state is not modeled separately from the Linux host state.
- The code has no role boundary between “derive NetBox intent” and “apply intent to Linux/Cisco.”

A clean next architecture would split the project into multiple plays or roles:

```text
Play 1: Build intended state from NetBox
  hosts: localhost or an Ansible control node
  output: normalized VLAN/interface/service facts

Play 2: Apply Linux host state
  hosts: linux_reconcilers
  roles:
    - linux_vlan_reconcile
    - tcp_simulator

Play 3: Apply Cisco switch state
  hosts: cisco_switches
  connection: ansible.netcommon.network_cli or httpapi, depending on device support
  roles:
    - cisco_c1300_reconcile
```

For the Cisco C1300-4G-24P specifically, the implementation should first confirm the best supported Ansible connection and collection for that platform/firmware. If it supports standard Cisco IOS-style CLI, the likely direction is `cisco.ios` modules such as `ios_vlans`, `ios_l2_interfaces`, and `ios_config`. If it behaves like Cisco Small Business/CBS/Catalyst 1200/1300 web-managed switches rather than IOS, the project may need CLI templates, REST calls if available, or a vendor-specific approach.

## Persistence Across Reboots

The current design has partial persistence.

### VLAN interfaces and IP addresses

During a playbook run, VLAN interfaces and IP addresses are applied immediately with Linux `ip` commands. Those direct `ip link` and `ip addr` changes are runtime state and are not persistent by themselves.

To make them persistent, `netbox_reconcile.yml` generates this script:

```text
/etc/netbox_reconcile/network-config.sh
```

The generated script recreates the trunk/VLAN interfaces and re-adds IP addresses. The playbook then tries to enable and start a systemd unit named `netbox-network`.

Important limitation: this repository does not currently include a `netbox-network.service` unit file. Unless that unit already exists on the host outside this repository, the generated `network-config.sh` will not automatically run after reboot. In other words, the mechanism is designed for persistence, but the repo does not fully define or install the reboot hook.

### TCP socket/service simulation

The TCP socket information is generated into:

```text
/etc/netbox_reconcile/tcp_services.json
```

`tcp_simulator.py` can read that file and bind the configured IP/port listeners. The simulator also supports reloading configuration on `SIGHUP`.

Important limitation: this repository does not currently include a systemd service unit for the TCP simulator either. Therefore the TCP listener configuration file is persistent on disk, but the simulator process itself will only be persistent across reboots if it is managed by an external service definition not shown in this repo.

### Current persistence summary

| State | Runtime applied now? | Persisted to disk? | Automatically restored by repo-defined service? |
| --- | --- | --- | --- |
| VLAN subinterfaces | Yes | Yes, via generated script | Not fully; unit file missing from repo |
| IP addresses | Yes | Yes, via generated script | Not fully; unit file missing from repo |
| TCP service definitions | Config generated | Yes, via JSON config | Not fully; simulator unit missing from repo |
| TCP listening sockets | Only when simulator is running | No, sockets are process runtime state | Not fully; simulator unit missing from repo |

## Running the Current Playbooks

Run the full reconciler:

```bash
ansible-playbook -i inventory.ini netbox_reconcile.yml
```

Run the IP assignment playbook in test mode:

```bash
ansible-playbook assign_vlan_ips.yml -e "test_mode=true"
```

Run the standalone NetBox fetch helper:

```bash
python3 fetch_netbox_data.py staging-server enp1s0
```

## Scripts

### `netbox_api.py`

Python API client for interacting with NetBox. Can be used as a library or standalone.

```bash
python3 netbox_api.py
```

### `netbox_inventory.py`

Custom dynamic inventory script for Ansible. It fetches devices from NetBox and emits Ansible inventory JSON. This is a local custom implementation, not the standardized `netbox.netbox.nb_inventory` plugin.

```bash
python3 netbox_inventory.py
```

### `fetch_netbox_data.py`

Fetches the current device/trunk/child-interface/IP model from NetBox and prints normalized JSON. This is useful for debugging the NetBox side of the architecture without running Ansible changes.

```bash
python3 fetch_netbox_data.py staging-server enp1s0
```

### `get_vlan_ids.py`

Reads Linux runtime network state and returns VLAN IDs found under a parent interface.

```bash
python3 get_vlan_ids.py enp1s0
```

### `tcp_simulator.py`

Starts TCP listeners based on a JSON configuration file. By default it reads `/etc/netbox_reconcile/tcp_services.json` and logs to `/etc/netbox_reconcile/tcp_connections.log`.

```bash
python3 tcp_simulator.py /etc/netbox_reconcile/tcp_services.json
```

## API Examples

### Get all devices

```bash
curl -H "Authorization: Token RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ" \
  -H "Accept: application/json" \
  http://10.100.66.48:8000/api/dcim/devices/
```

### Get device by ID

```bash
curl -H "Authorization: Token RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ" \
  -H "Accept: application/json" \
  http://10.100.66.48:8000/api/dcim/devices/1/
```

### Create a device

```bash
curl -X POST \
  -H "Authorization: Token RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"name": "new-device", "device_type": 1, "device_role": 1, "site": 1, "status": "active"}' \
  http://10.100.66.48:8000/api/dcim/devices/
```

## Future Work

### Real-time or near-real-time NetBox-triggered reconciliation

The current mechanism is pull-based: Ansible runs, fetches NetBox state, and applies the difference. To react to NetBox changes faster, there are several possible directions.

#### Option 1: Scheduled polling

Run `ansible-playbook -i inventory.ini netbox_reconcile.yml` from systemd timers, cron, AWX schedules, or another scheduler.

- **Pros:** simple, robust, easy to audit, no NetBox customization required.
- **Cons:** not truly real time; changes apply only at the next interval; too-short intervals can create unnecessary API and host load.
- **Good fit:** lab and early production while the data model is still changing.

#### Option 2: NetBox webhooks to an automation endpoint

Configure NetBox webhooks for relevant object changes, such as device interfaces, VLANs, IP addresses, and custom fields. The webhook calls an automation endpoint that starts the reconciliation playbook.

- **Pros:** near-real-time behavior and fewer unnecessary reconciliations.
- **Cons:** requires a secure receiver endpoint, authentication/signature validation, event filtering, queueing, and debouncing to avoid starting many overlapping playbooks.
- **Good fit:** when NetBox becomes the operational source of truth and fast convergence matters.

#### Option 3: AWX/Ansible Automation Platform webhook launch

Use NetBox webhooks to trigger AWX/AAP job templates. AWX can manage credentials, inventory, job logs, RBAC, retries, and concurrency controls.

- **Pros:** production-friendly operational model; better audit history and secret handling than ad-hoc local scripts.
- **Cons:** adds AWX/AAP infrastructure; still needs careful event filtering and inventory design.
- **Good fit:** teams that already operate AWX/AAP or need multi-device orchestration including the future Cisco switch.

#### Option 4: Local lightweight event receiver plus queue

Run a small local service that receives NetBox webhook events, writes them to a queue, coalesces rapid changes, and runs the reconciler after a short debounce window.

- **Pros:** can be simple and tailored; avoids running a full automation platform.
- **Cons:** custom operational code to secure, monitor, and maintain; must handle failures and replay.
- **Good fit:** constrained lab/edge deployments where AWX is too heavy but near-real-time behavior is desired.

#### Option 5: NetBox plugin or event rule extension

Implement NetBox-side plugin logic or event rules that directly encode when and how reconciliations should be requested.

- **Pros:** tight integration with NetBox events and object model.
- **Cons:** highest coupling to NetBox internals; more upgrade and testing responsibility.
- **Good fit:** mature environments where reconciliation policy is a core NetBox workflow.

Recommended near-term path: start with scheduled polling or AWX schedules, then add NetBox webhooks once the Linux and Cisco roles are separated and idempotent. Before enabling real-time triggers, add a lock or queue so multiple NetBox edits do not launch overlapping reconciliations against the same host or switch.

### Other improvements

- Add systemd unit files for `netbox-network.service` and `tcp-simulator.service` so persistence is fully defined in this repo.
- Move secrets out of source code.
- Refactor playbooks into roles with a shared normalized NetBox intent data structure.
- Add official NetBox inventory plugin support.
- Add Cisco switch inventory, credentials, connection settings, and a switch-specific role after confirming the correct Ansible collection/connection type for the C1300 firmware.
- Add dry-run/check-mode support for the full reconciler.
- Add tests around NetBox JSON parsing and VLAN/IP/service transformation.
