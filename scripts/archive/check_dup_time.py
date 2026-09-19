#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""查重复任务的创建时间"""
import subprocess, json, datetime

cmd = ["lark-cli", "base", "+record-list",
       "--base-token", "X8N1bvN3na99dFsyu0gcU8zTnHf",
       "--table-id", "tblz3H4lV7PCrBrX",
       "--limit", "200", "--format", "json"]
r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
d = json.loads(r.stdout)
data = d.get('data', {})
rows = data.get('data', [])
fields = data.get('fields', [])
rids = data.get('record_id_list', [])

print("字段:", fields)
print()
ni = fields.index('任务名称')
# 找创建时间/日期字段
for i, fn in enumerate(fields):
    if '创建' in fn:
        print(f"创建相关字段: 索引{i} = {fn}")

print()
print("=== 测试相关任务（含record_id和创建字段）===")
for idx, row in enumerate(rows):
    val = row[ni] if ni < len(row) else ''
    if isinstance(val, list):
        val = ''.join([x.get('text','') if isinstance(x,dict) else str(x) for x in val])
    if val and ('测试任务' in str(val) or '另一个测试' in str(val) or '第三个' in str(val) or '12345' in str(val)):
        rid = rids[idx] if idx < len(rids) else '?'
        # 打印所有字段
        print(f"任务: {val}")
        print(f"  record_id: {rid}")
        for i, fn in enumerate(fields):
            if ('创建' in fn or '时间' in fn or '日期' in fn) and i < len(row):
                v = row[i]
                if v and str(v) not in ('None','0',''):
                    if isinstance(v,(int,float)) and v > 1000000000000:
                        try:
                            v = datetime.datetime.fromtimestamp(v/1000).strftime('%Y-%m-%d %H:%M')
                        except: pass
                    print(f"  {fn}: {v}")
        print()
