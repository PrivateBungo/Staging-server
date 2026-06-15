#!/usr/bin/env python3
"""Generate a static Ansible inventory snapshot from NetBox.

The output keeps a small host summary and one canonical network block
with the multi-angle views needed by downstream playbooks.
"""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Any, Dict, List, Optional

import requests
import yaml


NETBOX_URL = os.getenv("NETBOX_URL", "http://10.100.66.48:8000")
NETBOX_TOKEN = os.getenv("NETBOX_TOKEN", "RUmeVgksKcgogMd7tn5TrkIphBEGrQEUKibOmayQ")
INVENTORY_OUTPUT = os.getenv("INVENTORY_OUTPUT", "inventory_snapshot.yml")
VERIFY_SSL = False


class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: Any) -> bool:
        return True


SESSION = requests.Session()
SESSION.headers.update(
    {
        "Authorization": f"Token {NETBOX_TOKEN}",
        "Accept": "application/json",
    }
)


def paginate(path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    url = f"{NETBOX_URL}{path}"
    query = dict(params or {})

    while url:
        response = SESSION.get(url, params=query, verify=VERIFY_SSL, timeout=30)
        response.raise_for_status()
        payload = response.json()
        results.extend(payload.get("results", []))
        url = payload.get("next")
        query = {}

    return results


def get_slug(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        return value.get("slug")
    return None


def vlan_summary(vlan: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not vlan:
        return None
    site = vlan.get("site") if isinstance(vlan.get("site"), dict) else {}
    return {
        "id": vlan.get("id"),
        "vid": vlan.get("vid"),
        "name": vlan.get("name"),
        "display": vlan.get("display"),
        "slug": vlan.get("slug"),
        "site": site.get("slug") or site.get("name"),
        "description": vlan.get("description", ""),
    }


def parse_service_ports(custom_fields: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = custom_fields.get("service_port")
    if not raw:
        return []

    services: List[Dict[str, Any]] = []
    for item in str(raw).split(","):
        entry = item.strip()
        if not entry or "-" not in entry:
            continue
        protocol, port = entry.split("-", 1)
        try:
            services.append(
                {
                    "protocol": protocol.upper(),
                    "port": int(port),
                    "raw": entry,
                }
            )
        except ValueError:
            continue
    return services


def interface_summary(iface: Dict[str, Any], ips: List[Dict[str, Any]]) -> Dict[str, Any]:
    tagged_vlans = [vlan_summary(vlan) for vlan in iface.get("tagged_vlans", [])]
    tagged_vlans = [item for item in tagged_vlans if item]
    untagged_vlan = vlan_summary(iface.get("untagged_vlan"))
    parent = iface.get("parent") or {}
    primary_type = iface.get("type", {}) if isinstance(iface.get("type"), dict) else {}
    mode = iface.get("mode", {}) if isinstance(iface.get("mode"), dict) else {}
    services: List[Dict[str, Any]] = []
    ip_entries: List[Dict[str, Any]] = []

    for ip in ips:
        parsed_services = parse_service_ports(ip.get("custom_fields", {}))
        services.extend(
            {
                "device": iface.get("device", {}).get("name"),
                "interface": iface.get("name"),
                "ip": ip.get("address", "").split("/")[0],
                **svc,
            }
            for svc in parsed_services
        )
        ip_entries.append(
            {
                "id": ip.get("id"),
                "address": ip.get("address"),
                "address_no_prefix": ip.get("address", "").split("/")[0],
                "family": ip.get("family", {}).get("value") if isinstance(ip.get("family"), dict) else None,
                "description": ip.get("description", ""),
                "custom_fields": ip.get("custom_fields", {}),
                "services": parsed_services,
            }
        )

    return {
        "id": iface.get("id"),
        "name": iface.get("name"),
        "label": iface.get("label", ""),
        "type": primary_type.get("value"),
        "type_label": primary_type.get("label"),
        "mode": mode.get("value"),
        "mode_label": mode.get("label"),
        "enabled": iface.get("enabled", True),
        "description": iface.get("description", ""),
        "parent": parent.get("name"),
        "parent_id": parent.get("id"),
        "mgmt_only": iface.get("mgmt_only", False),
        "untagged_vlan": untagged_vlan,
        "tagged_vlans": tagged_vlans,
        "ip_addresses": ip_entries,
        "listener_services": services,
    }


def build_groups(hostvars: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    groups: Dict[str, Any] = {}
    for host, vars_ in hostvars.items():
        role = vars_.get("netbox_device_role_slug") or "unknown"
        site = vars_.get("netbox_site_slug") or "unknown"
        status = vars_.get("netbox_status") or "unknown"
        for group_name in [
            f"device_roles_{role}",
            f"sites_{site}",
            f"status_{status}",
        ]:
            groups.setdefault(group_name, {"hosts": {}})
            groups[group_name]["hosts"][host] = {}
    return groups


def build_hostvars(device: Dict[str, Any]) -> Dict[str, Any]:
    role = device.get("role") or {}
    site = device.get("site") or {}
    device_type = device.get("device_type") or {}
    manufacturer = device_type.get("manufacturer") or {}
    primary_ip4 = device.get("primary_ip4") or {}

    hostvars = {
        "ansible_host": primary_ip4.get("address", "").split("/")[0] if primary_ip4 else None,
        "netbox_id": device.get("id"),
        "netbox_name": device.get("name"),
        "netbox_display_name": device.get("display", device.get("name")),
        "netbox_description": device.get("description", ""),
        "netbox_status": device.get("status", {}).get("value"),
        "netbox_device_type": device_type.get("model"),
        "netbox_device_type_slug": device_type.get("slug"),
        "netbox_device_role": role.get("name"),
        "netbox_device_role_slug": role.get("slug"),
        "netbox_manufacturer": manufacturer.get("name"),
        "netbox_site": site.get("name"),
        "netbox_site_slug": site.get("slug"),
        "network": {},
    }

    if device.get("name") == "staging-server":
        hostvars.update(
            {
                "ansible_user": "gijs",
                "ansible_password": "123GjH#@!",
                "ansible_connection": "ssh",
                "ansible_become": True,
                "ansible_become_method": "sudo",
                "ansible_become_password": "123GjH#@!",
            }
        )

    return hostvars


def build_device_payload(device: Dict[str, Any]) -> Dict[str, Any]:
    payload = build_hostvars(device)
    device_id = device.get("id")
    interfaces = paginate("/api/dcim/interfaces/", {"device_id": device_id})

    interface_ips: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for iface in interfaces:
        interface_ips[iface.get("id")].extend(paginate("/api/ipam/ip-addresses/", {"interface_id": iface.get("id")}))

    interface_entries = [interface_summary(iface, interface_ips.get(iface.get("id"), [])) for iface in interfaces]
    interface_entries = sorted(interface_entries, key=lambda item: (item["parent"] or "", item["name"]))

    if device.get("name") == "staging-server":
        eno1 = next((iface for iface in interface_entries if iface["name"] == "eno1"), None)
        eno1_ip = None
        if eno1:
            eno1_ip = next((ip["address_no_prefix"] for ip in eno1.get("ip_addresses", []) if ip.get("address_no_prefix")), None)
        if eno1_ip:
            payload["ansible_host"] = eno1_ip

    vlan_by_id: Dict[int, Dict[str, Any]] = {}
    for iface in interface_entries:
        for vlan in [iface.get("untagged_vlan")] + list(iface.get("tagged_vlans", [])):
            if vlan and vlan.get("id") is not None:
                vlan_by_id[vlan["id"]] = vlan

    ip_entries: List[Dict[str, Any]] = []
    listener_services: List[Dict[str, Any]] = []
    trunk_ports: List[Dict[str, Any]] = []
    management_interfaces: List[Dict[str, Any]] = []

    for iface in interface_entries:
        iface_view = {
            "name": iface["name"],
            "id": iface["id"],
            "mode": iface["mode"],
            "description": iface["description"],
            "parent": iface["parent"],
            "untagged_vlan": iface["untagged_vlan"],
            "tagged_vlans": iface["tagged_vlans"],
        }
        if iface["type"] != "virtual":
            if iface["mode"] == "tagged" or iface["tagged_vlans"]:
                trunk_ports.append(iface_view)
        if iface["name"].lower().startswith("mgmt") or iface["name"].lower().endswith("mgmt"):
            management_interfaces.append(iface_view)

        for ip in iface["ip_addresses"]:
            ip_entry = {
                "interface": iface["name"],
                "interface_id": iface["id"],
                "address": ip["address"],
                "address_no_prefix": ip["address_no_prefix"],
                "custom_fields": ip["custom_fields"],
                "services": ip["services"],
            }
            ip_entries.append(ip_entry)
            for svc in ip["services"]:
                listener_services.append(
                    {
                        "ip": ip["address_no_prefix"],
                        "address": ip["address"],
                        "interface": iface["name"],
                        "port": svc["port"],
                        "protocol": svc["protocol"],
                        "raw": svc["raw"],
                    }
                )

    network_profile: Dict[str, Any] = {
        "interfaces": interface_entries,
        "vlans": sorted(vlan_by_id.values(), key=lambda item: item["vid"]),
        "ip_addresses": ip_entries,
        "listener_services": listener_services,
        "trunk_ports": trunk_ports,
        "management_interfaces": management_interfaces,
    }

    if get_slug(device.get("role")) == "switch" or get_slug(device.get("device_type", {}).get("manufacturer")) == "cisco":
        network_profile["switch_ports"] = sorted(
            [
                {
                    "port": port["name"],
                    "mode": port["mode"],
                    "description": port["description"],
                    "native_vlan": port["untagged_vlan"]["vid"] if port["untagged_vlan"] else None,
                    "tagged_vlans": [v["vid"] for v in port["tagged_vlans"]],
                }
                for port in trunk_ports + [p for p in interface_entries if p["type"] != "virtual" and p["mode"] == "access"]
            ],
            key=lambda item: int(item["port"]) if str(item["port"]).isdigit() else str(item["port"]),
        )

    payload["network"] = network_profile
    return payload


def main() -> None:
    devices = paginate("/api/dcim/devices/")
    hostvars: Dict[str, Dict[str, Any]] = {}

    for device in devices:
        name = device.get("name") or f"device-{device.get('id')}"
        hostvars[name] = build_device_payload(device)

    inventory = {
        "all": {
            "hosts": hostvars,
            "children": build_groups(hostvars),
        }
    }

    with open(INVENTORY_OUTPUT, "w", encoding="utf-8") as handle:
        yaml.dump(
            inventory,
            handle,
            Dumper=NoAliasDumper,
            sort_keys=False,
            default_flow_style=False,
        )

    print(f"Wrote inventory snapshot to {INVENTORY_OUTPUT}")


if __name__ == "__main__":
    main()
