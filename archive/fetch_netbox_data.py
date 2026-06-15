#!/usr/bin/env python3
"""Fetch data from NetBox and output as JSON for Ansible consumption."""
import sys
import json
import requests
import os

NETBOX_URL = os.getenv('NETBOX_URL', 'http://10.100.66.48:8000')
NETBOX_TOKEN = os.getenv('NETBOX_TOKEN', 'RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ')
DEVICE_NAME = sys.argv[1] if len(sys.argv) > 1 else 'staging-server'
TRUNK_INTERFACE = sys.argv[2] if len(sys.argv) > 2 else 'enp1s0'

def get_netbox(url, params=None):
    headers = {
        'Authorization': f'Token {NETBOX_TOKEN}',
        'Accept': 'application/json',
    }
    response = requests.get(f'{NETBOX_URL}{url}', headers=headers, params=params)
    response.raise_for_status()
    return response.json()

def main():
    try:
        # Get device
        devices = get_netbox('/api/dcim/devices/', params={'name': DEVICE_NAME})
        device = devices.get('results', [{}])[0]
        device_id = device.get('id')
        
        if not device_id:
            print(json.dumps({'error': 'Device not found'}))
            sys.exit(1)
        
        # Get all interfaces for device
        interfaces = get_netbox('/api/dcim/interfaces/', params={'device_id': device_id})
        if_results = interfaces.get('results', [])
        
        # Find trunk interface
        trunk_if = None
        for iface in if_results:
            if iface.get('name') == TRUNK_INTERFACE:
                trunk_if = iface
                break
        
        if not trunk_if:
            print(json.dumps({'error': f'Trunk interface {TRUNK_INTERFACE} not found'}))
            sys.exit(1)
        
        trunk_if_id = trunk_if.get('id')
        
        # Get child interfaces of trunk
        child_interfaces = get_netbox('/api/dcim/interfaces/', params={'parent_id': trunk_if_id})
        children = child_interfaces.get('results', [])
        
        # Collect VLAN IDs and IP data
        vlan_ids = []
        ip_data = []
        child_iface_data = []
        
        for child in children:
            child_name = child.get('name', '')
            tagged_vlans = child.get('tagged_vlans', [])
            child_vlan_ids = [v.get('vid') for v in tagged_vlans]
            vlan_ids.extend(child_vlan_ids)
            
            # Get IP addresses for this child interface
            child_id = child.get('id')
            ips_resp = get_netbox('/api/ipam/ip-addresses/', params={'interface_id': child_id})
            ips = ips_resp.get('results', [])
            
            for ip in ips:
                addr = ip.get('address', '')
                cf = ip.get('custom_fields', {})
                services = cf.get('service_port', '')
                ip_data.append({
                    'interface': child_name,
                    'vlan': child_vlan_ids[0] if child_vlan_ids else None,
                    'address': addr,
                    'services': services
                })
            
            child_iface_data.append({
                'name': child_name,
                'vlan_ids': child_vlan_ids,
                'ip_addresses': [ip.get('address', '') for ip in ips]
            })
        
        vlan_ids = sorted(set(vlan_ids))
        
        result = {
            'device': {
                'id': device_id,
                'name': device.get('display', ''),
                'description': device.get('description', '')
            },
            'trunk_interface': {
                'id': trunk_if_id,
                'name': trunk_if.get('name', ''),
                'description': trunk_if.get('description', '')
            },
            'vlan_ids': vlan_ids,
            'child_interfaces': child_iface_data,
            'ip_data': ip_data
        }
        
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(json.dumps({'error': str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
