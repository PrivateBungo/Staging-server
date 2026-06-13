# Environment Setup Guide for Debian Bookworm

This guide helps you set up the NetBox Ansible integration on Debian Bookworm with:
- Python 3.11.2
- Ansible 2.14.18
- No upgrades required

## Quick Start

### 1. Set Environment Variables

Add these to your `~/.bashrc` file:

```bash
# NetBox API Configuration
export NETBOX_URL="http://10.100.66.48:8000"
export NETBOX_TOKEN="RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ"

# Optional: Disable SSL verification for development
export NETBOX_VERIFY_SSL="false"
```

Then apply:
```bash
source ~/.bashrc
```

### 2. Verify Your Environment

```bash
# Check Python
echo "Python: $(python3 --version)"

# Check Ansible
echo "Ansible: $(ansible --version | head -1)"

# Check environment variables
echo "NETBOX_URL: $NETBOX_URL"
echo "NETBOX_TOKEN: ${NETBOX_TOKEN:0:10}..."  # Show first 10 chars only
```

---

## Using the Existing Scripts

All existing scripts now support environment variables as a fallback to hardcoded values.

### Inventory

```bash
# Use the custom dynamic inventory
ansible -i netbox_inventory.py all -m ping

# List all hosts
ansible -i netbox_inventory.py all --list-hosts

# Show host variables for a specific device
ansible -i netbox_inventory.py staging-server -m debug -a "var=hostvars[inventory_hostname]"
```

### API Client

```bash
# Run the API client directly
python3 netbox_api.py

# Or import in your own scripts
from netbox_api import get_devices, get_device

devices = get_devices()
print(devices)
```

### Fetch Data

```bash
# Fetch data for a specific device and trunk interface
python3 fetch_netbox_data.py staging-server enp1s0

# Output is JSON, can be piped to other tools
python3 fetch_netbox_data.py staging-server enp1s0 | jq .
```

---

## Running Playbooks

### Full Reconciliation

```bash
# Dry run (test mode - no changes)
ansible-playbook netbox_reconcile.yml --check

# Live run (applies changes)
ansible-playbook netbox_reconcile.yml
```

### VLAN Reconciliation Only

```bash
ansible-playbook netbox_fetch.yml
```

### IP Assignment Only

```bash
ansible-playbook assign_vlan_ips.yml
```

---

## Environment Variable Reference

| Variable | Purpose | Default Value | Required |
|----------|---------|---------------|----------|
| `NETBOX_URL` | NetBox API URL | `http://10.100.66.48:8000` | ❌ No |
| `NETBOX_TOKEN` | NetBox API token | `RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ` | ❌ No |
| `NETBOX_VERIFY_SSL` | Enable SSL verification | `false` | ❌ No |

**Note:** If environment variables are not set, the scripts fall back to hardcoded values.

---

## Security Recommendations

### Option 1: Use Environment Variables (Recommended)

```bash
# Add to ~/.bashrc (only you can see)
echo 'export NETBOX_TOKEN="RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ"' >> ~/.bashrc
source ~/.bashrc
```

### Option 2: Use a .env File

Create a `.env` file in your ansible directory:

```bash
# .env file
NETBOX_URL=http://10.100.66.48:8000
NETBOX_TOKEN=RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ
NETBOX_VERIFY_SSL=false
```

Then load it before running commands:

```bash
# Load the .env file
set -a && source .env && set +a

# Now run your commands
ansible -i netbox_inventory.py all -m ping
```

### Option 3: Use Ansible Vault (Most Secure)

```bash
# Create encrypted variable file
ansible-vault create group_vars/all/vault.yml

# Add to vault.yml:
# netbox_token: "RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ"

# Edit encrypted file
ansible-vault edit group_vars/all/vault.yml

# Run playbook (will prompt for vault password)
ansible-playbook netbox_reconcile.yml --ask-vault-pass
```

---

## Troubleshooting

### "Failed to connect to the host via ssh"

This means the inventory script returned a hostname that doesn't exist in DNS/hosts file.

**Solution:**
```bash
# Check what hosts are returned
ansible -i netbox_inventory.py all --list-hosts

# If it shows "staging-server" but that host doesn't exist,
# you need to either:
# 1. Add staging-server to /etc/hosts
# 2. Use localhost connection (for local execution)
```

### Permission Denied on /etc/netbox_reconcile

**Solution:**
```bash
# Create directory with sudo
sudo mkdir -p /etc/netbox_reconcile
sudo chown $USER:$USER /etc/netbox_reconcile

# Or run playbook with become
ansible-playbook netbox_reconcile.yml --become --ask-become-pass
```

### API Connection Failed

**Solution:**
```bash
# Test API connection manually
curl -H "Authorization: Token $NETBOX_TOKEN" \
  -H "Accept: application/json" \
  http://10.100.66.48:8000/api/dcim/devices/

# Check if token is correct
# Check if NetBox is running
# Check network connectivity
```

---

## File Locations

| File | Location | Purpose |
|------|----------|---------|
| `netbox_inventory.py` | `/home/gijs/ansible/` | Dynamic inventory script |
| `netbox_api.py` | `/home/gijs/ansible/` | API client library |
| `fetch_netbox_data.py` | `/home/gijs/ansible/` | Data fetcher |
| `get_vlan_ids.py` | `/home/gijs/ansible/` | Local VLAN discovery |
| `netbox_reconcile.yml` | `/home/gijs/ansible/` | Full reconciliation playbook |
| `netbox_fetch.yml` | `/home/gijs/ansible/` | VLAN reconciliation playbook |
| `assign_vlan_ips.yml` | `/home/gijs/ansible/` | IP assignment playbook |
| `tcp_simulator.py` | `/home/gijs/ansible/` | TCP service simulator |

---

## Common Commands Cheat Sheet

```bash
# ===== Environment =====
source ~/.bashrc

# ===== Test Connection =====
curl -H "Authorization: Token $NETBOX_TOKEN" http://10.100.66.48:8000/api/dcim/devices/

# ===== Inventory =====
ansible -i netbox_inventory.py all --list-hosts
ansible -i netbox_inventory.py all -m ping

# ===== Data Fetching =====
python3 fetch_netbox_data.py staging-server enp1s0

# ===== Reconciliation =====
ansible-playbook netbox_reconcile.yml --check          # Dry run
ansible-playbook netbox_reconcile.yml                # Live run

# ===== VLAN Only =====
ansible-playbook netbox_fetch.yml

# ===== IP Assignment Only =====
ansible-playbook assign_vlan_ips.yml

# ===== Check VLANs =====
python3 get_vlan_ids.py enp1s0
ip link show

# ===== Check IPs =====
ip addr show
```

---

## No Upgrades Required

✅ **Python 3.11.2** - Supported
✅ **Ansible 2.14.18** - Supported  
✅ **Debian Bookworm** - Supported
✅ **All existing scripts** - Work as-is
✅ **Environment variables** - Optional enhancement

Everything in this repository works with your current setup. No upgrades needed!
