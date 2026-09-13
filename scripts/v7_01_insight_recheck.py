#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V7-01 S3-05 洞察归档结构化 复核验证脚本"""
import sys, os, json, subprocess
sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

from v19_integration import BASE_TOKEN, LARK_CLI

# 洞察笔记表ID
INSIGHT_TABLE = "tblaqKBl87V9C0q1"

print('=' * 60)
print('V7-01 S3-05 洞察归档结构化 复核验证')
print('=' * 60)

# 步骤1: 真实触发handle_insight
print('\n【步骤1】真实触发handle_insight')
test_insight = "洞察：V7-01复核测试，学习系统的间隔重复算法需要结合遗忘曲线优化，同时关注用户倦怠期的自动恢复机制"

# 直接导入并调用handle_insight
from task_insight_extension import handle_insight, INSIGHT_ARCHIVER_AVAILABLE
print(f'  INSIGHT_ARCHIVER_AVAILABLE: {INSIGHT_ARCHIVER_AVAILABLE}')

success, result = handle_insight(test_insight)
print(f'  handle_insight返回: success={success}, result={result}')

if not success:
    print(f'  ❌ 失败: handle_insight调用失败')
    sys.exit(1)

record_id = result
print(f'  洞察记录ID: {record_id}')

# 步骤2: 用record-get查询该记录，确认填充字段数
print('\n【步骤2】查询洞察记录，确认填充字段数')
cmd = [LARK_CLI, 'base', '+record-get',
       '--base-token', BASE_TOKEN, '--table-id', INSIGHT_TABLE,
       '--record-id', record_id, '--as', 'user', '--format', 'json']
r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=True)
data = json.loads(r.stdout)

fields = data.get('data', {}).get('fields', [])
record_data = data.get('data', {}).get('data', [[]])[0]

print(f'  总字段数: {len(fields)}')
filled_count = 0
empty_count = 0
filled_fields = []
empty_fields = []

for i, field_name in enumerate(fields):
    value = record_data[i] if i < len(record_data) else None
    if value is None or value == "" or value == [] or value == {}:
        empty_count += 1
        empty_fields.append(field_name)
    else:
        filled_count += 1
        filled_fields.append((field_name, str(value)[:80]))

print(f'  已填充字段数: {filled_count}')
print(f'  空字段数: {empty_count}')
print(f'\n  已填充字段:')
for fname, fval in filled_fields:
    print(f'    ✅ {fname}: {fval}')

print(f'\n  空字段:')
for fname in empty_fields[:10]:
    print(f'    ❌ {fname}')
if len(empty_fields) > 10:
    print(f'    ... 还有{len(empty_fields)-10}个空字段')

# 步骤3: 验证三个核心字段
print('\n【步骤3】验证三个核心字段（标签/关联科目/AI摘要）')
core_fields = {
    '标签': None,
    '关联科目': None,
    'AI摘要': None
}

for i, field_name in enumerate(fields):
    if field_name in core_fields:
        value = record_data[i] if i < len(record_data) else None
        core_fields[field_name] = value

all_core_filled = True
for fname, fval in core_fields.items():
    if fval is None or fval == "" or fval == []:
        print(f'  ❌ {fname}: 空（未填充）')
        all_core_filled = False
    else:
        print(f'  ✅ {fname}: {str(fval)[:100]}')

# 步骤4: 判定
print('\n【步骤4】判定')
print(f'  填充率: {filled_count}/{len(fields)} = {filled_count/len(fields)*100:.1f}%')
print(f'  三个核心字段全部填充: {all_core_filled}')

if filled_count >= 15 and all_core_filled:
    print(f'  ✅ L2 通过: 填充字段数≥15且三个核心字段全部填充')
    l2_pass = True
elif filled_count >= 9 and all_core_filled:
    print(f'  🟡 部分通过: 填充字段数{filled_count}（≥9但<15），三个核心字段全部填充')
    l2_pass = False
else:
    print(f'  ❌ 不通过: 填充字段数{filled_count}或核心字段未全部填充')
    l2_pass = False

# 步骤5: 清理测试数据
print('\n【步骤5】清理测试数据')
cmd = [LARK_CLI, 'base', '+record-delete',
       '--base-token', BASE_TOKEN, '--table-id', INSIGHT_TABLE,
       '--record-id', record_id, '--as', 'user', '--yes']
r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=True)
print(f'  删除测试记录: {record_id}')
print(f'  删除结果: {r.stdout[:100]}')

print('\n' + '=' * 60)
print(f'V7-01 复核完成: L2通过={l2_pass}')
print('=' * 60)
