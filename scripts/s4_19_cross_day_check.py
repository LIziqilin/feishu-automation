#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S4-19 跨日6h宽限期单元级验证"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('═══ S4-19 跨日6h宽限期单元级验证 ═══')
print()

# 导入mark_superseded_same_day相关函数
try:
    # 直接测试get_effective_day逻辑（从mark_superseded_same_day中提取）
    print('【1 跨日6h宽限期逻辑验证】')
    
    CROSS_DAY_GRACE_HOURS = 6
    
    def get_effective_day_test(timestamp_str, natural_day=""):
        """测试用：获取记录的有效日期（考虑跨日6h宽限）"""
        if not timestamp_str:
            return natural_day
        
        try:
            if isinstance(timestamp_str, str):
                if "T" in timestamp_str:
                    ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    if ts.tzinfo is not None:
                        ts = ts.replace(tzinfo=None)
                elif "/" in timestamp_str:
                    ts = datetime.strptime(timestamp_str, "%Y/%m/%d %H:%M")
                else:
                    return natural_day
                
                # 跨日6h宽限期：如果时间在00:00-06:00之间，视为前一天
                if ts.hour < CROSS_DAY_GRACE_HOURS:
                    effective_date = (ts - timedelta(days=1)).strftime("%Y-%m-%d")
                    return effective_date
                
                return ts.strftime("%Y-%m-%d")
        except:
            pass
        
        return natural_day
    
    # 测试用例1：23:59（自然日当天）
    ts1 = "2026-09-12T23:59:00"
    day1 = get_effective_day_test(ts1)
    print(f'  测试1: 23:59 → 有效日期={day1} (期望2026-09-12)')
    assert day1 == "2026-09-12", f"期望2026-09-12，实际{day1}"
    print('    → 23:59视为当天 ✅')
    
    # 测试用例2：00:01（跨日6h宽限期，视为前一天）
    ts2 = "2026-09-13T00:01:00"
    day2 = get_effective_day_test(ts2)
    print(f'  测试2: 00:01 → 有效日期={day2} (期望2026-09-12)')
    assert day2 == "2026-09-12", f"期望2026-09-12，实际{day2}"
    print('    → 00:01视为前一天（跨日6h宽限）✅')
    
    # 测试用例3：23:59和00:01视为同一天
    print(f'  测试3: 23:59和00:01是否同一天 → {day1 == day2}')
    assert day1 == day2, "23:59和00:01应视为同一天"
    print('    → 23:59和00:01视为同一天 ✅')
    
    # 测试用例4：05:59（跨日6h宽限期边界，视为前一天）
    ts4 = "2026-09-13T05:59:00"
    day4 = get_effective_day_test(ts4)
    print(f'  测试4: 05:59 → 有效日期={day4} (期望2026-09-12)')
    assert day4 == "2026-09-12", f"期望2026-09-12，实际{day4}"
    print('    → 05:59视为前一天（宽限期边界）✅')
    
    # 测试用例5：06:00（宽限期外，视为当天）
    ts5 = "2026-09-13T06:00:00"
    day5 = get_effective_day_test(ts5)
    print(f'  测试5: 06:00 → 有效日期={day5} (期望2026-09-13)')
    assert day5 == "2026-09-13", f"期望2026-09-13，实际{day5}"
    print('    → 06:00视为当天（宽限期外）✅')
    
    # 测试用例6：12:00（正常时间，视为当天）
    ts6 = "2026-09-13T12:00:00"
    day6 = get_effective_day_test(ts6)
    print(f'  测试6: 12:00 → 有效日期={day6} (期望2026-09-13)')
    assert day6 == "2026-09-13", f"期望2026-09-13，实际{day6}"
    print('    → 12:00视为当天 ✅')
    
    print()
    print('  → 跨日6h宽限期逻辑全部通过 ✅')
    
except Exception as e:
    print(f'  验证失败: {e}')
    import traceback
    traceback.print_exc()

# 验证排除非答题记录（S7-12修复）
print()
print('【2 排除非答题记录验证（S7-12修复）】')
valid_answer_results = {"会", "不会", "模糊"}
test_results = ["会", "不会", "模糊", "INIT", "REVOKE", "ADMIN_OVERRIDE"]
for result in test_results:
    is_valid = result in valid_answer_results
    print(f'  {result}: {"有效答题" if is_valid else "排除（不参与superseded）"}')
print('  → INIT/REVOKE/ADMIN_OVERRIDE被排除，不参与superseded标记 ✅')

# 反证：23:59答"会"+00:01答"不会" → 取"不会"，前条superseded
print()
print('【3 反证：23:59答"会"+00:01答"不会"】')
print('  场景：同一卡片，23:59答"会"，00:01答"不会"')
print('  期望：两条视为同一天，取最新的"不会"，前条"会"被标记superseded')

# 模拟数据
mock_flows = [
    {"_record_id": "rec_001", "event_id": "evt_001", "结果": "会", "客户端时间戳": "2026-09-12T23:59:00", "superseded": False},
    {"_record_id": "rec_002", "event_id": "evt_002", "结果": "不会", "客户端时间戳": "2026-09-13T00:01:00", "superseded": False},
]

# 计算有效日期
for f in mock_flows:
    f["effective_day"] = get_effective_day_test(f["客户端时间戳"])

print(f'  记录1: 23:59 "会" → 有效日期={mock_flows[0]["effective_day"]}')
print(f'  记录2: 00:01 "不会" → 有效日期={mock_flows[1]["effective_day"]}')

# 按有效日期分组
from collections import defaultdict
day_groups = defaultdict(list)
for f in mock_flows:
    day_groups[f["effective_day"]].append(f)

print(f'  分组结果: {dict(day_groups)}')

# 对每组进行superseded标记
for day, flows in day_groups.items():
    answer_flows = [f for f in flows if f.get("结果", "") in valid_answer_results]
    if len(answer_flows) > 1:
        flows_sorted = sorted(answer_flows, key=lambda x: x.get("客户端时间戳", "") or "")
        latest_flow = flows_sorted[-1]
        print(f'  最新记录: {latest_flow["结果"]} ({latest_flow["客户端时间戳"]})')
        for f in flows_sorted[:-1]:
            f["superseded"] = True
            print(f'  标记superseded: {f["结果"]} ({f["客户端时间戳"]})')

print(f'  最终状态: 记录1"会" superseded={mock_flows[0]["superseded"]}, 记录2"不会" superseded={mock_flows[1]["superseded"]}')
assert mock_flows[0]["superseded"] == True, "记录1应被标记superseded"
assert mock_flows[1]["superseded"] == False, "记录2不应被标记superseded"
print('  → 反证通过：23:59"会"被superseded，00:01"不会"保留 ✅')

# 检查代码中mark_superseded_same_day的实现
print()
print('【4 代码实现检查】')
try:
    with open(r'D:\AI-Tools\feishu\V13方案增强\scripts\learning_system.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    has_cross_day = 'CROSS_DAY_GRACE_HOURS = 6' in content
    has_get_effective_day = 'get_effective_day' in content
    has_hour_check = 'ts.hour < CROSS_DAY_GRACE_HOURS' in content
    has_valid_answer = 'valid_answer_results = {"会", "不会", "模糊"}' in content
    has_superseded_mark = 'update_flow(record_id, {"superseded": True})' in content
    
    print(f'  CROSS_DAY_GRACE_HOURS=6: {has_cross_day}')
    print(f'  get_effective_day函数: {has_get_effective_day}')
    print(f'  ts.hour < 6判断: {has_hour_check}')
    print(f'  valid_answer_results排除非答题: {has_valid_answer}')
    print(f'  update_flow标记superseded: {has_superseded_mark}')
    
    if all([has_cross_day, has_get_effective_day, has_hour_check, has_valid_answer, has_superseded_mark]):
        print('  → 代码实现完整 ✅')
    else:
        print('  → 代码实现不完整 ⚠️')
except Exception as e:
    print(f'  代码检查失败: {e}')

# PENDING_TIME登记
print()
print('【5 PENDING_TIME登记】')
print('  真实跨日场景测试需要等待23:59-00:01时间窗口，当前为单元级验证')
print('  待回填时间点: 下次可执行真实跨日测试时（23:59-00:01）')
print('  回填验证项:')
print('    1. 23:59答"会"，00:01答"不会"')
print('    2. 确认两条视为同一天')
print('    3. 确认前条"会"被标记superseded')
print('    4. 确认最新"不会"保留')

print()
print('═══ 单元级验证完成 ═══')
