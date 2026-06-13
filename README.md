# NetBox Ansible Integration

**Date:** 2026-06-12

This directory contains scripts for integrating NetBox with Ansible.

## Setup

### NetBox Installation
- NetBox is installed at: `http://10.100.66.48:8000`
- Superuser: `gijs` / `123GjH#@!`

### API Token
- Token: `RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ`
- This token has full API access

### Device
- Device **debian** (ID: 1) is registered in NetBox representing this host
- Interfaces:
  - **eth0**: Primary network interface - in use
  - **eth1**: Trunk port - for future use

## Scripts

### `netbox_api.py`
Python API client for interacting with NetBox. Can be used as a library or standalone.

**Usage:**
```bash
python3 netbox_api.py
```

**Example:**
```python
from netbox_api import get_devices, get_device

devices = get_devices()
print(devices)
```

### `netbox_inventory.py`
Dynamic inventory script for Ansible. Fetches devices from NetBox and creates Ansible inventory.

**Usage:**
```bash
# In ansible.cfg
[defaults]
inventory = /opt/ansible/netbox_inventory.py

# Or run directly
python3 netbox_inventory.py
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

## Notes

- The API token is stored in plaintext in these scripts. For production, consider:
  - Using Ansible Vault
  - Setting the token as an environment variable
  - Using a secrets management system
- SSL verification is disabled (`VERIFY_SSL = False`) for development. Enable it for production.
