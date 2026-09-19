#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查最近任务"""
import subprocess, json

cmd = ["lark-cli", "base", "+record-list",
       "--base-token", "X8N1bvN3na99dFsyu0gcU8zTnHf",
       "--table-id", "tblz3H4lV7PCrBrX",
       "--limit", "15", "--format", "json"]
r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
d = json.loads(r.stdout)
data = d.get('data', {})
rows = data.get('data', [])
fields = data.get('fields', [])
print("字段列表:", fields[:8])
print(f"共{len(rows)}条")
print()
# 找任务名称字段索引
name_idx = 0
for i, fn in enumerate(fields):
    if '名称' in str(fn) or '任务' in str(fn):
        name_idx = i
        break
for row in rows[:15]:
    if isinstance(row, list):
        val = row[name_idx] if name_idx < len(row) else '?'
        if isinstance(val, list):
            val = ''.join([x.get('text','') if isinstance(x,dict) else str(x) for x in val])
        print(f"- {val}")
    elif isinstance(row, dict):
        print("-", list(row.items())[:3])
