# NetBox Ansible Integration - Architecture Overview

**Date:** 2026-06-12
**Version:** 2.0 - Expanded Architecture Documentation

This repository contains a comprehensive integration between NetBox (Network Source of Truth) and Ansible for automated network configuration management on Linux systems. The architecture enables dynamic reconciliation of network interfaces, VLANs, IP addresses, and TCP services based on NetBox data.

---

## Table of Contents

1. [Setup](#setup)
2. [Architecture Overview](#architecture-overview)
3. [NetBox Data Extraction Layer](#netbox-data-extraction-layer)
4. [Ansible Playbook Structure](#ansible-playbook-structure)
5. [Persistence Mechanism](#persistence-mechanism)
6. [Real-time Reconciliation](#real-time-reconciliation)
7. [Future Work](#future-work)
8. [Official NetBox Collection Support](#official-netbox-collection-support)
9. [API Examples](#api-examples)
10. [Security Notes](#security-notes)

---

## Setup

### NetBox Installation
- **URL:** `http://10.100.66.48:8000`
- **Superuser:** `gijs` / `123GjH#@!`
- **Version:** NetBox v3.x (assumed based on API endpoints used)

### API Token
- **Token:** `RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ`
- **Permissions:** Full API access (read/write)
- **Scope:** All devices, interfaces, IP addresses, and VLANs

### Registered Devices
- **Device:** `staging-server` (ID: 1) - Primary Linux host
  - **eth0:** Primary network interface (management)
  - **enp1s0:** Trunk port for VLAN tagging
- **Future Device:** `cisco-c1300-4g-24p` - Cisco switch connected to trunk port (planned)

---

## Architecture Overview

The system follows a **Source-of-Truth (SoT) driven architecture** where NetBox serves as the authoritative source for all network configuration. The architecture consists of three main layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                        NetBox (SoT)                               │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────────────────────┐  │
│  │   Devices   │  │ Interfaces  │  │    IP Addresses (IPAM)     │  │
│  └─────────────┘  └─────────────┘  └───────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────────────────────┐  │
│  │   VLANs     │  │ Custom Fields│  │   Services/Applications   │  │
│  └─────────────┘  └─────────────┘  └───────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Data Extraction Layer                            │
│  ┌─────────────────────┐  ┌───────────────────────────────────┐  │
│  │  Python API Client   │  │   Dynamic Inventory Script         │  │
│  │  (netbox_api.py)     │  │   (netbox_inventory.py)            │  │
│  └─────────────────────┘  └───────────────────────────────────┘  │
│  ┌─────────────────────┐  ┌───────────────────────────────────┐  │
│  │  fetch_netbox_data.py │  │   get_vlan_ids.py                 │  │
│  └─────────────────────┘  └───────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Ansible Execution Layer                          │
│  ┌─────────────────────┐  ┌───────────────────────────────────┐  │
│  │  netbox_reconcile.yml│  │   assign_vlan_ips.yml              │  │
│  │  (Full reconciliation)│  │   (IP assignment only)            │  │
│  └─────────────────────┘  └───────────────────────────────────┘  │
│  ┌─────────────────────┐  ┌───────────────────────────────────┐  │
│  │  netbox_fetch.yml     │  │   tcp_simulator.py                │  │
│  │  (VLAN reconciliation)│  │   (TCP service simulation)       │  │
│  └─────────────────────┘  └───────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Target Systems                              │
│  ┌─────────────────────┐  ┌───────────────────────────────────┐  │
│  │   staging-server     │  │   cisco-c1300-4g-24p (future)      │  │
│  │   (Linux/Ansible)    │  │   (Cisco IOS/Ansible)             │  │
│  └─────────────────────┘  └───────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## NetBox Data Extraction Layer

### Current Implementation

The current implementation uses **custom Python scripts** that make direct REST API calls to NetBox. This approach provides full control but does not leverage standardized NetBox-Ansible integrations.

#### Key Components:

1. **`netbox_api.py`** - Core API client library
   - Provides CRUD operations for NetBox objects
   - Uses `requests` library for HTTP calls
   - Hardcoded API token and URL (development pattern)
   - Supports: devices, interfaces, IP addresses

2. **`fetch_netbox_data.py`** - Data aggregation script
   - Fetches complete device configuration from NetBox
   - Extracts:
     - Device metadata
     - Trunk interface configuration
     - Child interfaces (VLAN sub-interfaces)
     - VLAN IDs (from tagged_vlans)
     - IP addresses per child interface
     - Custom fields (service_port for TCP services)
   - Outputs structured JSON for Ansible consumption

3. **`netbox_inventory.py`** - Dynamic Ansible inventory
   - Implements Ansible's dynamic inventory protocol
   - Fetches all devices from NetBox
   - Creates Ansible host groups and variables
   - Can be used as: `ansible -i netbox_inventory.py all -m ping`

4. **`get_vlan_ids.py`** - Local VLAN discovery
   - Parses `ip link show` output
   - Identifies VLAN sub-interfaces (e.g., `enp1s0.2000`)
   - Returns sorted list of VLAN IDs on a given parent interface

### Standardized NetBox-Ansible Plugin Analysis

**Current State:** The implementation does **NOT** use the official NetBox Ansible collection (`netbox.netbox`).

#### Official NetBox Ansible Collection

The [netbox.netbox](https://galaxy.ansible.com/netbox/netbox) collection provides:

```yaml
# Example using official collection
- name: Get device from NetBox
  netbox.netbox.netbox_device:
    netbox_url: "http://10.100.66.48:8000"
    netbox_token: "{{ netbox_token }}"
    name: "staging-server"
    state: present
  register: device
```

**Advantages of Official Collection:**
- ✅ Maintained by NetBox community
- ✅ Handles API pagination automatically
- ✅ Consistent error handling
- ✅ Supports all NetBox object types
- ✅ Idempotency built-in
- ✅ Better performance for bulk operations
- ✅ Future-proof (API changes handled by collection)

**Disadvantages of Current Custom Approach:**
- ❌ Manual API call handling
- ❌ No pagination support (could miss objects)
- ❌ Inconsistent error handling
- ❌ Maintenance burden
- ❌ No built-in idempotency

### Migration Path to Standardized Plugin

#### Phase 1: Preparation (No Breaking Changes)
1. Install the official collection:
   ```bash
   ansible-galaxy collection install netbox.netbox
   ```

2. Create a `requirements.yml`:
   ```yaml
   collections:
     - name: netbox.netbox
       version: ">=4.0.0"
   ```

3. Add to `ansible.cfg`:
   ```ini
   [defaults]
   collections_paths = ~/.ansible/collections:/usr/share/ansible/collections
   ```

#### Phase 2: Hybrid Approach (Gradual Migration)
Create wrapper modules that use the official collection but maintain the same interface:

```python
# netbox_api_v2.py - New version using official collection
from ansible_collections.netbox.netbox.plugins.module_utils.netbox import NetBoxModule

class NetBoxAPIV2:
    def __init__(self, url, token):
        self.nb = NetBoxModule(url=url, token=token)
    
    def get_devices(self):
        return self.nb.netbox.api.dcim.devices.all()
    
    def get_device(self, name):
        return self.nb.netbox.api.dcim.devices.get(name=name)
```

#### Phase 3: Full Migration
Replace custom API calls with official collection modules in playbooks:

**Before (custom):**
```yaml
- name: Get device information from NetBox
  ansible.builtin.uri:
    url: "{{ netbox_url }}/api/dcim/devices/?name={{ device_name }}"
    method: GET
    headers:
      Authorization: "Token {{ netbox_token }}"
    return_content: yes
  register: device_result
```

**After (standard):**
```yaml
- name: Get device information from NetBox
  netbox.netbox.netbox_device_info:
    netbox_url: "{{ netbox_url }}"
    netbox_token: "{{ netbox_token }}"
    name: "{{ device_name }}"
  register: device_result
```

#### Phase 4: Inventory Migration
Replace `netbox_inventory.py` with the official inventory plugin:

**New `ansible.cfg`:**
```ini
[defaults]
inventory = /etc/ansible/inventory.yml

[inventory]
enable_plugins = netbox.netbox.netbox
```

**New `inventory.yml`:**
```yaml
plugin: netbox.netbox.netbox
netbox_url: http://10.100.66.48:8000
netbox_token: "{{ lookup('env', 'NETBOX_TOKEN') }}"
validate_certs: false
```

#### Migration Benefits
- **Reduced code complexity:** ~70% reduction in custom Python code
- **Better reliability:** Handled edge cases (pagination, rate limiting)
- **Easier maintenance:** Community-supported
- **Multi-device support:** Built-in support for targeting multiple devices

#### Estimated Effort
| Component | Effort | Complexity |
|-----------|--------|------------|
| API client migration | 2-4 hours | Low |
| Playbook updates | 4-8 hours | Medium |
| Inventory migration | 2-4 hours | Low |
| Testing | 4-8 hours | Medium |
| **Total** | **2-3 days** | - |

---

## Ansible Playbook Structure

### Current Playbook Architecture

The system currently has **three main playbooks** with different scopes:

#### 1. `netbox_fetch.yml` - VLAN Reconciliation
- **Purpose:** Create/remove VLAN sub-interfaces based on NetBox
- **Scope:** Single device (staging-server)
- **Target:** localhost (runs on the same host)
- **Operations:**
  - Fetch VLAN IDs from NetBox child interfaces
  - Compare with current host VLAN configuration
  - Create missing VLAN interfaces (`ip link add ... type vlan`)
  - Remove extra VLAN interfaces (`ip link del`)
  - Bring up all VLAN interfaces (`ip link set ... up`)

#### 2. `assign_vlan_ips.yml` - IP Address Assignment
- **Purpose:** Assign IP addresses to existing VLAN interfaces
- **Scope:** Single device (device_id: 1)
- **Target:** localhost
- **Operations:**
  - Fetch all interfaces for device from NetBox
  - Identify trunk and child interfaces
  - Extract IP addresses from child interfaces
  - Map IPs to VLAN IDs
  - Remove IPs not in NetBox
  - Assign new IPs to VLAN interfaces
  - Validate IP assignments

#### 3. `netbox_reconcile.yml` - Full Reconciliation
- **Purpose:** Complete network configuration reconciliation
- **Scope:** Single device (staging-server)
- **Target:** localhost
- **Operations:**
  - All operations from `netbox_fetch.yml`
  - All operations from `assign_vlan_ips.yml`
  - Generate persistent network configuration
  - Configure TCP services (via tcp_simulator.py)
  - Create systemd service for persistence

### Multi-Device Support Analysis

**Current Limitation:** All playbooks target a **single hardcoded device** (`staging-server` or device_id: 1).

#### Required Changes for Cisco C1300-4G-24P Support

**1. Device-Specific Configuration**
```yaml
# inventory.yml - Multi-device inventory
all:
  children:
    linux_servers:
      hosts:
        staging-server:
          ansible_host: 10.100.66.48
          device_type: linux
          trunk_interface: enp1s0
    cisco_switches:
      hosts:
        cisco-c1300-4g-24p:
          ansible_host: 10.100.66.49
          device_type: cisco_ios
          trunk_interface: GigabitEthernet1/0/1
```

**2. Device-Type Specific Playbooks**
```
playbooks/
├── reconcile_linux.yml      # For Linux servers
├── reconcile_cisco.yml      # For Cisco switches
└── reconcile_all.yml         # Orchestrator playbook
```

**3. Platform-Agnostic Variables**
```yaml
# group_vars/all.yml
netbox_url: "http://10.100.66.48:8000"
netbox_token: "{{ vault_netbox_token }}"

# group_vars/linux_servers.yml
platform: linux
vlan_command: "ip link add link {trunk} name {trunk}.{vlan} type vlan id {vlan}"
ip_command: "ip addr add {address}/{prefix} dev {interface}"

# group_vars/cisco_switches.yml
platform: cisco_ios
vlan_command: "interface {trunk}.{vlan}"
ip_command: "ip address {address} {prefix}"
```

**4. Unified Reconciliation Playbook**
```yaml
# reconcile_all.yml
- name: Reconcile all network devices
  hosts: all
  strategy: free  # Allow parallel execution
  tasks:
    - name: Include platform-specific reconciliation
      ansible.builtin.include_tasks: "reconcile_{{ platform }}.yml"
```

#### Cisco-Specific Implementation

For the Cisco C1300-4G-24P switch, you would need:

```yaml
# reconcile_cisco.yml
- name: Reconcile Cisco switch configuration
  hosts: cisco_switches
  connection: network_cli  # or netconf
  gather_facts: false
  
  vars:
    ansible_network_os: ios
    ansible_user: admin
    ansible_password: "{{ vault_cisco_password }}"
    ansible_become: yes
    ansible_become_method: enable
    ansible_become_password: "{{ vault_cisco_enable }}"
  
  tasks:
    - name: Get current VLAN configuration
      cisco.ios.ios_vlans:
        state: gathered
      register: current_vlans
    
    - name: Get interfaces from NetBox
      netbox.netbox.netbox_interface_info:
        netbox_url: "{{ netbox_url }}"
        netbox_token: "{{ netbox_token }}"
        device: "{{ inventory_hostname }}"
      register: netbox_interfaces
    
    - name: Configure VLANs
      cisco.ios.ios_vlans:
        config: "{{ netbox_vlans | map('extract', netbox_vlan_mapping) | list }}"
        state: merged
```

#### Scalability Considerations

| Aspect | Current | Required for Multi-Device |
|--------|---------|--------------------------|
| Device targeting | Hardcoded | Dynamic from inventory |
| Platform support | Linux only | Linux + Cisco IOS |
| Connection method | local | local + network_cli |
| Parallel execution | No | Yes (strategy: free) |
| Error handling | Basic | Per-device, continue on error |
| Configuration drift | Manual check | Automated per device |

**Estimated Changes Required:**
- Inventory structure: **High priority** - 2-4 hours
- Playbook refactoring: **High priority** - 4-8 hours
- Cisco-specific modules: **Medium priority** - 4-8 hours
- Testing across platforms: **High priority** - 8-16 hours

---

## Persistence Mechanism

### Current Implementation

The system uses **multiple persistence layers** to ensure configuration survives reboots:

#### 1. Systemd Service for Network Configuration

**Generated by:** `netbox_reconcile.yml`

**Location:** `/etc/netbox_reconcile/network-config.sh`

**Content:** Auto-generated bash script that recreates all network configuration:
```bash
#!/bin/bash
# Auto-generated by NetBox reconciliation - 2026-06-12T10:00:00
TRUNK_IF="enp1s0"

# Bring up trunk interface
ip link set $TRUNK_IF up 2>/dev/null

# Create and configure VLAN interfaces
ip link add link $TRUNK_IF name $TRUNK_IF.2000 type vlan id 2000 2>/dev/null || true
ip link set $TRUNK_IF.2000 up 2>/dev/null || true
ip link add link $TRUNK_IF name $TRUNK_IF.2008 type vlan id 2008 2>/dev/null || true
ip link set $TRUNK_IF.2008 up 2>/dev/null || true

# Configure IP addresses
ip addr add 10.2.223.2/24 dev $TRUNK_IF.2000 2>/dev/null || true
ip addr add 10.2.223.10/24 dev $TRUNK_IF.2008 2>/dev/null || true
```

**Systemd Service:** `netbox-network.service`
- **Type:** oneshot
- **Trigger:** Multi-user.target (boot)
- **Purpose:** Run network-config.sh on system startup

#### 2. TCP Services Configuration

**Location:** `/etc/netbox_reconcile/tcp_services.json`

**Content:** JSON configuration for tcp_simulator.py:
```json
{
  "services": [
    {
      "ip": "10.2.223.2",
      "port": 80,
      "protocol": "tcp",
      "banner": "Service tcp-80 on 10.2.223.2"
    },
    {
      "ip": "10.2.223.10",
      "port": 443,
      "protocol": "tcp",
      "banner": "Service tcp-443 on 10.2.223.10"
    }
  ]
}
```

**Systemd Service:** `tcp_simulator.service`
- **Type:** simple
- **Restart:** always
- **Purpose:** Start TCP simulator on boot, auto-restart on crash

#### 3. Persistence Directory Structure

```
/etc/netbox_reconcile/
├── network-config.sh      # Network configuration script
├── tcp_services.json       # TCP services configuration
├── tcp_simulator.pid       # PID file for TCP simulator
└── tcp_connections.log     # Connection logs
```

### Persistence Verification

**What IS Persistent:**
- ✅ VLAN interface creation (via network-config.sh)
- ✅ IP address assignment (via network-config.sh)
- ✅ TCP service configuration (via tcp_services.json)
- ✅ TCP service listeners (via tcp_simulator.service)

**What is NOT Persistent (without reconciliation):**
- ❌ VLAN interface state (UP/DOWN) - Recreated on boot
- ❌ Route configurations - Not currently managed
- ❌ DNS configurations - Not currently managed

### Boot Sequence

```
System Boot
    │
    ▼
┌─────────────────────────┐
│ multi-user.target        │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ netbox-network.service   │ ◄── Runs network-config.sh
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ tcp_simulator.service    │ ◄── Starts TCP listeners
└─────────────────────────┘
    │
    ▼
System Ready (All services configured)
```

### Limitations of Current Persistence

1. **No Configuration Versioning:** Generated scripts overwrite previous versions
2. **No Rollback Capability:** Cannot revert to previous configuration
3. **No Dependency Management:** Services start independently, no ordering guarantees
4. **No Health Checks:** No verification that configuration was applied successfully

### Recommended Improvements

1. **Configuration Versioning:**
   ```bash
   # Store versions
   /etc/netbox_reconcile/versions/
   ├── 2026-06-12T10:00:00/
   │   ├── network-config.sh
   │   └── tcp_services.json
   └── current -> 2026-06-12T10:00:00
   ```

2. **Pre-boot Validation:**
   ```yaml
   # In netbox-network.service
   ExecStartPre=/usr/local/bin/validate-network-config.sh
   ```

3. **Post-boot Verification:**
   ```yaml
   ExecStartPost=/usr/local/bin/verify-network-config.sh
   ```

---

## Real-time Reconciliation

### Current Trigger Mechanism

**Manual Trigger Only:**
```bash
# Run reconciliation manually
ansible-playbook netbox_reconcile.yml

# Or via cron (if configured)
0 * * * * /usr/bin/ansible-playbook /opt/ansible/netbox_reconcile.yml
```

### Real-time Change Detection Options

#### Option 1: NetBox Webhooks (Recommended)

NetBox supports webhooks that can trigger reconciliation on changes:

**Setup:**
1. Configure webhook in NetBox Admin → Webhooks
2. Point to a local HTTP endpoint
3. Webhook fires on: device create/update/delete, interface changes, IP changes

**Implementation:**
```python
# webhook_receiver.py
from flask import Flask, request, jsonify
import subprocess

app = Flask(__name__)

@app.route('/webhook/netbox', methods=['POST'])
def netbox_webhook():
    data = request.json
    event = data.get('event')
    model = data.get('model')
    
    # Filter for relevant changes
    if model in ['dcim.device', 'dcim.interface', 'ipam.ipaddress']:
        # Trigger reconciliation
        subprocess.run(['ansible-playbook', '/opt/ansible/netbox_reconcile.yml'])
        return jsonify({'status': 'triggered'}), 200
    
    return jsonify({'status': 'ignored'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

**NetBox Webhook Configuration:**
```
Name: ansible-reconcile
URL: http://staging-server:5000/webhook/netbox
HTTP Method: POST
HTTP Content Type: application/json
Secret: (optional, for verification)
Events:
  - dcim.device: created, updated, deleted
  - dcim.interface: created, updated, deleted
  - ipam.ipaddress: created, updated, deleted
```

**Pros:**
- ✅ Real-time (immediate on change)
- ✅ Granular (only triggers on relevant changes)
- ✅ Built into NetBox
- ✅ No polling overhead

**Cons:**
- ❌ Requires webhook receiver service
- ❌ Network dependency (webhook must reach receiver)
- ❌ No built-in deduplication (multiple changes = multiple triggers)

#### Option 2: Polling with Change Detection

Enhanced cron job that checks for changes before running:

```python
# check_netbox_changes.py
import requests
import hashlib
import json
import os

NETBOX_URL = "http://10.100.66.48:8000"
TOKEN = "RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ"
STATE_FILE = "/var/lib/netbox_reconcile/last_state.json"

def get_state_hash():
    """Get a hash of current NetBox state for relevant objects."""
    state = {}
    
    # Get devices
    devices = requests.get(
        f"{NETBOX_URL}/api/dcim/devices/",
        headers={"Authorization": f"Token {TOKEN}"}
    ).json()
    state['devices'] = devices['results']
    
    # Get interfaces
    interfaces = requests.get(
        f"{NETBOX_URL}/api/dcim/interfaces/",
        headers={"Authorization": f"Token {TOKEN}"}
    ).json()
    state['interfaces'] = interfaces['results']
    
    # Get IP addresses
    ips = requests.get(
        f"{NETBOX_URL}/api/ipam/ip-addresses/",
        headers={"Authorization": f"Token {TOKEN}"}
    ).json()
    state['ip_addresses'] = ips['results']
    
    return hashlib.md5(json.dumps(state, sort_keys=True).encode()).hexdigest()

def main():
    current_hash = get_state_hash()
    
    # Load previous state
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            last_hash = json.load(f).get('hash')
    else:
        last_hash = None
    
    # Check for changes
    if current_hash != last_hash:
        print("Change detected, triggering reconciliation...")
        os.system('ansible-playbook /opt/ansible/netbox_reconcile.yml')
        
        # Update state file
        with open(STATE_FILE, 'w') as f:
            json.dump({'hash': current_hash, 'timestamp': time.time()}, f)
    else:
        print("No changes detected")

if __name__ == '__main__':
    main()
```

**Cron Entry:**
```bash
# Check every 5 minutes
*/5 * * * * /usr/bin/python3 /opt/ansible/check_netbox_changes.py
```

**Pros:**
- ✅ No additional services required
- ✅ Works with existing infrastructure
- ✅ Can be rate-limited

**Cons:**
- ❌ Delayed (polling interval)
- ❌ API load (frequent calls)
- ❌ No granularity (checks everything)

#### Option 3: NetBox Event Log Polling

Poll NetBox's event log for changes:

```python
# poll_event_log.py
import requests
import time

NETBOX_URL = "http://10.100.66.48:8000"
TOKEN = "RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ"
LAST_EVENT_FILE = "/var/lib/netbox_reconcile/last_event_id.txt"

def get_last_event_id():
    try:
        with open(LAST_EVENT_FILE) as f:
            return int(f.read().strip())
    except:
        return 0

def save_last_event_id(event_id):
    with open(LAST_EVENT_FILE, 'w') as f:
        f.write(str(event_id))

def check_events():
    last_id = get_last_event_id()
    
    # Get events since last check
    url = f"{NETBOX_URL}/api/extras/object-changes/?id__gt={last_id}"
    response = requests.get(url, headers={"Authorization": f"Token {TOKEN}"})
    events = response.json().get('results', [])
    
    if events:
        # Filter for relevant models
        relevant_models = ['dcim.device', 'dcim.interface', 'ipam.ipaddress']
        relevant_events = [e for e in events if e.get('changed_object_type') in relevant_models]
        
        if relevant_events:
            print(f"Found {len(relevant_events)} relevant changes")
            os.system('ansible-playbook /opt/ansible/netbox_reconcile.yml')
            save_last_event_id(events[-1]['id'])

if __name__ == '__main__':
    check_events()
```

**Pros:**
- ✅ Uses NetBox's built-in audit log
- ✅ Can filter by object type
- ✅ No additional NetBox configuration

**Cons:**
- ❌ Still polling-based
- ❌ Event log might be rate-limited

#### Option 4: File System Watch on NetBox (Advanced)

For local NetBox installations, watch the database or file system:

```python
# watch_netbox_db.py
import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class NetBoxChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if 'netbox' in event.src_path and event.src_path.endswith('.json'):
            print(f"Detected change in {event.src_path}")
            os.system('ansible-playbook /opt/ansible/netbox_reconcile.yml')

if __name__ == '__main__':
    path = '/var/lib/netbox/'  # Adjust based on NetBox installation
    event_handler = NetBoxChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
```

**Pros:**
- ✅ Immediate detection
- ✅ No API calls

**Cons:**
- ❌ NetBox-specific implementation
- ❌ File system access required
- ❌ Not portable

### Comparison Matrix

| Solution | Real-time | Granular | Complexity | Dependencies | Recommended |
|----------|-----------|----------|------------|--------------|-------------|
| Webhooks | ✅ Yes | ✅ Yes | Medium | Flask/server | ✅ **Best** |
| Polling (State Hash) | ❌ No (delayed) | ❌ No | Low | None | ⚠️ Simple |
| Event Log Polling | ❌ No (delayed) | ✅ Yes | Medium | None | ⚠️ Good |
| FS Watch | ✅ Yes | ✅ Yes | High | watchdog | ❌ Complex |

### Recommended Implementation

**Phase 1: Quick Win (1-2 hours)**
- Implement polling with change detection (Option 2)
- Set interval to 5-10 minutes
- Minimal changes, immediate benefit

**Phase 2: Production Ready (4-8 hours)**
- Implement webhook receiver (Option 1)
- Configure NetBox webhooks
- Add authentication/verification
- Implement deduplication (ignore rapid successive changes)

**Phase 3: Advanced (Optional)**
- Add event log polling as fallback
- Implement health checks
- Add notification system (email/Slack on reconciliation)

---

## Future Work

### Real-time Reconciliation Solutions

#### Solution Direction 1: NetBox Webhooks with Queue System

**Architecture:**
```
NetBox Changes → Webhook → Message Queue (Redis/RabbitMQ) → Worker → Ansible
```

**Implementation:**
```python
# webhook_to_queue.py
import pika
import json

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='netbox_changes')

@app.route('/webhook/netbox', methods=['POST'])
def webhook():
    data = request.json
    # Validate webhook signature
    if not validate_signature(request.headers, request.data):
        return jsonify({'error': 'Invalid signature'}), 401
    
    # Publish to queue
    channel.basic_publish(
        exchange='',
        routing_key='netbox_changes',
        body=json.dumps(data)
    )
    return jsonify({'status': 'queued'}), 200

# worker.py
import pika
import subprocess

def callback(ch, method, properties, body):
    data = json.loads(body)
    # Deduplicate: check if this change was already processed
    if not is_duplicate(data):
        subprocess.run(['ansible-playbook', 'netbox_reconcile.yml'])
        mark_processed(data)

channel.basic_consume(queue='netbox_changes', on_message_callback=callback, auto_ack=True)
channel.start_consuming()
```

**Benefits:**
- Decouples webhook receiver from Ansible execution
- Handles bursts of changes gracefully
- Easy to scale (multiple workers)
- Can add retry logic

**Complexity:** Medium (requires message queue infrastructure)

---

#### Solution Direction 2: NetBox Event Log with Long Polling

**Architecture:**
```
Ansible Control Node → Long Poll Event Log → Trigger Reconciliation
```

**Implementation:**
```python
# long_poll_events.py
import requests
import time

def long_poll_events(last_id=0, timeout=300):
    """Long poll NetBox event log for changes."""
    url = f"{NETBOX_URL}/api/extras/object-changes/"
    params = {
        'id__gt': last_id,
        'limit': 100
    }
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = requests.get(url, headers=headers, params=params)
        events = response.json().get('results', [])
        
        if events:
            return events
        
        time.sleep(5)  # Short sleep between checks
    
    return []  # Timeout

# Main loop
last_id = 0
while True:
    events = long_poll_events(last_id)
    if events:
        last_id = events[-1]['id']
        if has_relevant_changes(events):
            run_reconciliation()
```

**Benefits:**
- No additional infrastructure
- Efficient (only active when changes occur)
- Works with existing NetBox API

**Complexity:** Low-Medium

---

#### Solution Direction 3: GitOps Approach with NetBox as SoT

**Architecture:**
```
NetBox → Export Config → Git Repo → CI/CD Pipeline → Ansible → Targets
```

**Implementation:**
1. **Export Script:**
   ```python
   # export_netbox_config.py
   import requests
   import yaml
   
   def export_device_config(device_name):
       # Fetch all configuration for a device
       device = get_device(device_name)
       interfaces = get_interfaces(device['id'])
       ips = get_ips(device['id'])
       
       # Generate Ansible variables
       config = {
           'device': device,
           'interfaces': interfaces,
           'ip_addresses': ips
       }
       
       # Write to Git repo
       with open(f'config/devices/{device_name}.yml', 'w') as f:
           yaml.dump(config, f)
   ```

2. **Git Repo Structure:**
   ```
   netbox-config/
   ├── config/
   │   └── devices/
   │       ├── staging-server.yml
   │       └── cisco-c1300-4g-24p.yml
   ├── playbooks/
   │   └── reconcile.yml
   └── .gitlab-ci.yml
   ```

3. **CI/CD Pipeline:**
   ```yaml
   # .gitlab-ci.yml
   reconcile:
     image: ansible/ansible:latest
     script:
       - ansible-galaxy install -r requirements.yml
       - ansible-playbook playbooks/reconcile.yml
     only:
       - main
   ```

4. **NetBox Webhook:**
   - Triggers GitLab CI pipeline on changes
   - Or runs export script periodically

**Benefits:**
- Full audit trail (Git history)
- Rollback capability (Git revert)
- Review process (Merge Requests)
- Scalable to many devices

**Complexity:** High (requires Git infrastructure, CI/CD setup)

---

#### Solution Direction 4: Kubernetes Operator Pattern

For containerized environments, create a Kubernetes operator:

**Architecture:**
```
NetBox → Webhook → Kubernetes Operator → Custom Resource → Reconciliation
```

**Implementation:**
```yaml
# netbox-reconciler-operator.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: netbox-reconciler-operator
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: operator
        image: netbox-reconciler-operator:latest
        env:
        - name: NETBOX_URL
          value: "http://10.100.66.48:8000"
        - name: NETBOX_TOKEN
          valueFrom:
            secretKeyRef:
              name: netbox-credentials
              key: token
```

**Custom Resource Definition:**
```yaml
# netboxreconciliation.yaml
apiVersion: netbox.example.com/v1
kind: NetBoxReconciliation
metadata:
  name: staging-server-reconcile
spec:
  device: staging-server
  interval: 5m
  webhookSecret: my-secret
```

**Operator Logic:**
- Watches NetBoxReconciliation CRDs
- Sets up webhook or polling based on spec
- Manages reconciliation state
- Reports status back to CRD

**Benefits:**
- Native Kubernetes integration
- Scalable (multiple operators for different devices)
- Self-healing (Kubernetes restarts failed operators)

**Complexity:** High (requires Kubernetes expertise)

---

### Comparison of Future Solutions

| Solution | Real-time | Scalability | Complexity | Infrastructure | Best For |
|----------|-----------|-------------|------------|----------------|----------|
| Webhooks + Queue | ✅ Yes | ⭐⭐⭐⭐ | Medium | Redis/RabbitMQ | Production environments |
| Long Polling | ⚠️ Near | ⭐⭐⭐ | Low | None | Simple setups |
| GitOps | ❌ No (delayed) | ⭐⭐⭐⭐⭐ | High | Git, CI/CD | Team environments |
| Kubernetes Operator | ✅ Yes | ⭐⭐⭐⭐⭐ | High | Kubernetes | Containerized environments |

### Recommended Roadmap

**Short Term (1-2 weeks):**
1. Implement webhook receiver with basic authentication
2. Add change deduplication (5-minute window)
3. Set up logging and monitoring

**Medium Term (1-2 months):**
1. Migrate to official NetBox Ansible collection
2. Add multi-device support (Linux + Cisco)
3. Implement message queue for handling bursts
4. Add health checks and notifications

**Long Term (3-6 months):**
1. Evaluate GitOps approach for configuration management
2. Consider Kubernetes operator for containerized deployments
3. Add automated testing of reconciliation
4. Implement configuration drift detection

---

## Official NetBox Collection Support

**✅ NOW AVAILABLE:** The repository now includes support for the official `netbox.netbox` Ansible collection alongside the existing custom implementation.

### What's New

The following files have been added to support the official collection:

| File | Purpose |
|------|---------|
| `requirements.yml` | Collection dependencies definition |
| `inventory.yml` | Official NetBox inventory plugin configuration |
| `ansible.cfg` | Ansible configuration with inventory plugins enabled |
| `netbox_reconcile_collection.yml` | New reconciliation playbook using official collection modules |
| `NETBOX_COLLECTION_GUIDE.md` | Complete guide for using the official collection |

### Dual Approach Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    NetBox (SoT)                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        │                                       │
        ▼                                       ▼
┌─────────────────────┐               ┌─────────────────────────┐
│  LEGACY APPROACH     │               │  OFFICIAL COLLECTION     │
│                     │               │                         │
│  • netbox_api.py    │               │  • requirements.yml      │
│  • netbox_inventory.py│               │  • inventory.yml         │
│  • fetch_netbox_data.py│               │  • ansible.cfg           │
│  • netbox_*.yml      │               │  • netbox_reconcile_     │
│    (legacy playbooks)│               │    collection.yml        │
└─────────────────────┘               └─────────────────────────┘
        │                                       │
        └─────────────────────┬─────────────────────┘
                              ▼
              ┌─────────────────────────────────┐
              │       Target Systems              │
              │  (staging-server, cisco switches)  │
              └─────────────────────────────────┘
```

### Key Benefits of Official Collection

| Feature | Legacy Approach | Official Collection |
|---------|----------------|-------------------|
| Maintenance | Manual updates | Community-supported |
| Pagination | ❌ Not handled | ✅ Automatic |
| Error Handling | Basic | ✅ Robust |
| API Coverage | Limited | ✅ Complete |
| Performance | Manual HTTP calls | ✅ Optimized |
| Future-proof | ❌ May break | ✅ Maintained |
| Documentation | Custom | ✅ Official |

### Quick Start with Official Collection

#### 1. Install Dependencies (Debian)

```bash
# Install pynetbox via APT (recommended for Debian)
sudo apt update
sudo apt install -y python3-pynetbox

# Install the Ansible collection
ansible-galaxy collection install netbox.netbox

# Verify
ansible-galaxy collection list | grep netbox
python3 -c "import pynetbox; print(pynetbox.__version__)"
```

#### 2. Set Environment Variable

```bash
# Add to ~/.bashrc
echo 'export NETBOX_TOKEN="RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ"' >> ~/.bashrc
source ~/.bashrc
```

#### 3. Test the New Inventory

```bash
# List all hosts from NetBox
ansible -i inventory.yml all --list-hosts

# Test connectivity
ansible -i inventory.yml all -m ping
```

#### 4. Run the New Playbook

```bash
# Dry run
ansible-playbook -i inventory.yml netbox_reconcile_collection.yml --check

# Live run
ansible-playbook -i inventory.yml netbox_reconcile_collection.yml
```

### Using Both Approaches Together

Both the legacy and collection-based approaches can coexist:

```bash
# Legacy approach (still works)
ansible -i netbox_inventory.py all -m ping
ansible-playbook netbox_reconcile.yml

# Collection approach (new)
ansible -i inventory.yml all -m ping
ansible-playbook -i inventory.yml netbox_reconcile_collection.yml
```

### Migration Path

**Phase 1: Test (Current)**
- ✅ Install collection and dependencies
- ✅ Test `inventory.yml`
- ✅ Test `netbox_reconcile_collection.yml`
- ✅ Keep legacy files for fallback

**Phase 2: Gradual Migration**
- Update existing playbooks to use collection modules
- Replace custom API calls with official modules
- Test thoroughly

**Phase 3: Full Migration (Optional)**
- Remove legacy playbooks (or keep as backup)
- Standardize on collection-based approach

### Files Reference

**New Files (Collection Support):**
- `requirements.yml` - Collection dependencies
- `inventory.yml` - Official inventory plugin config
- `ansible.cfg` - Ansible configuration
- `netbox_reconcile_collection.yml` - New reconciliation playbook
- `NETBOX_COLLECTION_GUIDE.md` - Complete guide

**Existing Files (Legacy - Still Supported):**
- `inventory.ini` - Static inventory
- `netbox_inventory.py` - Custom dynamic inventory
- `netbox_api.py` - Custom API client
- `fetch_netbox_data.py` - Custom data fetcher
- `netbox_reconcile.yml` - Legacy reconciliation
- `netbox_fetch.yml` - Legacy VLAN fetch
- `assign_vlan_ips.yml` - Legacy IP assignment
- `get_vlan_ids.py` - Local VLAN discovery
- `tcp_simulator.py` - TCP service simulation

**See Also:** [NETBOX_COLLECTION_GUIDE.md](NETBOX_COLLECTION_GUIDE.md) for complete documentation on using the official collection.

---

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

### Get interfaces for a device
```bash
curl -H "Authorization: Token RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ" \
  -H "Accept: application/json" \
  "http://10.100.66.48:8000/api/dcim/interfaces/?device_id=1"
```

### Get child interfaces (VLAN sub-interfaces)
```bash
curl -H "Authorization: Token RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ" \
  -H "Accept: application/json" \
  "http://10.100.66.48:8000/api/dcim/interfaces/?parent_id=123"
```

### Get IP addresses for an interface
```bash
curl -H "Authorization: Token RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ" \
  -H "Accept: application/json" \
  "http://10.100.66.48:8000/api/ipam/ip-addresses/?interface_id=123"
```

---

## Security Notes

### Current Security Concerns

1. **Plaintext Tokens:** API tokens are stored in plaintext in scripts
2. **No SSL Verification:** `VERIFY_SSL = False` in all scripts
3. **No Rate Limiting:** Unlimited API calls possible
4. **No Authentication on Webhooks:** (if implemented)

### Recommended Security Improvements

1. **Use Ansible Vault for Tokens:**
   ```bash
   ansible-vault encrypt_string 'RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ' --name 'netbox_token'
   ```
   
   In playbooks:
   ```yaml
   vars:
     netbox_token: !vault |
       $ANSIBLE_VAULT;1.1;AES256
       663864396537363337363631616464653566636334363265376534643566633561306464353464353038
       ...
   ```

2. **Enable SSL Verification:**
   ```python
   VERIFY_SSL = True  # In all scripts
   ```
   
   Requires proper certificates on NetBox.

3. **Use Environment Variables:**
   ```python
   NETBOX_TOKEN = os.getenv('NETBOX_TOKEN')
   ```
   
   Set in shell:
   ```bash
   export NETBOX_TOKEN="RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ"
   ```

4. **Implement Webhook Authentication:**
   ```python
   WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
   
   def validate_signature(headers, body):
       signature = headers.get('X-NetBox-Signature')
       expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
       return hmac.compare_digest(signature, expected)
   ```

5. **Rate Limiting:**
   ```python
   from ratelimit import limits, sleep_and_retry
   
   @sleep_and_retry
   @limits(calls=100, period=60)  # 100 calls per minute
   def api_request(method, endpoint, **kwargs):
       # ... existing code
   ```

6. **Principle of Least Privilege:**
   - Create separate API tokens for different operations
   - Read-only token for inventory
   - Read-write token for reconciliation
   - Limited scope tokens where possible

---

## Quick Start

### Run Full Reconciliation
```bash
# Dry run (test mode)
ansible-playbook netbox_reconcile.yml --check

# Live run
ansible-playbook netbox_reconcile.yml
```

### Run VLAN Reconciliation Only
```bash
ansible-playbook netbox_fetch.yml
```

### Run IP Assignment Only
```bash
ansible-playbook assign_vlan_ips.yml
```

### Check Current VLAN Configuration
```bash
python3 get_vlan_ids.py enp1s0
```

### Fetch NetBox Data for a Device
```bash
python3 fetch_netbox_data.py staging-server enp1s0
```

---

## Troubleshooting

### Common Issues

1. **API Connection Failed:**
   - Verify NetBox is running: `curl http://10.100.66.48:8000`
   - Check API token: Verify token in NetBox admin
   - Check network connectivity

2. **VLAN Interfaces Not Created:**
   - Verify trunk interface exists: `ip link show enp1s0`
   - Check for errors: `journalctl -u netbox-network.service`
   - Run manually: `bash /etc/netbox_reconcile/network-config.sh`

3. **IP Addresses Not Assigned:**
   - Check VLAN interfaces exist: `ip link show`
   - Verify IP assignment: `ip addr show`
   - Check for conflicts: `ip addr show | grep <address>`

4. **TCP Services Not Listening:**
   - Check service status: `systemctl status tcp_simulator.service`
   - Check logs: `journalctl -u tcp_simulator.service`
   - Test manually: `python3 tcp_simulator.py /etc/netbox_reconcile/tcp_services.json`

### Debug Mode

All playbooks support verbose output:
```bash
ansible-playbook netbox_reconcile.yml -vvvv
```

For Python scripts:
```bash
python3 -m pdb fetch_netbox_data.py staging-server enp1s0
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License.

---

*Documentation generated on 2026-06-12. For the latest information, check the source code and NetBox API documentation.*
