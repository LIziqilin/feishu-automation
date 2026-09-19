#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""读取基线文件关键内容"""
import json, os
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

with open('regression_baseline.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('=== 基线文件关键内容 ===')
print('版本:', data.get('baseline_version'))
print('生成时间:', data.get('generated_at'))
print('基线哈希:', data.get('_baseline_hash'))
print()
print('【表记录数】')
for k, v in data.get('table_counts', {}).items():
    print('  ' + k + ': ' + str(v) + '条')
print()
print('【学习卡状态分布】', data.get('card_status_distribution'))
print()
print('【流水结果分布】', data.get('flow_result_distribution'))
print()
print('【流水来源分布】', data.get('flow_source_distribution'))
print()
print('【不变量检查】')
for k, v in data.get('invariant_checks', {}).items():
    if k != '_summary':
        status = 'PASS' if v.get('pass') else 'FAIL'
        print('  ' + k + ': ' + status)
print('  汇总:', data.get('invariant_checks', {}).get('_summary'))
print()
print('【空值率>50%的字段】')
for table, fields in data.get('field_null_rates', {}).items():
    high_null = {k: v for k, v in fields.items() if v.get('null_rate_percent', 0) > 50}
    print('  ' + table + ': ' + str(len(high_null)) + '个')
    for fname, finfo in list(high_null.items())[:5]:
        print('    - ' + fname + ': ' + str(finfo['null_rate_percent']) + '% (' + str(finfo['null_count']) + '/' + str(finfo['total']) + ')')
print()
print('【汇总】', data.get('summary'))
