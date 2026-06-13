#!/usr/bin/env python3
"""
NetBox API Client for Ansible
This script provides functions to interact with NetBox API
using the stored API token.
"""

import requests
import json
import sys

# NetBox Configuration
NETBOX_URL = "http://10.100.66.48:8000"
API_TOKEN = "RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ"

# Disable SSL verification for development (remove in production)
VERIFY_SSL = False


def api_request(method, endpoint, data=None, params=None):
    """
    Make an authenticated request to NetBox API
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        endpoint: API endpoint path (e.g., '/api/dcim/devices/')
        data: JSON data for POST/PUT/PATCH
        params: Query parameters
    
    Returns:
        JSON response or None on error
    """
    url = f"{NETBOX_URL}{endpoint}"
    headers = {
        "Authorization": f"Token {API_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=params, verify=VERIFY_SSL)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data, verify=VERIFY_SSL)
        elif method.upper() == "PUT":
            response = requests.put(url, headers=headers, json=data, verify=VERIFY_SSL)
        elif method.upper() == "PATCH":
            response = requests.patch(url, headers=headers, json=data, verify=VERIFY_SSL)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers, verify=VERIFY_SSL)
        else:
            print(f"Error: Unsupported HTTP method {method}", file=sys.stderr)
            return None
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error: {e}", file=sys.stderr)
        return None


def get_devices():
    """Get all devices from NetBox"""
    return api_request("GET", "/api/dcim/devices/")


def get_device(device_id):
    """Get a specific device by ID"""
    return api_request("GET", f"/api/dcim/devices/{device_id}/")


def create_device(name, device_type, device_role, site=None, status="active", **kwargs):
    """Create a new device in NetBox"""
    data = {
        "name": name,
        "device_type": device_type,
        "device_role": device_role,
        "site": site,
        "status": status,
    }
    data.update(kwargs)
    return api_request("POST", "/api/dcim/devices/", data=data)


def create_interface(device, name, type="1000base-t", description="", enabled=True):
    """Create an interface on a device"""
    data = {
        "device": device,
        "name": name,
        "type": type,
        "description": description,
        "enabled": enabled,
    }
    return api_request("POST", "/api/dcim/interfaces/", data=data)


if __name__ == "__main__":
    # Example usage
    print("Testing NetBox API connection...")
    devices = get_devices()
    if devices:
        print(f"Found {devices.get('count', 0)} devices")
        for device in devices.get('results', []):
            print(f"  - {device.get('name')} (ID: {device.get('id')})")
    else:
        print("Failed to connect to NetBox API")
        sys.exit(1)
