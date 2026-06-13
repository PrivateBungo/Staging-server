# NetBox Collection Integration Guide

This guide explains how to use the official `netbox.netbox` Ansible collection alongside the existing custom implementation.

## Overview

This repository now supports **two parallel approaches** for NetBox integration:

1. **Legacy Approach** (existing files)
   - `netbox_inventory.py` - Custom dynamic inventory script
   - `netbox_api.py` - Custom API client
   - `fetch_netbox_data.py` - Custom data fetcher
   - `netbox_reconcile.yml` - Legacy reconciliation playbook
   - `netbox_fetch.yml` - Legacy VLAN fetch playbook
   - `assign_vlan_ips.yml` - Legacy IP assignment playbook

2. **Official Collection Approach** (new files)
   - `requirements.yml` - Collection requirements
   - `inventory.yml` - Official inventory plugin configuration
   - `ansible.cfg` - Ansible configuration
   - `netbox_reconcile_collection.yml` - New reconciliation playbook using official modules

**Both approaches can coexist** - you can use either or both depending on your needs.

---

## Quick Start with Official Collection

### 1. Install Dependencies on Host

Since you're on Debian with Python 3.11.2 and have pip restrictions, use APT:

```bash
# Install pynetbox via Debian packages (recommended)
sudo apt update
sudo apt install -y python3-pynetbox

# Install the Ansible collection
ansible-galaxy collection install netbox.netbox

# Verify installation
ansible-galaxy collection list | grep netbox
python3 -c "import pynetbox; print('pynetbox version:', pynetbox.__version__)"
```

**Alternative: Use Virtual Environment**
```bash
# Create virtual environment
python3 -m venv ~/ansible-venv

# Activate it
source ~/ansible-venv/bin/activate

# Install dependencies
pip install pynetbox
ansible-galaxy collection install netbox.netbox

# Add to ~/.bashrc for persistence
echo "source ~/ansible-venv/bin/activate" >> ~/.bashrc
source ~/.bashrc
```

### 2. Set Environment Variable

```bash
# Add to ~/.bashrc or /etc/environment
echo 'export NETBOX_TOKEN="RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ"' >> ~/.bashrc
source ~/.bashrc

# Verify
echo $NETBOX_TOKEN
```

### 3. Test the New Inventory

```bash
# Test inventory plugin
ansible -i inventory.yml all -m ping

# List all hosts from NetBox
ansible -i inventory.yml all --list-hosts

# Show host variables
ansible -i inventory.yml staging-server -m debug -a "var=hostvars[inventory_hostname]"
```

### 4. Run the New Reconciliation Playbook

```bash
# Dry run (test mode)
ansible-playbook -i inventory.yml netbox_reconcile_collection.yml --check

# Live run
ansible-playbook -i inventory.yml netbox_reconcile_collection.yml
```

---

## File Reference

### New Files for Collection Support

| File | Purpose | Usage |
|------|---------|-------|
| `requirements.yml` | Collection dependencies | `ansible-galaxy collection install -r requirements.yml` |
| `inventory.yml` | Dynamic inventory config | `ansible -i inventory.yml ...` |
| `ansible.cfg` | Ansible configuration | Automatic when in same directory |
| `netbox_reconcile_collection.yml` | New reconciliation playbook | `ansible-playbook -i inventory.yml netbox_reconcile_collection.yml` |

### Existing Files (Legacy - Still Supported)

| File | Purpose | Usage |
|------|---------|-------|
| `inventory.ini` | Static inventory | `ansible -i inventory.ini ...` |
| `netbox_inventory.py` | Custom dynamic inventory | `ansible -i netbox_inventory.py ...` |
| `netbox_api.py` | Custom API client | `python3 netbox_api.py` |
| `fetch_netbox_data.py` | Custom data fetcher | `python3 fetch_netbox_data.py` |
| `netbox_reconcile.yml` | Legacy reconciliation | `ansible-playbook netbox_reconcile.yml` |
| `netbox_fetch.yml` | Legacy VLAN fetch | `ansible-playbook netbox_fetch.yml` |
| `assign_vlan_ips.yml` | Legacy IP assignment | `ansible-playbook assign_vlan_ips.yml` |

---

## Comparison: Legacy vs Collection

### Data Fetching

**Legacy (netbox_reconcile.yml):**
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

**Collection (netbox_reconcile_collection.yml):**
```yaml
- name: Get device information from NetBox
  netbox.netbox.netbox_device_info:
    netbox_url: "{{ netbox_url }}"
    netbox_token: "{{ netbox_token }}"
    name: "{{ device_name }}"
  register: nb_device
```

### Inventory

**Legacy (netbox_inventory.py):**
```bash
ansible -i netbox_inventory.py all -m ping
```

**Collection (inventory.yml):**
```bash
ansible -i inventory.yml all -m ping
```

---

## Migration Path

### Phase 1: Test Collection (Current)
- ✅ Install collection and dependencies
- ✅ Test `inventory.yml`
- ✅ Test `netbox_reconcile_collection.yml`
- ✅ Keep legacy files for fallback

### Phase 2: Gradual Migration
- Update existing playbooks to use collection modules
- Replace custom API calls with official modules
- Test thoroughly

### Phase 3: Full Migration (Optional)
- Remove legacy playbooks (or keep as backup)
- Remove custom Python scripts (or keep for direct usage)
- Standardize on collection-based approach

---

## Troubleshooting

### Common Issues

**1. Collection not found:**
```
ERROR! the role 'netbox.netbox.netbox_device_info' was not found
```
**Solution:** Install the collection first:
```bash
ansible-galaxy collection install netbox.netbox
```

**2. pynetbox not found:**
```
ModuleNotFoundError: No module named 'pynetbox'
```
**Solution:** Install pynetbox:
```bash
# On Debian
sudo apt install -y python3-pynetbox

# Or in virtual environment
pip install pynetbox
```

**3. NETBOX_TOKEN not set:**
```
fatal: [localhost]: FAILED! => {"msg": "The field 'netbox_token' has an invalid value ({{ lookup('env', 'NETBOX_TOKEN') }})"
```
**Solution:** Set the environment variable:
```bash
export NETBOX_TOKEN="RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ"
```

**4. Inventory plugin not enabled:**
```
ERROR! Unable to parse /path/to/inventory.yml as an inventory source
```
**Solution:** Ensure inventory plugins are enabled in ansible.cfg:
```ini
[inventory]
enable_plugins = netbox.netbox.netbox, yaml, ini
```

---

## Using Both Approaches Together

You can use both the legacy and collection-based approaches simultaneously:

```bash
# Use legacy inventory for some operations
ansible -i netbox_inventory.py all -m ping

# Use collection inventory for others
ansible -i inventory.yml all -m ping

# Run both playbooks
ansible-playbook netbox_reconcile.yml
ansible-playbook -i inventory.yml netbox_reconcile_collection.yml
```

This allows for gradual migration and testing.

---

## Benefits of Official Collection

| Feature | Legacy | Collection |
|---------|--------|------------|
| Maintenance | Manual | Community-supported |
| Pagination | ❌ No | ✅ Yes |
| Error handling | Basic | ✅ Robust |
| API coverage | Limited | ✅ Complete |
| Performance | Manual calls | ✅ Optimized |
| Future-proof | ❌ No | ✅ Yes |
| Documentation | Custom | ✅ Official |

---

## Files to Keep vs Remove

### ✅ Keep (Both Approaches)
- `get_vlan_ids.py` - Local VLAN discovery (independent)
- `tcp_simulator.py` - TCP service simulation (independent)
- `inventory.ini` - Static inventory (fallback)

### ✅ Keep (Legacy)
- `netbox_inventory.py` - Custom inventory (fallback)
- `netbox_api.py` - Custom API client (for direct Python usage)
- `fetch_netbox_data.py` - Custom data fetcher (for direct Python usage)
- `netbox_reconcile.yml` - Legacy playbook (fallback)
- `netbox_fetch.yml` - Legacy playbook (fallback)
- `assign_vlan_ips.yml` - Legacy playbook (fallback)

### ✅ Keep (Collection)
- `requirements.yml` - Collection requirements
- `inventory.yml` - Official inventory config
- `ansible.cfg` - Ansible configuration
- `netbox_reconcile_collection.yml` - New playbook

### ⚠️ Optional Remove (After Full Migration)
- `netbox_inventory.py` - Can remove after switching to inventory.yml
- `netbox_api.py` - Can remove if not used directly
- `fetch_netbox_data.py` - Can remove if not used directly
- Legacy playbooks - Can remove after testing collection playbook

---

## Environment Setup Checklist

- [ ] Install `netbox.netbox` collection: `ansible-galaxy collection install netbox.netbox`
- [ ] Install `pynetbox`: `sudo apt install -y python3-pynetbox` or `pip install pynetbox`
- [ ] Set `NETBOX_TOKEN` environment variable
- [ ] Test inventory: `ansible -i inventory.yml all --list-hosts`
- [ ] Test playbook: `ansible-playbook -i inventory.yml netbox_reconcile_collection.yml --check`
- [ ] Run live: `ansible-playbook -i inventory.yml netbox_reconcile_collection.yml`

---

## Additional Resources

- [NetBox Ansible Collection Documentation](https://galaxy.ansible.com/netbox/netbox)
- [pynetbox Documentation](https://pynetbox.readthedocs.io/)
- [Ansible Inventory Plugins](https://docs.ansible.com/ansible/latest/user_guide/intro_inventory.html)
- [NetBox API Documentation](https://netbox.readthedocs.io/en/stable/rest-api/overview/)
