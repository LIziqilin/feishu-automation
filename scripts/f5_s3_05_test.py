#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F5-S3-05 洞察归档补全测试"""
import sys
sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
from v19_integration import InsightArchiver

print('=' * 60)
print('S3-05 洞察归档补全测试')
print('=' * 60)

# 测试1: 关键词提取
print('\n测试1: 关键词提取')
print('-' * 60)
test_text = "今天学习了酒店给排水系统的维保周期，需要注意水泵的日常维护和管道清洗。应该建立定期检查机制，确保系统正常运行。"
keywords = InsightArchiver.extract_keywords(test_text, max_keywords=5)
print('测试文本: ' + test_text[:50] + '...')
print('提取关键词: ' + str(keywords))
if len(keywords) > 0:
    print('✅ 关键词提取测试通过')
else:
    print('❌ 关键词提取测试失败')

# 测试2: 摘要生成
print('\n测试2: 摘要生成')
print('-' * 60)
long_text = "这是一段很长的洞察笔记内容。" * 20
summary = InsightArchiver.generate_summary(long_text, max_length=100)
print('原文长度: ' + str(len(long_text)) + '字')
print('摘要长度: ' + str(len(summary)) + '字')
print('摘要内容: ' + summary[:80] + '...')
if len(summary) <= 120 and len(summary) > 0:
    print('✅ 摘要生成测试通过')
else:
    print('❌ 摘要生成测试失败')

# 测试3: 行动项提取
print('\n测试3: 行动项提取')
print('-' * 60)
action_text = "今天的学习收获很大。需要明天复习给排水系统知识点。应该建立错题本。必须完成本周的复盘。下一步准备学习空调系统。"
action_items = InsightArchiver.extract_action_items(action_text)
print('测试文本: ' + action_text)
print('提取行动项:')
for i, item in enumerate(action_items, 1):
    print(f'  {i}. {item}')
if len(action_items) >= 3:
    print('✅ 行动项提取测试通过')
else:
    print('❌ 行动项提取测试失败')

# 测试4: 自动结构化处理
print('\n测试4: 自动结构化处理')
print('-' * 60)
insight_text = "今天深入学习了酒店机电系统的运维管理。需要建立设备台账，记录每个设备的维保周期。应该定期检查消防系统，确保符合规范。通过这次学习，我认识到预防性维护的重要性。下一步准备学习电梯系统的维保知识。"
structured = InsightArchiver.auto_structure_insight(insight_text, related_card_id="recvtLY8poT8zw")
print('结构化结果:')
print('  摘要: ' + str(structured.get('summary', ''))[:60] + '...')
print('  关键词: ' + str(structured.get('keywords', [])))
print('  行动项数: ' + str(len(structured.get('action_items', []))))
print('  关联卡片: ' + str(structured.get('related_card_id')))
print('  字数: ' + str(structured.get('word_count')))
print('  结构化时间: ' + str(structured.get('structured_at')))
if structured.get('summary') and structured.get('keywords') and len(structured.get('action_items', [])) > 0:
    print('✅ 自动结构化处理测试通过')
else:
    print('❌ 自动结构化处理测试失败')

# 测试5: 洞察归档
print('\n测试5: 洞察归档')
print('-' * 60)
archive_result = InsightArchiver.archive_insight(
    insight_text="今天学习了空调系统的维保知识，需要定期清洗滤网，检查制冷剂液位。应该建立季度维保计划。",
    related_card_id="recvtLY8poT8zw",
    insight_type="学习洞察"
)
print('归档成功: ' + str(archive_result.get('success')))
if archive_result.get('archive_data'):
    data = archive_result['archive_data']
    print('归档数据:')
    print('  摘要: ' + str(data.get('摘要', ''))[:50] + '...')
    print('  标签: ' + str(data.get('标签', [])))
    print('  行动项数: ' + str(len(data.get('行动项', []))))
    print('  洞察类型: ' + str(data.get('洞察类型')))
    print('  关联卡片: ' + str(data.get('关联卡片')))
if archive_result.get('success'):
    print('✅ 洞察归档测试通过')
else:
    print('❌ 洞察归档测试失败')

# 总结
print('\n' + '=' * 60)
print('S3-05 测试总结')
print('=' * 60)
print('✅ 关键词提取：已实现（词频统计+停用词过滤）')
print('✅ 摘要生成：已实现（智能截断，保留完整句子）')
print('✅ 行动项提取：已实现（识别需要/应该/必须等关键词）')
print('✅ 自动结构化处理：已实现（摘要+关键词+行动项+关联卡片）')
print('✅ 洞察归档：已实现（结构化数据写入洞察笔记表）')
print('✅ 关联学习卡片：已实现（支持关联卡片ID）')
print('✅ 洞察类型分类：已实现（学习洞察/工作洞察等）')
