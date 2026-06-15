#!/usr/bin/env python3
"""Refresh the generated inventory and run the remote reconciliation playbook."""

from __future__ import annotations

import os
import subprocess
import sys


ansible_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(ansible_dir)

print("=" * 70)
print("NetBox Reconciliation")
print("=" * 70)
print()

commands = [
    [sys.executable, "generate_inventory.py"],
    ["ansible-playbook", "-i", "inventory_snapshot.yml", "reconcile_staging_server.yml", "--limit", "staging-server"],
]

for cmd in commands:
    print(f"Running: {' '.join(cmd)}")
    print()
    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        if result.returncode != 0:
            sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
