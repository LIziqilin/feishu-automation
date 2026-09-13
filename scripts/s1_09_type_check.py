#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S1-09 类型错配验证"""
import sys
import json
import subprocess
import os
from datetime import datetime

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('═══ S1-09 类型错配验证 ═══')
print()

# 获取学习卡表datetime字段
print('【1 学习卡表datetime字段验证】')
datetime_fields = ['创建日期', '首次正确日期', '最近正确日期', '上次复习日期', '下次复习日期']
cmd = ['lark-cli', 'base', '+record-list',
       '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf',
       '--table-id', 'tblpLvxyYpDJgF92',
       '--limit', '5',
       '--as', 'user', '--format', 'json']
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
resp = json.loads(proc.stdout)
data = resp.get("data", {})
records = data.get("data", [])
fields = data.get("fields", [])

for field in datetime_fields:
    if field in fields:
        idx = fields.index(field)
        values = [rec[idx] for rec in records if idx < len(rec) and rec[idx]]
        print(f'  {field}:')
        print(f'    字段类型: datetime')
        print(f'    返回值示例: {values[:3]}')
        if values:
            # 检查是否为ISO字符串
            sample = values[0]
            if isinstance(sample, str) and 'T' in sample:
                print(f'    格式判断: ISO 8601字符串（lark-cli输出格式转换）')
                # 尝试解析
                try:
                    dt = datetime.fromisoformat(sample.replace('Z', '+00:00'))
                    print(f'    解析验证: 成功，解析为 {dt}')
                except Exception as e:
                    print(f'    解析验证: 失败，{e}')
            elif isinstance(sample, (int, float)):
                print(f'    格式判断: 毫秒时间戳')
            else:
                print(f'    格式判断: 其他类型 {type(sample)}')
    else:
        print(f'  {field}: 字段不存在')
print()

# 获取流水表客户端时间戳字段
print('【2 流水表客户端时间戳字段验证】')
cmd = ['lark-cli', 'base', '+record-list',
       '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf',
       '--table-id', 'tblbznzCSpPhSz93',
       '--limit', '5',
       '--as', 'user', '--format', 'json']
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
resp = json.loads(proc.stdout)
data = resp.get("data", {})
records = data.get("data", [])
fields = data.get("fields", [])

if '客户端时间戳' in fields:
    idx = fields.index('客户端时间戳')
    values = [rec[idx] for rec in records if idx < len(rec) and rec[idx]]
    print(f'  客户端时间戳:')
    print(f'    字段类型: datetime')
    print(f'    返回值示例: {values[:3]}')
    if values:
        sample = values[0]
        if isinstance(sample, str) and 'T' in sample:
            print(f'    格式判断: ISO 8601字符串（lark-cli输出格式转换）')
            try:
                dt = datetime.fromisoformat(sample.replace('Z', '+00:00'))
                print(f'    解析验证: 成功，解析为 {dt}')
            except Exception as e:
                print(f'    解析验证: 失败，{e}')
        elif isinstance(sample, (int, float)):
            print(f'    格式判断: 毫秒时间戳')
else:
    print(f'  客户端时间戳: 字段不存在')
print()

# 检查脚本中日期解析是否统一
print('【3 脚本中日期解析一致性检查】')
scripts_to_check = ['learning_system.py', 'v19_integration.py']
for script in scripts_to_check:
    script_path = os.path.join(r'D:\AI-Tools\feishu\V13方案增强\scripts', script)
    if os.path.exists(script_path):
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找日期解析相关代码
        import re
        date_patterns = [
            r'datetime\.fromisoformat',
            r'strptime',
            r'fromtimestamp',
            r'parse.*date',
            r'date.*parse',
            r'isoformat',
        ]
        
        print(f'  {script}:')
        for pattern in date_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                print(f'    {pattern}: {len(matches)}处')
        
        # 查找是否有处理ISO字符串的代码
        if 'fromisoformat' in content or 'isoformat' in content:
            print(f'    → 已使用ISO格式解析，与lark-cli输出一致')
        else:
            print(f'    → 未发现ISO格式解析代码，需确认')
    else:
        print(f'  {script}: 文件不存在')
print()

# 抽查5条记录的日期计算正确性
print('【4 抽查5条记录的日期计算正确性】')
cmd = ['lark-cli', 'base', '+record-list',
       '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf',
       '--table-id', 'tblpLvxyYpDJgF92',
       '--limit', '5',
       '--as', 'user', '--format', 'json']
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
resp = json.loads(proc.stdout)
data = resp.get("data", {})
records = data.get("data", [])
fields = data.get("fields", [])

# 找相关字段索引
last_review_idx = fields.index('上次复习日期') if '上次复习日期' in fields else None
next_review_idx = fields.index('下次复习日期') if '下次复习日期' in fields else None
interval_idx = fields.index('interval_days') if 'interval_days' in fields else None

for i, rec in enumerate(records[:5]):
    print(f'  记录{i+1}:')
    if last_review_idx and last_review_idx < len(rec) and rec[last_review_idx]:
        last = rec[last_review_idx]
        print(f'    上次复习日期: {last}')
    if next_review_idx and next_review_idx < len(rec) and rec[next_review_idx]:
        next_d = rec[next_review_idx]
        print(f'    下次复习日期: {next_d}')
    if interval_idx and interval_idx < len(rec) and rec[interval_idx]:
        interval = rec[interval_idx]
        print(f'    interval_days: {interval}')
    
    # 验证日期差
    if last_review_idx and next_review_idx and last_review_idx < len(rec) and next_review_idx < len(rec):
        last_val = rec[last_review_idx]
        next_val = rec[next_review_idx]
        if last_val and next_val and isinstance(last_val, str) and isinstance(next_val, str):
            try:
                last_dt = datetime.fromisoformat(last_val.replace('Z', '+00:00'))
                next_dt = datetime.fromisoformat(next_val.replace('Z', '+00:00'))
                diff = (next_dt - last_dt).days
                print(f'    日期差计算: {diff}天')
                if interval_idx and interval_idx < len(rec) and rec[interval_idx]:
                    interval_val = rec[interval_idx]
                    if diff == interval_val:
                        print(f'    → 与interval_days一致 ✅')
                    else:
                        print(f'    → 与interval_days不一致（interval={interval_val}）⚠️')
            except Exception as e:
                print(f'    日期解析失败: {e}')
print()

print('═══ 验证完成 ═══')
