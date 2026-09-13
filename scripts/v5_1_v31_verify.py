#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5-1 V31独立验证：端到端测试洞察结构化"""
import sys
import json
import subprocess
import os

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')
from v19_integration import InsightArchiver

print('═══ V5-1 V31独立验证：端到端测试 ═══')
print()

# 测试洞察内容
test_text = '【V5-1验证测试】今天学习了飞书多维表格的自动化工作流配置，发现条件触发可以大幅提升办公效率。AI技术在知识管理中的应用需要进一步探索，应该建立完整的洞察归档SOP，必须测试API集成的稳定性。'

print('【1 真实触发：调用archive_insight写入测试洞察】')
result = InsightArchiver.archive_insight(
    insight_text=test_text,
    related_card_id='rec_v51_test_001',
    insight_type='系统优化'
)
print(f'  success: {result["success"]}')
print(f'  record_id: {result.get("record_id")}')
print(f'  error: {result.get("error")}')
print()

record_id = result.get("record_id")
if not result["success"] or not record_id:
    print('❌ 写入失败，终止验证')
    sys.exit(1)

print('【2 数据落点：读取写入记录，检查实际填充字段】')
# 使用lark-cli读取记录
cmd = ['lark-cli', 'base', '+record-get',
       '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf',
       '--table-id', 'tblaqKBl87V9C0q1',
       '--record-id', record_id,
       '--as', 'user', '--format', 'json']
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
print(f'  退出码: {proc.returncode}')

if proc.returncode != 0:
    print(f'  读取失败: {proc.stderr}')
    sys.exit(1)

resp = json.loads(proc.stdout)
record_data = resp.get("data", {})

# record-get返回格式：data.fields是字段名列表，data.data是值数组
fields = record_data.get("fields", [])
values = record_data.get("data", [[]])[0] if record_data.get("data") else []

print(f'  字段总数: {len(fields)}')
print()

# 统计填充字段数
filled_fields = []
empty_fields = []
for i, field in enumerate(fields):
    val = values[i] if i < len(values) else None
    if val is not None and val != "" and val != [] and val != False:
        filled_fields.append((field, val))
    else:
        empty_fields.append(field)

print(f'  已填充字段数: {len(filled_fields)}')
print(f'  空字段数: {len(empty_fields)}')
print()

print('  【已填充字段详情】')
for field, val in filled_fields:
    val_str = str(val)
    if len(val_str) > 80:
        val_str = val_str[:80] + '...'
    print(f'    {field}: {val_str}')
print()

# 核心字段验证
print('  【三个核心字段验证】')
core_fields = ['标签', '关联科目', 'AI摘要']
core_results = {}
for cf in core_fields:
    if cf in fields:
        idx = fields.index(cf)
        val = values[idx] if idx < len(values) else None
        core_results[cf] = val
        if val and val != [] and val != "":
            print(f'    ✅ {cf}: {val}')
        else:
            print(f'    ❌ {cf}: 空')
    else:
        print(f'    ❌ {cf}: 字段不存在')
print()

print('【3 用户可感知：结构化处理输出】')
structured = result.get("structured", {})
print(f'  AI摘要: {structured.get("summary", "")[:80]}...')
print(f'  标签: {structured.get("keywords")}')
print(f'  关联科目: {structured.get("subject")}')
print(f'  行动项数: {len(structured.get("action_items", []))}')
print()

print('【4 反向验证：空内容和超长内容处理】')
# 空内容
empty_result = InsightArchiver.auto_structure_insight('')
print(f'  空内容-摘要: "{empty_result["summary"]}"')
print(f'  空内容-标签: {empty_result["keywords"]}')
print(f'  空内容-科目: {empty_result["subject"]}')
print(f'  空内容-是否崩溃: 否')

# 超长内容（1000字）
long_text = '这是一个超长的洞察内容测试。' * 100
long_result = InsightArchiver.auto_structure_insight(long_text)
print(f'  超长内容-字数: {long_result["word_count"]}')
print(f'  超长内容-摘要长度: {len(long_result["summary"])}')
print(f'  超长内容-标签数: {len(long_result["keywords"])}')
print(f'  超长内容-是否崩溃: 否')
print()

print('【5 清理测试数据】')
delete_cmd = ['lark-cli', 'base', '+record-delete',
              '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf',
              '--table-id', 'tblaqKBl87V9C0q1',
              '--record-id', record_id,
              '--as', 'user', '--yes']
del_proc = subprocess.run(delete_cmd, capture_output=True, text=True, timeout=30)
print(f'  删除退出码: {del_proc.returncode}')
if del_proc.returncode == 0:
    print(f'  ✅ 测试数据已清理')
else:
    print(f'  ❌ 清理失败: {del_proc.stderr}')
print()

print('═══ 验证数据汇总 ═══')
print(f'  表总字段数: {len(fields)}')
print(f'  实际填充字段数: {len(filled_fields)}')
print(f'  空字段数: {len(empty_fields)}')
print(f'  填充率: {len(filled_fields)/len(fields)*100:.1f}%')
print(f'  核心字段-标签: {"✅" if core_results.get("标签") else "❌"}')
print(f'  核心字段-关联科目: {"✅" if core_results.get("关联科目") else "❌"}')
print(f'  核心字段-AI摘要: {"✅" if core_results.get("AI摘要") else "❌"}')
print()
