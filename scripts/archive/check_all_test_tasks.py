#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""全面搜索测试任务"""
import subprocess, json

all_rows = []
offset = 0
while True:
    cmd = ["lark-cli", "base", "+record-list",
           "--base-token", "X8N1bvN3na99dFsyu0gcU8zTnHf",
           "--table-id", "tblz3H4lV7PCrBrX",
           "--limit", "200", "--offset", str(offset), "--format", "json"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    d = json.loads(r.stdout)
    data = d.get('data', {})
    rows = data.get('data', [])
    fields = data.get('fields', [])
    all_rows.extend(rows)
    if not data.get('has_more'):
        break
    offset += len(rows)
    if offset > 1000:
        break

print(f"任务总表共 {len(all_rows)} 条")
print()
print("=== 所有包含'测试'或'验收'或'消防'的任务 ===")
name_idx = fields.index('任务名称') if '任务名称' in fields else 0
status_idx = fields.index('状态') if '状态' in fields else 1
for row in all_rows:
    if isinstance(row, list):
        val = row[name_idx] if name_idx < len(row) else ''
        status = row[status_idx] if status_idx < len(row) else ''
        if isinstance(val, list):
            val = ''.join([x.get('text','') if isinstance(x,dict) else str(x) for x in val])
        if isinstance(status, list):
            status = '/'.join([x.get('text','') if isinstance(x,dict) else str(x) for x in status])
        if val and ('测试' in str(val) or '验收' in str(val) or '消防' in str(val) or '供电' in str(val) or '三网' in str(val)):
            print(f"  [{status}] {val}")
