#!/usr/bin/env python3
"""
Wrapper script to run the TCP listener deployment with sudo.

This script:
1. Runs the Ansible playbook to deploy TCP listeners based on NetBox data
2. Handles the sudo password prompt automatically
3. Provides a simple one-command interface

Usage:
    sudo ./reconcile.py
    # or
    ./reconcile.py  (will prompt for sudo password)
"""

import subprocess
import sys
import os

# Change to the ansible directory
ansible_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(ansible_dir)

print("=" * 70)
print("NetBox TCP Listener Deployment")
print("=" * 70)
print()

# Run the ansible playbook with become
# Note: When this script is run with sudo, ansible already has root via the wrapper
cmd = [
    'ansible-playbook',
    '-i', 'inventory.ini',
    'tcp_listener.yml',
    '-b',  # become (sudo) - will use the sudo privileges from the wrapper
]

print(f"Running: {' '.join(cmd)}")
print()

try:
    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True
    )
    
    # Print output
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    
    # Exit with same code as ansible
    sys.exit(result.returncode)
    
except KeyboardInterrupt:
    print("\nInterrupted by user")
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
