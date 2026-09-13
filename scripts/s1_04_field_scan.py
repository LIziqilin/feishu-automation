#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S1-04 学习卡空转字段扫描"""
import sys
import json
import subprocess
import os

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('═══ S1-04 学习卡空转字段扫描 ═══')
print()

# 获取学习卡表全部记录
print('【1 获取学习卡表全部记录】')
all_records = []
offset = 0
while True:
    cmd = ['lark-cli', 'base', '+record-list',
           '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf',
           '--table-id', 'tblpLvxyYpDJgF92',
           '--limit', '200',
           '--offset', str(offset),
           '--as', 'user', '--format', 'json']
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        print(f'  获取失败: {proc.stderr}')
        break
    resp = json.loads(proc.stdout)
    data = resp.get("data", {})
    records = data.get("data", [])
    fields = data.get("fields", [])
    
    for rec in records:
        record = {}
        for i, field in enumerate(fields):
            record[field] = rec[i] if i < len(rec) else None
        all_records.append(record)
    
    has_more = data.get("has_more", False)
    if not has_more or len(records) == 0:
        break
    offset += len(records)

print(f'  学习卡记录数: {len(all_records)}')
print(f'  字段数: {len(fields)}')
print()

# 扫描每个字段的空值率
print('【2 字段空值率扫描】')
field_stats = []
for field in fields:
    total = len(all_records)
    empty = 0
    for rec in all_records:
        val = rec.get(field)
        if val is None or val == "" or val == [] or val == False:
            empty += 1
    empty_rate = empty / total * 100 if total > 0 else 0
    field_stats.append((field, total, empty, empty_rate))

# 按空值率排序
field_stats.sort(key=lambda x: x[3], reverse=True)

print(f'  {"字段名":<20} {"总数":>6} {"空值":>6} {"空值率":>8} {"状态"}')
print('  ' + '-' * 70)
for field, total, empty, rate in field_stats:
    status = "🔴空转" if rate > 80 else ("🟡部分" if rate > 30 else "✅正常")
    print(f'  {field:<20} {total:>6} {empty:>6} {rate:>7.1f}% {status}')
print()

# 原问题中的空转字段确认
print('【3 原问题空转字段确认】')
original_idle_fields = ['SOP关联', 'cold_archived', '前置依赖', '关联任务', '实战留痕', '底层规律', 
                        '应用场景', '费曼自检', '费曼打分_AI', '标准答案_AI', '知识点分类_AI',
                        '来源知识ID', 'intro_offset']
for field in original_idle_fields:
    if field in fields:
        idx = fields.index(field)
        total = len(all_records)
        empty = sum(1 for rec in all_records if rec.get(field) is None or rec.get(field) == "" or rec.get(field) == [] or rec.get(field) == False)
        rate = empty / total * 100 if total > 0 else 0
        status = "🔴空转" if rate > 80 else ("🟡部分" if rate > 30 else "✅正常")
        print(f'  {field}: 空值率={rate:.1f}% {status}')
    else:
        print(f'  {field}: 字段不存在')
print()

# 连续正确次数字段确认
print('【4 连续正确次数字段确认】')
if '连续正确次数' in fields:
    values = []
    for rec in all_records:
        val = rec.get('连续正确次数')
        if val is not None and val != "":
            values.append(val)
    print(f'  有值记录数: {len(values)}/{len(all_records)}')
    print(f'  值分布: {sorted(set(values))[:10]}')
    if values:
        print(f'  最大值: {max(values)}')
        print(f'  非零记录数: {sum(1 for v in values if v > 0)}')
else:
    print('  字段不存在')
print()

# 关键字段写入者确认
print('【5 关键字段写入情况】')
key_fields = ['连续正确次数', '掌握度M', '记忆等级', '复习次数', 'interval_days', 
              'last_result', '卡片状态', '上次复习日期', '下次复习日期', 'cold_archived']
for field in key_fields:
    if field in fields:
        total = len(all_records)
        empty = sum(1 for rec in all_records if rec.get(field) is None or rec.get(field) == "" or rec.get(field) == [] or rec.get(field) == False)
        rate = empty / total * 100 if total > 0 else 0
        print(f'  {field}: 空值率={rate:.1f}% {"✅有写入" if rate < 80 else "🔴空转"}')
print()

print('═══ 扫描完成 ═══')
