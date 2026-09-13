#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-S1-06 孤儿引用扫描检查"""
import sys
sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
import learning_system as ls

# 获取所有流水记录
all_flows = ls.get_all_flows()
print(f'总流水记录数: {len(all_flows)}')

# 查找孤儿记录
orphan_flows = [f for f in all_flows if f.get('卡片ID') == 'recvtNKGDut2Ac']
print(f'孤儿记录数: {len(orphan_flows)}')
for f in orphan_flows:
    rid = f.get('_record_id')
    cid = f.get('卡片ID')
    eid = f.get('event_id')
    result = f.get('结果')
    source = f.get('来源')
    print(f'  record_id: {rid}')
    print(f'  卡片ID: {cid}')
    print(f'  event_id: {eid}')
    print(f'  结果: {result}')
    print(f'  来源: {source}')
    print()

# 检查学习卡片表中是否存在该卡片
all_cards = ls.get_all_cards()
card_ids = [c.get('_record_id') for c in all_cards]
print(f'学习卡片表记录数: {len(all_cards)}')
print(f'recvtNKGDut2Ac是否在学习卡片表中: {"recvtNKGDut2Ac" in card_ids}')
