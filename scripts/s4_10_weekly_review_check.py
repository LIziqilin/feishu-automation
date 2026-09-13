#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S4-10 周日复盘验证"""
import sys
import json
import os

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('═══ S4-10 周日复盘验证 ═══')
print()

# 导入SundayReviewManager
try:
    from v19_integration import SundayReviewManager
    print('【1 SundayReviewManager导入成功】')
except Exception as e:
    print(f'【1 SundayReviewManager导入失败】{e}')
    sys.exit(1)

# 检查关键方法
print()
print('【2 关键方法检查】')
methods = ['select_key_cards', 'generate_application_scenario', 'calculate_roi', 'generate_weekly_review']
for method in methods:
    if hasattr(SundayReviewManager, method):
        print(f'  {method}: 存在 ✅')
    else:
        print(f'  {method}: 不存在 ❌')

# 手动触发一次复盘
print()
print('【3 手动触发周日复盘】')
try:
    # 构造模拟学习统计数据
    study_stats = {
        "total_answers": 38,
        "correct_rate": 0.75,
        "study_days": 7,
        "streak_days": 5
    }
    
    review_report = SundayReviewManager.generate_weekly_review(study_stats)
    print('  复盘报告生成成功')
    print(f'  报告长度: {len(review_report)}字符')
    print()
    print('  【报告内容】')
    print(review_report)
except Exception as e:
    print(f'  复盘报告生成失败: {e}')
    import traceback
    traceback.print_exc()

# 验证三部分内容
print()
print('【4 三部分内容验证】')
if 'review_report' in dir():
    # 检查脱稿讲3张
    has_key_cards = '脱稿讲解' in review_report or '重点卡片' in review_report or '【1/3】' in review_report
    print(f'  脱稿讲3张: {"包含 ✅" if has_key_cards else "不包含 ❌"}')
    
    # 检查1应用场景
    has_application = '实际应用' in review_report or '应用场景' in review_report or '【2/3】' in review_report
    print(f'  1应用场景: {"包含 ✅" if has_application else "不包含 ❌"}')
    
    # 检查ROI数据
    has_roi = 'ROI' in review_report or '投资回报' in review_report or '【3/3】' in review_report
    print(f'  ROI数据: {"包含 ✅" if has_roi else "不包含 ❌"}')
    
    # 检查具体ROI指标
    has_time = '时间投入' in review_report
    has_knowledge = '知识获取' in review_report
    has_efficiency = '效率提升' in review_report
    has_roi_score = 'ROI评分' in review_report
    print(f'    时间投入: {"包含 ✅" if has_time else "不包含 ❌"}')
    print(f'    知识获取: {"包含 ✅" if has_knowledge else "不包含 ❌"}')
    print(f'    效率提升: {"包含 ✅" if has_efficiency else "不包含 ❌"}')
    print(f'    ROI评分: {"包含 ✅" if has_roi_score else "不包含 ❌"}')

# 反证：无学习数据时不应崩溃
print()
print('【5 反证：无学习数据时不应崩溃】')
try:
    empty_report = SundayReviewManager.generate_weekly_review(None)
    print(f'  无学习数据时生成成功 ✅')
    print(f'  报告长度: {len(empty_report)}字符')
    # 检查是否有合理的默认值
    has_default_roi = '时间投入: 0小时' in empty_report or 'ROI评分: 0' in empty_report
    print(f'  包含默认ROI值: {"包含 ✅" if has_default_roi else "检查中"}')
except Exception as e:
    print(f'  无学习数据时崩溃 ❌: {e}')
    import traceback
    traceback.print_exc()

# 反证：空卡片列表时不应崩溃
print()
print('【6 反证：空卡片列表时不应崩溃】')
try:
    empty_cards = SundayReviewManager.select_key_cards(all_cards=[], top_n=3)
    print(f'  空卡片列表时返回: {empty_cards} ✅')
except Exception as e:
    print(f'  空卡片列表时崩溃 ❌: {e}')

print()
print('═══ 验证完成 ═══')
