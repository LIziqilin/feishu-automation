#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S3-05 洞察归档验证"""
import sys
import json
import subprocess
import os

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('═══ S3-05 洞察归档验证 ═══')
print()

# 获取洞察笔记表全部字段
print('【1 洞察笔记表字段清单】')
cmd = ['lark-cli', 'base', '+field-list',
       '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf',
       '--table-id', 'tblaqKBl87V9C0q1',
       '--as', 'user', '--format', 'json']
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
resp = json.loads(proc.stdout)
data = resp.get("data", {})
fields = data.get("fields", [])
print(f'  字段总数: {len(fields)}')
for i, f in enumerate(fields):
    print(f'    {i+1}. {f.get("name")} ({f.get("type")})')
print()

# 获取洞察笔记表全部记录
print('【2 洞察笔记表记录及字段填充情况】')
all_records = []
offset = 0
while True:
    cmd = ['lark-cli', 'base', '+record-list',
           '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf',
           '--table-id', 'tblaqKBl87V9C0q1',
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
    field_names = data.get("fields", [])
    record_id_list = data.get("record_id_list", [])
    
    for i, rec in enumerate(records):
        record = {}
        for j, field in enumerate(field_names):
            record[field] = rec[j] if j < len(rec) else None
        if i < len(record_id_list):
            record['record_id'] = record_id_list[i]
        all_records.append(record)
    
    has_more = data.get("has_more", False)
    if not has_more or len(records) == 0:
        break
    offset += len(records)

print(f'  洞察记录数: {len(all_records)}')
print()

# 统计每个字段的填充率
print('【3 字段填充率统计】')
field_fill_stats = {}
for field in field_names:
    total = len(all_records)
    filled = 0
    for rec in all_records:
        val = rec.get(field)
        if val is not None and val != "" and val != [] and val != False:
            filled += 1
    fill_rate = filled / total * 100 if total > 0 else 0
    field_fill_stats[field] = (filled, total, fill_rate)

# 按填充率排序
sorted_fields = sorted(field_fill_stats.items(), key=lambda x: x[1][2], reverse=True)
print(f'  {"字段名":<20} {"填充":>6} {"总数":>6} {"填充率":>8}')
print('  ' + '-' * 50)
for field, (filled, total, rate) in sorted_fields:
    status = "✅" if rate > 50 else ("🟡" if rate > 0 else "🔴")
    print(f'  {field:<20} {filled:>6} {total:>6} {rate:>7.1f}% {status}')
print()

# 三个核心字段验证
print('【4 三个核心字段验证】')
core_fields = ['标签', '关联科目', 'AI摘要']
for field in core_fields:
    if field in field_fill_stats:
        filled, total, rate = field_fill_stats[field]
        print(f'  {field}:')
        print(f'    填充数: {filled}/{total} ({rate:.1f}%)')
        # 显示有值的记录
        for rec in all_records:
            val = rec.get(field)
            if val is not None and val != "" and val != []:
                if isinstance(val, list):
                    val_str = ', '.join(str(v) for v in val)
                else:
                    val_str = str(val)[:100]
                print(f'    {rec.get("record_id", "UNKNOWN")}: {val_str}')
                break  # 只显示第一条
    else:
        print(f'  {field}: 字段不存在')
print()

# 检查原问题记录recvuZtFqWu3ht
print('【5 原问题记录recvuZtFqWu3ht状态】')
target_found = False
for rec in all_records:
    if rec.get('record_id') == 'recvuZtFqWu3ht':
        target_found = True
        print(f'  记录存在: recvuZtFqWu3ht')
        # 统计该记录的填充字段数
        filled_count = 0
        for field in field_names:
            val = rec.get(field)
            if val is not None and val != "" and val != [] and val != False:
                filled_count += 1
        print(f'  填充字段数: {filled_count}/{len(field_names)}')
        print(f'  填充率: {filled_count/len(field_names)*100:.1f}%')
        # 显示三个核心字段值
        for field in core_fields:
            val = rec.get(field)
            if isinstance(val, list):
                val_str = ', '.join(str(v) for v in val) if val else '空'
            else:
                val_str = str(val)[:100] if val else '空'
            print(f'    {field}: {val_str}')
        break
if not target_found:
    print(f'  记录recvuZtFqWu3ht不存在（可能已删除或为测试数据已清理）')
print()

# 检查InsightArchiver代码实现
print('【6 InsightArchiver代码实现检查】')
script_path = r'D:\AI-Tools\feishu\V13方案增强\scripts\v19_integration.py'
if os.path.exists(script_path):
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查关键方法
    methods = ['extract_keywords', 'extract_subject', 'generate_summary', 'archive_insight']
    for method in methods:
        if method in content:
            # 找方法定义行号
            import re
            match = re.search(rf'def {method}\(', content)
            if match:
                line_num = content[:match.start()].count('\n') + 1
                print(f'  {method}: 存在（第{line_num}行）')
            else:
                print(f'  {method}: 存在')
        else:
            print(f'  {method}: 不存在 ❌')
    
    # 检查INSIGHT_TABLE配置
    if 'INSIGHT_TABLE' in content:
        import re
        match = re.search(r'INSIGHT_TABLE\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            table_id = match.group(1)
            print(f'  INSIGHT_TABLE: {table_id}')
            if table_id == 'tblaqKBl87V9C0q1':
                print(f'    → 配置正确，与实际表ID一致 ✅')
            else:
                print(f'    → 配置可能不正确，实际表ID为tblaqKBl87V9C0q1 ⚠️')
    else:
        print(f'  INSIGHT_TABLE: 未配置 ❌')
else:
    print(f'  v19_integration.py: 文件不存在')
print()

print('═══ 验证完成 ═══')
