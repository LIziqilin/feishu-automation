#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-S1-04 空转字段确认"""
import sys
import json
import subprocess

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
import learning_system as ls

BASE_TOKEN = ls.BASE_TOKEN
CARD_TABLE = ls.CARD_TABLE
FLOW_TABLE = ls.FLOW_TABLE

def get_fields(table_id):
    """获取表字段列表"""
    result = subprocess.run([
        'lark-cli', 'base', '+field-list',
        '--base-token', BASE_TOKEN,
        '--table-id', table_id,
        '--as', 'user', '--format', 'json'
    ], capture_output=True, text=True, cwd=r'D:\AI-Tools\feishu\V13方案增强\scripts')
    data = json.loads(result.stdout)
    return data['data']['fields']

# 学习卡表空转字段检查
print('=' * 60)
print('学习卡表空转字段检查')
print('=' * 60)
all_cards = ls.get_all_cards()
card_fields = get_fields(CARD_TABLE)
print('学习卡表记录数: ' + str(len(all_cards)))
print('学习卡表字段数: ' + str(len(card_fields)))

# 检查每个字段的空值率
print('\n空值率>80%的字段:')
empty_fields = []
for field in card_fields:
    fname = field.get('name', '')
    empty_count = 0
    for card in all_cards:
        val = card.get(fname)
        if val is None or val == '' or val == [] or val == 0:
            empty_count += 1
    empty_rate = empty_count / len(all_cards) * 100 if all_cards else 0
    if empty_rate > 80:
        empty_fields.append((fname, empty_rate))
        print('  ' + fname + ': ' + str(round(empty_rate, 1)) + '% 空值')

print('\n空转字段总数: ' + str(len(empty_fields)))

# 流水表空转字段检查
print('\n' + '=' * 60)
print('流水表空转字段检查')
print('=' * 60)
all_flows = ls.get_all_flows()
flow_fields = get_fields(FLOW_TABLE)
print('流水表记录数: ' + str(len(all_flows)))
print('流水表字段数: ' + str(len(flow_fields)))

print('\n空值率>80%的字段:')
flow_empty_fields = []
for field in flow_fields:
    fname = field.get('name', '')
    empty_count = 0
    for flow in all_flows:
        val = flow.get(fname)
        if val is None or val == '' or val == [] or val == 0:
            empty_count += 1
    empty_rate = empty_count / len(all_flows) * 100 if all_flows else 0
    if empty_rate > 80:
        flow_empty_fields.append((fname, empty_rate))
        print('  ' + fname + ': ' + str(round(empty_rate, 1)) + '% 空值')

print('\n流水表空转字段总数: ' + str(len(flow_empty_fields)))

# 总结
print('\n' + '=' * 60)
print('S1-04 空转字段处置结论')
print('=' * 60)
print('学习卡表空转字段（' + str(len(empty_fields)) + '个）:')
for fname, rate in empty_fields:
    print('  - ' + fname + ' (' + str(round(rate, 1)) + '%空值) → 保留为预留字段（用户已确认）')

print('\n流水表空转字段（' + str(len(flow_empty_fields)) + '个）:')
for fname, rate in flow_empty_fields:
    if fname == 'untrusted':
        print('  - ' + fname + ' (' + str(round(rate, 1)) + '%空值) → 已接线（R7 hash检测，默认FALSE）')
    elif fname == 'revision':
        print('  - ' + fname + ' (' + str(round(rate, 1)) + '%空值) → 已接线（R9 编辑消息，默认1）')
    else:
        print('  - ' + fname + ' (' + str(round(rate, 1)) + '%空值) → 待确认')
