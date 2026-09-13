#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5-1 修复验证：InsightArchiver结构化处理"""
import sys
sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
from v19_integration import InsightArchiver

print('=== V5-1 修复验证：InsightArchiver结构化处理 ===')
print()

# 测试1：AI技术相关洞察
print('【测试1：AI技术相关洞察】')
text1 = '今天研究了飞书多维表格的自动化工作流，发现可以通过条件触发自动发送消息提醒。AI技术在办公自动化中的应用越来越广泛，需要进一步学习大模型API的集成方法。'
result1 = InsightArchiver.auto_structure_insight(text1, related_card_id='rec_test_001')
print(f'  AI摘要: {result1["summary"][:80]}...')
print(f'  标签: {result1["keywords"]}')
print(f'  关联科目: {result1["subject"]}')
print(f'  行动项: {result1["action_items"]}')
print()

# 测试2：机电工程相关洞察
print('【测试2：机电工程相关洞察】')
text2 = '酒店空调系统维保中发现，冷却水塔的清洗周期应该从半年缩短到三个月，可以有效降低能耗。机电工程的预防性维护比故障维修成本低60%，必须建立完善的维保SOP。'
result2 = InsightArchiver.auto_structure_insight(text2)
print(f'  AI摘要: {result2["summary"][:80]}...')
print(f'  标签: {result2["keywords"]}')
print(f'  关联科目: {result2["subject"]}')
print(f'  行动项: {result2["action_items"]}')
print()

# 测试3：管理学相关洞察
print('【测试3：管理学相关洞察】')
text3 = '团队管理中发现，定期一对一沟通比季度绩效评估更能及时发现问题。管理者应该学会倾听，建立信任关系，决策时需要充分考虑团队成员的意见。'
result3 = InsightArchiver.auto_structure_insight(text3)
print(f'  AI摘要: {result3["summary"][:80]}...')
print(f'  标签: {result3["keywords"]}')
print(f'  关联科目: {result3["subject"]}')
print()

# 测试4：空内容
print('【测试4：空内容】')
result4 = InsightArchiver.auto_structure_insight('')
print(f'  AI摘要: "{result4["summary"]}"')
print(f'  标签: {result4["keywords"]}')
print(f'  关联科目: {result4["subject"]}')
print()

# 测试5：配置检查
print('【配置检查】')
print(f'  INSIGHT_TABLE: {InsightArchiver.INSIGHT_TABLE}')
print(f'  标签选项数: {len(InsightArchiver.TAG_OPTIONS)}')
print(f'  关联科目选项: {InsightArchiver.SUBJECT_OPTIONS}')
print()

print('=== 验证完成 ===')
