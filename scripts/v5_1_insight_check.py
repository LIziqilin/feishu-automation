#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5-1 S3-05 洞察结构化验证"""
import sys
sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
from v19_integration import InsightArchiver

print('=== V5-1 S3-05 洞察结构化验证 ===')
print()

# 测试1：正常洞察内容
print('【测试1：正常洞察内容】')
test_text = '今天学习了飞书多维表格的自动化工作流，发现可以通过条件触发自动发送消息提醒。需要进一步研究工作流的权限配置和错误处理机制，应该在下周完成一个完整的自动化案例。'
result = InsightArchiver.auto_structure_insight(test_text, related_card_id='rec_test_001')
print(f'  原始文本: {test_text[:50]}...')
print(f'  摘要: {result["summary"]}')
print(f'  关键词: {result["keywords"]}')
print(f'  行动项: {result["action_items"]}')
print(f'  关联卡片: {result["related_card_id"]}')
print(f'  字数: {result["word_count"]}')
print()

# 测试2：空内容
print('【测试2：空内容】')
empty_result = InsightArchiver.auto_structure_insight('')
print(f'  摘要: "{empty_result["summary"]}"')
print(f'  关键词: {empty_result["keywords"]}')
print(f'  行动项: {empty_result["action_items"]}')
print(f'  字数: {empty_result["word_count"]}')
print()

# 测试3：超长内容
print('【测试3：超长内容（500字）】')
long_text = '这是一个很长的洞察内容。' * 50
long_result = InsightArchiver.auto_structure_insight(long_text)
print(f'  原始长度: {len(long_text)}')
print(f'  摘要长度: {len(long_result["summary"])}')
print(f'  摘要前50字: {long_result["summary"][:50]}...')
print(f'  关键词数: {len(long_result["keywords"])}')
print()

# 测试4：archive_insight方法（检查是否真实写入）
print('【测试4：archive_insight方法检查】')
archive_result = InsightArchiver.archive_insight(test_text, related_card_id='rec_test_001')
print(f'  success: {archive_result["success"]}')
print(f'  archive_data字段: {list(archive_result.get("archive_data", {}).keys())}')
print(f'  错误: {archive_result.get("error")}')
print()

# 检查INSIGHT_TABLE配置
print('【配置检查】')
print(f'  INSIGHT_TABLE: {InsightArchiver.INSIGHT_TABLE}')
print(f'  是否为占位值: {InsightArchiver.INSIGHT_TABLE == "tblxxxxxxxxxx"}')
print()

print('=== 验证完成 ===')
