#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V6-01 数据层验证：检查错误supersede记录 + 连续正确统计"""
import sys
import json
import subprocess
import os

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('═══ V6-01 数据层验证 ═══')
print()

# 获取全部流水
print('【1 获取全部流水记录】')
all_flows = []
offset = 0
while True:
    cmd = ['lark-cli', 'base', '+record-list',
           '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf',
           '--table-id', 'tblbznzCSpPhSz93',
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
        flow = {}
        for i, field in enumerate(fields):
            flow[field] = rec[i] if i < len(rec) else None
        all_flows.append(flow)
    
    has_more = data.get("has_more", False)
    if not has_more or len(records) == 0:
        break
    offset += len(records)

print(f'  流水总记录数: {len(all_flows)}')
print()

# 按卡片ID分组
from collections import defaultdict
card_flows = defaultdict(list)
for f in all_flows:
    card_id = f.get("卡片ID", "")
    if card_id:
        card_flows[card_id].append(f)

print(f'  涉及卡片数: {len(card_flows)}')
print()

# 检查错误supersede：结果∈{会,不会,模糊}且superseded=TRUE且其后一条记录是INIT
print('【2 检查错误supersede记录】')
print('  判定方法：对每张卡，若存在结果∈{会,不会,模糊}且superseded=TRUE')
print('  且其后一条记录是INIT → 即为错误supersede')
print()

error_supersede_count = 0
error_details = []

for card_id, flows in card_flows.items():
    # 按客户端时间戳排序
    flows_sorted = sorted(flows, key=lambda x: str(x.get("客户端时间戳", "") or ""))
    
    for i, f in enumerate(flows_sorted):
        result = f.get("结果", "")
        # 处理数组类型（select字段返回数组）
        if isinstance(result, list):
            result = result[0] if result else ""
        superseded = f.get("superseded", False)
        # 处理数组类型
        if isinstance(superseded, list):
            superseded = superseded[0] if superseded else False
        
        # 检查是否是被错误supersede的有效答题记录
        if result in {"会", "不会", "模糊"} and superseded == True:
            # 检查其后一条记录是否是INIT
            if i + 1 < len(flows_sorted):
                next_result = flows_sorted[i+1].get("结果", "")
                if isinstance(next_result, list):
                    next_result = next_result[0] if next_result else ""
                if next_result == "INIT":
                    error_supersede_count += 1
                    error_details.append({
                        "card_id": card_id,
                        "record_id": f.get("_record_id", ""),
                        "result": result,
                        "next_result": next_result,
                        "timestamp": f.get("客户端时间戳", "")
                    })

print(f'  错误supersede记录数: {error_supersede_count}')
if error_details:
    print('  错误详情:')
    for e in error_details[:10]:
        print(f'    卡片={e["card_id"][:15]}..., 结果={e["result"]}, 下一条={e["next_result"]}, 时间={e["timestamp"]}')
else:
    print('  ✅ 无错误supersede记录')
print()

# 统计各结果类型的superseded情况
print('【3 各结果类型superseded统计】')
result_superseded_stats = defaultdict(lambda: {"total": 0, "superseded": 0})
for f in all_flows:
    result = f.get("结果", "")
    if isinstance(result, list):
        result = result[0] if result else ""
    superseded = f.get("superseded", False)
    if isinstance(superseded, list):
        superseded = superseded[0] if superseded else False
    result_superseded_stats[result]["total"] += 1
    if superseded:
        result_superseded_stats[result]["superseded"] += 1

for result, stats in sorted(result_superseded_stats.items(), key=lambda x: str(x[0])):
    print(f'  {result}: 总数={stats["total"]}, superseded={stats["superseded"]}')
print()

# 检查INIT记录是否被superseded
print('【4 INIT记录superseded检查】')
init_superseded = 0
for f in all_flows:
    result = f.get("结果", "")
    if isinstance(result, list):
        result = result[0] if result else ""
    if result == "INIT":
        superseded = f.get("superseded", False)
        if isinstance(superseded, list):
            superseded = superseded[0] if superseded else False
        if superseded:
            init_superseded += 1
print(f'  INIT被superseded的记录数: {init_superseded}')
if init_superseded == 0:
    print('  ✅ INIT记录未被错误supersede')
print()

# 统计最高连续正确值
print('【5 最高连续正确值统计】')
print('  （排除superseded=TRUE和非答题记录）')
max_consecutive = 0
max_card = None
consecutive_stats = []

for card_id, flows in card_flows.items():
    # 按客户端时间戳排序
    flows_sorted = sorted(flows, key=lambda x: str(x.get("客户端时间戳", "") or ""))
    
    # 过滤有效答题记录
    valid_flows = []
    for f in flows_sorted:
        result = f.get("结果", "")
        if isinstance(result, list):
            result = result[0] if result else ""
        superseded = f.get("superseded", False)
        if isinstance(superseded, list):
            superseded = superseded[0] if superseded else False
        if result in {"会", "不会", "模糊"} and superseded != True:
            valid_flows.append(f)
    
    # 计算连续正确（从最近一条往前数，遇到不会/模糊停止）
    consecutive = 0
    for f in reversed(valid_flows):
        result = f.get("结果", "")
        if isinstance(result, list):
            result = result[0] if result else ""
        if result == "会":
            consecutive += 1
        else:
            break
    
    if consecutive > 0:
        consecutive_stats.append((card_id, consecutive))
    if consecutive > max_consecutive:
        max_consecutive = consecutive
        max_card = card_id

print(f'  最高连续正确值: {max_consecutive}')
print(f'  达到≥3的卡片数: {sum(1 for _, c in consecutive_stats if c >= 3)}')
print(f'  达到≥2的卡片数: {sum(1 for _, c in consecutive_stats if c >= 2)}')
print(f'  有连续正确的卡片数: {len(consecutive_stats)}')
if max_card:
    print(f'  最高连续正确卡片: {max_card}')
print()

# 检查卡片状态
print('【6 卡片状态统计】')
cmd = ['lark-cli', 'base', '+record-list',
       '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf',
       '--table-id', 'tblpLvxyYpDJgF92',
       '--limit', '200',
       '--as', 'user', '--format', 'json']
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
if proc.returncode == 0:
    resp = json.loads(proc.stdout)
    data = resp.get("data", {})
    records = data.get("data", [])
    fields = data.get("fields", [])
    
    status_stats = defaultdict(int)
    for rec in records:
        for i, field in enumerate(fields):
            if field == "状态":
                status = rec[i] if i < len(rec) else None
                if isinstance(status, list):
                    status = status[0] if status else None
                status_stats[str(status)] += 1
    
    print(f'  卡片总数: {len(records)}')
    for status, count in sorted(status_stats.items()):
        print(f'  {status}: {count}')
else:
    print(f'  获取卡片失败: {proc.stderr}')

print()
print('═══ 验证完成 ═══')
