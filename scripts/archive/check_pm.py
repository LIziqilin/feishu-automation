#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""找processed_messages里所有create_task记录"""
import json

with open('.processed_messages.json', encoding='utf-8') as f:
    pm = json.load(f)

print(f"已处理消息共{len(pm)}条")
print()
print("=== 所有action=create_task的记录 ===")
create_records = []
for mid, info in pm.items():
    action = info.get('action','')
    if 'create' in action or 'task' in action:
        create_records.append((mid, info))
        print(f"{mid}  action={action}  at={info.get('processed_at')}")

print()
print("=== 13:25-13:35处理的所有消息 ===")
for mid, info in sorted(pm.items(), key=lambda x: x[1].get('processed_at','')):
    at = info.get('processed_at','')
    if '2026-09-15T13:2' in at or '2026-09-15T13:3' in at:
        print(f"{at[11:19]}  {mid}  action={info.get('action')}")
