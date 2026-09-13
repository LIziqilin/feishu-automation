#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S1-06 孤儿引用扫描（最终修正版）"""
import sys
import json
import subprocess
import os

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('═══ S1-06 孤儿引用扫描（最终修正版）═══')
print()

# 获取学习卡表全部record_id（使用record_id_list）
print('【1 获取学习卡表全部record_id】')
card_ids = set()
card_id_to_title = {}
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
    record_id_list = data.get("record_id_list", [])
    
    # 找卡片问题正面字段索引
    title_idx = None
    for i, f in enumerate(fields):
        if f == '卡片问题正面':
            title_idx = i
            break
    
    for i, rid in enumerate(record_id_list):
        card_ids.add(str(rid))
        if title_idx is not None and i < len(records) and title_idx < len(records[i]):
            card_id_to_title[str(rid)] = records[i][title_idx]
    
    has_more = data.get("has_more", False)
    if not has_more or len(records) == 0:
        break
    offset += len(records)

print(f'  学习卡记录数: {len(card_ids)}')
print(f'  学习卡record_id示例: {list(card_ids)[:5]}')
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
    
    for rec in records:
        record = {}
        for i, field in enumerate(fields):
            record[field] = rec[i] if i < len(rec) else None
        flow_records.append(record)
        
        cid = record.get('卡片ID')
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
for cid in set(flow_card_ids):
    if cid not in card_ids:
        orphan_cards.add(cid)

print(f'  流水表中引用的唯一卡片ID数: {len(set(flow_card_ids))}')
print(f'  学习卡表中存在的卡片ID数: {len(card_ids)}')
print(f'  孤儿引用（流水有但学习卡没有）: {len(orphan_cards)}')
if orphan_cards:
    print(f'  孤儿卡片ID列表: {sorted(orphan_cards)}')
    
    # 查找引用孤儿卡片的流水记录
    print()
    print('  【引用孤儿卡片的流水记录详情】')
    orphan_count = 0
    for rec in flow_records:
        cid = rec.get('卡片ID')
        if cid and str(cid) in orphan_cards:
            orphan_count += 1
            result = rec.get('结果')
            if isinstance(result, list):
                result = result[0] if result else None
            source = rec.get('来源')
            if isinstance(source, list):
                source = source[0] if source else None
            if orphan_count <= 10:  # 只显示前10条
                print(f'    卡片ID={cid}, 结果={result}, 来源={source}, 时间={rec.get("客户端时间戳")}')
    print(f'    ... 共{orphan_count}条引用孤儿卡片的流水')
print()

# 检查recvtNKGDut2Ac当前状态
print('【4 检查recvtNKGDut2Ac当前状态】')
target = 'recvtNKGDut2Ac'
if target in card_ids:
    print(f'  {target} 在学习卡表中存在')
    print(f'  卡片标题: {card_id_to_title.get(target, "UNKNOWN")}')
else:
    print(f'  {target} 不在学习卡表中（已删除或从未存在）')

target_flows = [rec for rec in flow_records if str(rec.get('卡片ID', '')) == target]
print(f'  流水表中引用该卡片的记录数: {len(target_flows)}')
print()

# 反向验证：学习卡表中是否有未被任何流水引用的卡片
print('【5 反向验证：未被流水引用的学习卡】')
referenced_cards = set(flow_card_ids)
unreferenced_cards = card_ids - referenced_cards
print(f'  学习卡总数: {len(card_ids)}')
print(f'  被流水引用的卡片数: {len(referenced_cards)}')
print(f'  未被流水引用的卡片数: {len(unreferenced_cards)}')
if unreferenced_cards:
    print(f'  未被引用的卡片ID: {sorted(list(unreferenced_cards))[:10]}')
    for cid in sorted(list(unreferenced_cards))[:5]:
        print(f'    {cid}: {card_id_to_title.get(cid, "UNKNOWN")}')
print()

# 验证流水引用的卡片ID是否都在学习卡表中
print('【6 验证：流水引用的卡片ID是否都在学习卡表中】')
all_referenced = set(flow_card_ids)
missing = all_referenced - card_ids
extra = card_ids - all_referenced
print(f'  流水引用的卡片ID数: {len(all_referenced)}')
print(f'  学习卡表中卡片ID数: {len(card_ids)}')
print(f'  交集数: {len(all_referenced & card_ids)}')
print(f'  流水有但学习卡没有（孤儿）: {len(missing)}')
print(f'  学习卡有但流水没有（未引用）: {len(extra)}')
print()

print('═══ 扫描完成 ═══')
