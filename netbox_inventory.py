#!/usr/bin/env python3
"""
NetBox Dynamic Inventory for Ansible
Uses NetBox API to fetch devices and create Ansible inventory
"""

import json
import os
import requests
import sys

# NetBox API Configuration
NETBOX_URL = "http://10.100.66.48:8000"
NETBOX_TOKEN = "RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ"

# Disable SSL verification for self-signed certs (not recommended for production)
VERIFY_SSL = False


def get_netbox_devices():
    """Fetch all devices from NetBox"""
    url = f"{NETBOX_URL}/api/dcim/devices/"
    headers = {
        "Authorization": f"Token {NETBOX_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.get(url, headers=headers, verify=VERIFY_SSL)
        response.raise_for_status()
        return response.json()["results"]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching devices from NetBox: {e}", file=sys.stderr)
        return []


def build_inventory():
    """Build Ansible inventory JSON from NetBox devices"""
    devices = get_netbox_devices()
    
    inventory = {
        "_meta": {"hostvars": {}},
        "all": {"hosts": []},
    }
    
    for device in devices:
        name = device.get("name", device.get("id"))
        inventory["all"]["hosts"].append(name)
        
        # Add host variables
        host_vars = {
            "netbox_id": device.get("id"),
            "netbox_name": device.get("name"),
            "netbox_device_role": device.get("device_role", {}).get("name") if device.get("device_role") else None,
            "netbox_device_type": device.get("device_type", {}).get("model") if device.get("device_type") else None,
            "netbox_status": device.get("status", {}).get("label") if device.get("status") else None,
            "netbox_primary_ip": device.get("primary_ip", {}).get("address") if device.get("primary_ip") else None,
        }
        inventory["_meta"]["hostvars"][name] = host_vars
    
    return inventory


if __name__ == "__main__":
    inventory = build_inventory()
    print(json.dumps(inventory, indent=2))
