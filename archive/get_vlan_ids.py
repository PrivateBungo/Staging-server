#!/usr/bin/env python3
import subprocess
import sys
import json

if len(sys.argv) < 2:
    print(json.dumps([]))
    sys.exit(0)

parent_if = sys.argv[1]

result = subprocess.run(
    ['ip', '-o', 'link', 'show'],
    capture_output=True, text=True
)

vlan_ids = []
for line in result.stdout.splitlines():
    if parent_if + '.' in line:
        # Example: "42: enp1s0.2000@enp1s0: <BROADCAST..."
        parts = line.split(':')
        if len(parts) > 1:
            ifname = parts[1].strip().split('@')[0].split()[0]
            if ifname.startswith(parent_if + '.'):
                vid = ifname.split('.')[1]
                if vid.isdigit():
                    vlan_ids.append(int(vid))

print(json.dumps(sorted(set(vlan_ids))))
