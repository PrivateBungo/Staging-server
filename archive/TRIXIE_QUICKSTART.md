# Debian Trixie Quick Start Guide

This guide gets you up and running with the official NetBox Ansible collection on Debian Trixie.

## Prerequisites

You should now have:
- ✅ Debian Trixie
- ✅ Ansible 2.19.4
- ✅ Python 3.13.5

---

## Step 1: Install Dependencies

```bash
# Install pynetbox (required by the collection)
sudo apt install -y python3-pynetbox

# Install the official NetBox collection
ansible-galaxy collection install netbox.netbox

# Verify installation
ansible --version | head -1
ansible-galaxy collection list | grep netbox
python3 -c "import pynetbox; print('pynetbox:', pynetbox.__version__)"
```

Expected output:
- Ansible: `ansible [core 2.19.4]`
- Collection: `netbox.netbox:3.x.x`
- pynetbox: version number

---

## Step 2: Set Environment Variable

```bash
# Add to ~/.bashrc
echo 'export NETBOX_TOKEN="RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ"' >> ~/.bashrc

# Apply
source ~/.bashrc

# Verify (shows first 10 chars only)
echo "Token set: ${NETBOX_TOKEN:0:10}..."
```

---

## Step 3: Test the Setup

### Test Inventory
```bash
# List all hosts from NetBox
ansible -i inventory.yml all --list-hosts

# Expected output: should list your devices from NetBox
# Example: staging-server
```

### Test Connectivity
```bash
# Ping all hosts
ansible -i inventory.yml all -m ping

# Expected output: should show "ping": "pong" for each device
```

---

## Step 4: Run Reconciliation

### Dry Run (Test Mode)
```bash
ansible-playbook -i inventory.yml netbox_reconcile_trixie.yml --check

# This will show what changes would be made without actually making them
```

### Live Run
```bash
ansible-playbook -i inventory.yml netbox_reconcile_trixie.yml

# This will apply the changes to your system
```

---

## Files Reference

| File | Purpose | Usage |
|------|---------|-------|
| `inventory.yml` | Dynamic inventory using official plugin | `ansible -i inventory.yml ...` |
| `ansible.cfg` | Ansible configuration | Automatic when in same directory |
| `requirements.yml` | Collection dependencies | `ansible-galaxy collection install -r requirements.yml` |
| `netbox_reconcile_trixie.yml` | Reconciliation playbook | `ansible-playbook -i inventory.yml netbox_reconcile_trixie.yml` |

### Legacy Files (Still Available)
| File | Purpose |
|------|---------|
| `netbox_inventory.py` | Custom dynamic inventory (fallback) |
| `netbox_api.py` | Custom API client |
| `fetch_netbox_data.py` | Custom data fetcher |
| `netbox_reconcile.yml` | Legacy reconciliation playbook |
| `netbox_fetch.yml` | Legacy VLAN fetch playbook |
| `assign_vlan_ips.yml` | Legacy IP assignment playbook |

---

## Troubleshooting

### "Failed to load inventory plugin"

**Cause:** Collection not installed or plugin not enabled.

**Solution:**
```bash
# Reinstall collection
ansible-galaxy collection install netbox.netbox --force

# Check plugin is available
ansible-doc -t inventory netbox.netbox.netbox

# Test with explicit path
ANSIBLE_COLLECTIONS_PATHS=~/.ansible/collections ansible -i inventory.yml all --list-hosts
```

### "No module named 'pynetbox'"

**Solution:**
```bash
sudo apt install -y python3-pynetbox
```

### "Host not found"

**Cause:** The device name in NetBox doesn't match what's in your local hosts file.

**Solution:**
```bash
# Check what hosts are returned
ansible -i inventory.yml all --list-hosts

# If it shows hosts but ping fails, the hostname might not resolve
# Add to /etc/hosts:
echo "127.0.0.1 staging-server" | sudo tee -a /etc/hosts
```

### Permission denied on /etc/netbox_reconcile

**Solution:** The playbook now uses `~/.netbox_reconcile` by default, so no sudo needed. But if you want system-wide:
```bash
sudo mkdir -p /etc/netbox_reconcile
sudo chown $USER:$USER /etc/netbox_reconcile
```

---

## Common Commands

```bash
# ===== Setup =====
source ~/.bashrc

# ===== Test =====
ansible -i inventory.yml all --list-hosts
ansible -i inventory.yml all -m ping

# ===== Reconcile =====
ansible-playbook -i inventory.yml netbox_reconcile_trixie.yml --check
ansible-playbook -i inventory.yml netbox_reconcile_trixie.yml

# ===== Legacy (fallback) =====
ansible -i netbox_inventory.py all -m ping
ansible-playbook netbox_reconcile.yml

# ===== Check Status =====
ip link show
ip addr show
systemctl status netbox-network.service
```

---

## Using Both Approaches

You can use both the official collection and legacy approaches:

```bash
# Official collection (recommended)
ansible -i inventory.yml all -m ping
ansible-playbook -i inventory.yml netbox_reconcile_trixie.yml

# Legacy (fallback)
ansible -i netbox_inventory.py all -m ping
ansible-playbook netbox_reconcile.yml
```

---

## Benefits of Official Collection

| Feature | Legacy | Official Collection |
|---------|--------|-------------------|
| Maintenance | Manual | Community-supported |
| Pagination | ❌ No | ✅ Automatic |
| Error Handling | Basic | ✅ Robust |
| API Coverage | Limited | ✅ Complete |
| Performance | Manual HTTP | ✅ Optimized |
| Future-proof | ❌ May break | ✅ Maintained |

---

## Next Steps

1. ✅ Upgrade to Debian Trixie
2. ✅ Install dependencies (pynetbox, collection)
3. ✅ Set environment variable
4. ✅ Test inventory
5. ✅ Run reconciliation

**You're all set!** 🎉

For more details, see:
- [Official NetBox Collection Documentation](https://galaxy.ansible.com/netbox/netbox)
- [pynetbox Documentation](https://pynetbox.readthedocs.io/)
