#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5-1 修复验证：archive_insight真实写入测试"""
import sys
import json
import time
sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
from v19_integration import InsightArchiver

print('=== V5-1 修复验证：archive_insight真实写入测试 ===')
print()

# 测试洞察内容
test_text = '【V5-1修复测试】今天验证了飞书多维表格洞察归档功能，发现AI摘要生成和标签提取需要优化。系统优化的关键是建立完整的自动化工作流，需要进一步测试API集成的稳定性。'

print('【1 调用archive_insight写入测试洞察】')
result = InsightArchiver.archive_insight(
    insight_text=test_text,
    related_card_id='rec_test_v5_1',
    insight_type='系统优化'
)
print(f'  success: {result["success"]}')
print(f'  record_id: {result.get("record_id")}')
print(f'  error: {result.get("error")}')
print()

if result["success"] and result.get("record_id"):
    record_id = result["record_id"]
    print(f'【2 验证写入数据：读取record_id={record_id}】')
    
    # 使用lark-cli读取记录
    import subprocess
    cmd = ['lark-cli', 'base', '+record-get',
           '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf',
           '--table-id', 'tblaqKBl87V9C0q1',
           '--record-id', record_id,
           '--as', 'user', '--format', 'json']
    ok, stdout, stderr = False, '', ''
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=r'D:\AI-Tools\feishu\V13方案增强\scripts')
        ok = proc.returncode == 0
        stdout = proc.stdout
        stderr = proc.stderr
    except Exception as e:
        stderr = str(e)
    
    if ok:
        try:
            resp = json.loads(stdout)
            record = resp.get("data", {})
            fields = record.get("fields", {})
            print(f'  洞察标题: {fields.get("洞察标题", "")[:50]}...')
            print(f'  AI摘要: {str(fields.get("AI摘要", ""))[:80]}...')
            print(f'  标签: {fields.get("标签")}')
            print(f'  关联科目: {fields.get("关联科目")}')
            print(f'  洞察类型: {fields.get("洞察类型")}')
            print(f'  状态: {fields.get("状态")}')
            print(f'  沉淀状态: {fields.get("沉淀状态")}')
            print(f'  关联学习卡片: {fields.get("关联学习卡片")}')
            print(f'  行动项: {str(fields.get("行动项", ""))[:80]}...')
            print()
            
            # 验证三个核心字段
            print('【3 核心字段验证】')
            ai_summary = fields.get("AI摘要", "")
            tags = fields.get("标签", [])
            subject = fields.get("关联科目", "")
            
            if ai_summary and len(str(ai_summary)) > 10:
                print(f'  ✅ AI摘要已填充（长度={len(str(ai_summary))}）')
            else:
                print(f'  ❌ AI摘要未填充或过短')
            
            if tags and len(tags) > 0:
                print(f'  ✅ 标签已填充: {tags}')
            else:
                print(f'  ❌ 标签未填充')
            
            if subject:
                print(f'  ✅ 关联科目已填充: {subject}')
            else:
                print(f'  ❌ 关联科目未填充')
            print()
            
        except Exception as e:
            print(f'  解析返回失败: {e}')
            print(f'  原始返回: {stdout[:500]}')
    else:
        print(f'  读取记录失败: {stderr}')
    
    print(f'【4 清理测试数据：删除record_id={record_id}】')
    delete_cmd = ['lark-cli', 'base', '+record-delete',
                  '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf',
                  '--table-id', 'tblaqKBl87V9C0q1',
                  '--record-id', record_id,
                  '--as', 'user', '--yes']
    try:
        proc = subprocess.run(delete_cmd, capture_output=True, text=True, timeout=30, cwd=r'D:\AI-Tools\feishu\V13方案增强\scripts')
        if proc.returncode == 0:
            print(f'  ✅ 测试数据已删除')
        else:
            print(f'  ❌ 删除失败: {proc.stderr}')
    except Exception as e:
        print(f'  删除异常: {e}')
else:
    print('写入失败，跳过验证和清理')

print()
print('=== 测试完成 ===')
