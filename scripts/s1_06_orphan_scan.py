#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S1-06 孤儿引用扫描"""
import sys
import json
import subprocess
import os

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('═══ S1-06 孤儿引用扫描 ═══')
print()

# 获取学习卡表全部record_id
print('【1 获取学习卡表全部record_id】')
card_ids = set()
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
    
    # 找record_id字段索引
    record_id_idx = None
    for i, f in enumerate(fields):
        if f == 'record_id' or f == 'recordId':
            record_id_idx = i
            break
    
    for rec in records:
        # record_id通常在返回的record_id字段或第一个字段
        if record_id_idx is not None and record_id_idx < len(rec):
            card_ids.add(str(rec[record_id_idx]))
        elif len(rec) > 0:
            # 尝试从返回结构中获取record_id
            pass
    
    has_more = data.get("has_more", False)
    if not has_more or len(records) == 0:
        break
    offset += len(records)

print(f'  学习卡record_id数: {len(card_ids)}')
print(f'  示例: {list(card_ids)[:5]}')
print()

# 获取流水表全部记录，提取卡片ID
print('【2 获取流水表全部记录，提取卡片ID】')
flow_card_ids = []
flow_records = []
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
    
    # 找卡片ID字段索引
    card_id_idx = None
    record_id_idx = None
    for i, f in enumerate(fields):
        if f == '卡片ID':
            card_id_idx = i
        if f == 'record_id' or f == 'recordId':
            record_id_idx = i
    
    for rec in records:
        record = {}
        for i, field in enumerate(fields):
            record[field] = rec[i] if i < len(rec) else None
        flow_records.append(record)
        
        if card_id_idx is not None and card_id_idx < len(rec):
            cid = rec[card_id_idx]
            if cid:
                flow_card_ids.append(str(cid))
    
    has_more = data.get("has_more", False)
    if not has_more or len(records) == 0:
        break
    offset += len(records)

print(f'  流水记录数: {len(flow_records)}')
print(f'  有卡片ID的流水数: {len(flow_card_ids)}')
print(f'  唯一卡片ID数: {len(set(flow_card_ids))}')
print()

# 集合比对：找孤儿引用
print('【3 集合比对：找孤儿引用】')
orphan_cards = set()
for cid in flow_card_ids:
    if cid not in card_ids:
        orphan_cards.add(cid)

print(f'  流水表中引用的卡片ID数: {len(set(flow_card_ids))}')
print(f'  学习卡表中存在的卡片ID数: {len(card_ids)}')
print(f'  孤儿引用（流水有但学习卡没有）: {len(orphan_cards)}')
if orphan_cards:
    print(f'  孤儿卡片ID列表: {orphan_cards}')
    
    # 查找引用孤儿卡片的流水记录
    print()
    print('  【引用孤儿卡片的流水记录】')
    for rec in flow_records:
        cid = rec.get('卡片ID')
        if cid and str(cid) in orphan_cards:
            print(f'    record_id={rec.get("record_id", "UNKNOWN")}, 卡片ID={cid}, 结果={rec.get("结果")}, 来源={rec.get("来源")}, 客户端时间戳={rec.get("客户端时间戳")}')
print()

# 检查recvtNKGDut2Ac当前状态
print('【4 检查recvtNKGDut2Ac当前状态】')
target = 'recvtNKGDut2Ac'
if target in card_ids:
    print(f'  {target} 在学习卡表中存在')
else:
    print(f'  {target} 不在学习卡表中（已删除或从未存在）')

# 检查流水表中是否有引用该卡片的记录
target_flows = [rec for rec in flow_records if str(rec.get('卡片ID', '')) == target]
print(f'  流水表中引用该卡片的记录数: {len(target_flows)}')
for rec in target_flows:
    print(f'    record_id={rec.get("record_id", "UNKNOWN")}, 结果={rec.get("结果")}, 来源={rec.get("来源")}')
print()

# 反向验证：学习卡表中是否有未被任何流水引用的卡片
print('【5 反向验证：未被流水引用的学习卡】')
referenced_cards = set(flow_card_ids)
unreferenced_cards = card_ids - referenced_cards
print(f'  学习卡总数: {len(card_ids)}')
print(f'  被流水引用的卡片数: {len(referenced_cards)}')
print(f'  未被流水引用的卡片数: {len(unreferenced_cards)}')
if unreferenced_cards:
    print(f'  未被引用的卡片ID: {list(unreferenced_cards)[:10]}')
print()

print('═══ 扫描完成 ═══')
