#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""全面搜索第三/测试，打印全部67条任务名"""
import subprocess, json

cmd = ["lark-cli", "base", "+record-list",
       "--base-token", "X8N1bvN3na99dFsyu0gcU8zTnHf",
       "--table-id", "tblz3H4lV7PCrBrX",
       "--limit", "200", "--format", "json"]
r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
d = json.loads(r.stdout)
data = d.get('data', {})
rows = data.get('data', [])
fields = data.get('fields', [])
ni = fields.index('任务名称')
si = fields.index('状态')

print(f"共{len(rows)}条，全部任务名：")
for idx, row in enumerate(rows):
    val = row[ni] if ni < len(row) else ''
    status = row[si] if si < len(row) else ''
    if isinstance(val, list):
        val = ''.join([x.get('text','') if isinstance(x,dict) else str(x) for x in val])
    if isinstance(status, list):
        status = '/'.join([str(x) for x in status])
    # 标记含第三/测试的
    mark = " <<<" if ('第三' in str(val) or '测试' in str(val)) else ""
    if mark:
        print(f"  [{status}] repr={repr(val)}{mark}")
print()
print("含'第三'的记录：")
found = False
for row in rows:
    val = row[ni] if ni < len(row) else ''
    if isinstance(val, list):
        val = ''.join([x.get('text','') if isinstance(x,dict) else str(x) for x in val])
    if '第三' in str(val):
        print(f"  找到: {repr(val)}")
        found = True
if not found:
    print("  ❌ 完全没有含'第三'的记录！")
