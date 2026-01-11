#!/usr/bin/env python3
"""
Debug script to check what monitor IDs are being passed to Bar
"""

import sys
import os
import json

sys.path.insert(0, os.path.expanduser('~/.config/Ax-Shell'))

from utils.monitor_manager import get_monitor_manager

# Load config
config_file = os.path.expanduser('~/.config/Ax-Shell/config/config.json')
with open(config_file) as f:
    config = json.load(f)

print("="*60)
print("MONITOR ID DEBUGGING")
print("="*60)

monitor_manager = get_monitor_manager()
all_monitors = monitor_manager.get_monitors()

print(f"\nAll monitors from monitor_manager:")
for m in all_monitors:
    ws_range = monitor_manager.get_workspace_range_for_monitor(m['id'])
    print(f"  {m['name']:12s} - ID: {m['id']}, X: {m['x']:5d}, Workspaces: {ws_range[0]:2d}-{ws_range[1]:2d}")

selected_monitors_config = config.get("selected_monitors", [])
print(f"\nselected_monitors from config: {selected_monitors_config}")

# Simulate what main.py does
if not selected_monitors_config:
    monitors = all_monitors
    print("\nNo specific monitors selected, using all")
else:
    monitors = []
    selected_monitor_names = set(selected_monitors_config)
    
    for monitor in all_monitors:
        monitor_name = monitor.get('name', f'monitor-{monitor.get("id", 0)}')
        if monitor_name in selected_monitor_names:
            monitors.append(monitor)

print(f"\nFiltered monitors list that gets passed to Bar:")
for m in monitors:
    ws_range = monitor_manager.get_workspace_range_for_monitor(m['id'])
    print(f"  {m['name']:12s} - ID: {m['id']}, X: {m['x']:5d}, Workspaces: {ws_range[0]:2d}-{ws_range[1]:2d}")

print("\n" + "="*60)
print("DIAGNOSIS:")
print("="*60)
print("\nWhen Bar(monitor_id=m['id']) is called:")
for m in monitors:
    ws_range = monitor_manager.get_workspace_range_for_monitor(m['id'])
    print(f"  Bar for {m['name']:12s} gets monitor_id={m['id']} → displays workspaces {ws_range[0]:2d}-{ws_range[1]:2d}")

print("\n" + "="*60)
