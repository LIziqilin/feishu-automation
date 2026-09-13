#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V6-1 S6-08 倦怠设置与恢复 端到端验证脚本"""
import sys, os, json, time
from datetime import datetime, timedelta
sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

from v19_integration import FatigueManager, FATIGUE_STATE_FILE

print('=' * 60)
print('V6-1 S6-08 倦怠设置与恢复 端到端验证')
print('=' * 60)

# 步骤0: 记录初始状态
print('\n【步骤0】记录初始状态')
initial_state = FatigueManager._load_state()
print(f'  初始倦怠状态: {json.dumps(initial_state, ensure_ascii=False)}')
print(f'  初始is_fatigue_mode: {FatigueManager.is_fatigue_mode()}')
print(f'  初始get_daily_card_count: {FatigueManager.get_daily_card_count(default_count=3)}')

# 步骤1: 触发进入倦怠模式
print('\n【步骤1】触发进入倦怠模式')
enter_result = FatigueManager.enter_fatigue_mode(
    reason="V6-1端到端验证-手动触发",
    reduced_card_count=1
)
print(f'  进入结果: {json.dumps(enter_result, ensure_ascii=False)}')

# 验证进入倦怠后的状态
is_fatigue = FatigueManager.is_fatigue_mode()
daily_count = FatigueManager.get_daily_card_count(default_count=3)
print(f'  进入后is_fatigue_mode: {is_fatigue}')
print(f'  进入后get_daily_card_count: {daily_count}（预期=1）')

if is_fatigue and daily_count == 1:
    print(f'  ✅ 通过: 进入倦怠模式成功，每日卡数从3降为1')
else:
    print(f'  ❌ 失败: 进入倦怠模式失败或卡数未降速')

# 步骤2: 反证 - 倦怠期内重复触发进入不应叠加降速
print('\n【步骤2】反证: 倦怠期内重复触发进入不应叠加降速')
enter_again = FatigueManager.enter_fatigue_mode(
    reason="重复触发测试",
    reduced_card_count=0  # 尝试降为0，应该被拒绝
)
print(f'  重复进入结果: {json.dumps(enter_again, ensure_ascii=False)}')
daily_count_after = FatigueManager.get_daily_card_count(default_count=3)
print(f'  重复进入后卡数: {daily_count_after}（预期仍=1，不应叠加为0）')

if not enter_again.get("success") and daily_count_after == 1:
    print(f'  ✅ 反证通过: 重复触发被拒绝，卡数未叠加降速')
else:
    print(f'  ❌ 反证失败: 重复触发成功或卡数被叠加降速')

# 步骤3: 验证状态记录与日志
print('\n【步骤3】验证状态记录与日志')
state = FatigueManager._load_state()
print(f'  状态文件内容: {json.dumps(state, ensure_ascii=False, indent=2)}')
print(f'  fatigue_mode: {state.get("fatigue_mode")}')
print(f'  start_time: {state.get("start_time")}')
print(f'  reduced_card_count: {state.get("reduced_card_count")}')
print(f'  reason: {state.get("reason")}')
print(f'  auto_recovery_time: {state.get("auto_recovery_time")}')

# 检查日志文件
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.fatigue_log.json')
if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8') as f:
        log = json.load(f)
    print(f'  日志文件存在，共{len(log)}条记录')
    print(f'  最近3条:')
    for entry in log[-3:]:
        print(f'    {entry.get("timestamp")} | {entry.get("event_type")} | {entry.get("reason")}')
else:
    print(f'  日志文件不存在: {log_file}')

# 步骤4: 手动恢复
print('\n【步骤4】手动恢复')
exit_result = FatigueManager.exit_fatigue_mode(reason="V6-1端到端验证-手动恢复")
print(f'  退出结果: {json.dumps(exit_result, ensure_ascii=False)}')
is_fatigue_after = FatigueManager.is_fatigue_mode()
daily_count_after = FatigueManager.get_daily_card_count(default_count=3)
print(f'  退出后is_fatigue_mode: {is_fatigue_after}')
print(f'  退出后get_daily_card_count: {daily_count_after}（预期=3）')

if not is_fatigue_after and daily_count_after == 3:
    print(f'  ✅ 通过: 手动恢复成功，卡数恢复为3')
else:
    print(f'  ❌ 失败: 手动恢复失败或卡数未恢复')

# 步骤5: ★自动恢复验证（模拟超过7天）
print('\n【步骤5】★自动恢复验证（模拟超过7天，不得永久降速）')
# 先进入倦怠
FatigueManager.enter_fatigue_mode(reason="自动恢复测试", reduced_card_count=1)
print(f'  已进入倦怠模式')

# 模拟修改start_time为8天前（超过MAX_FATIGUE_DAYS=7）
state = FatigueManager._load_state()
eight_days_ago = (datetime.now() - timedelta(days=8)).isoformat()
state["start_time"] = eight_days_ago
state["auto_recovery_time"] = (datetime.now() - timedelta(days=1)).isoformat()
with open(FATIGUE_STATE_FILE, 'w', encoding='utf-8') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
print(f'  已模拟start_time为8天前: {eight_days_ago}')

# 触发自动恢复检查
is_fatigue = FatigueManager.is_fatigue_mode()
daily_count = FatigueManager.get_daily_card_count(default_count=3)
print(f'  模拟8天后is_fatigue_mode: {is_fatigue}（预期=False，已自动恢复）')
print(f'  模拟8天后get_daily_card_count: {daily_count}（预期=3，已恢复正常）')

# 检查状态文件中的恢复原因
state_after = FatigueManager._load_state()
print(f'  恢复后状态: fatigue_mode={state_after.get("fatigue_mode")}')
print(f'  recovery_reason: {state_after.get("recovery_reason")}')

if not is_fatigue and daily_count == 3 and "自动恢复" in str(state_after.get("recovery_reason", "")):
    print(f'  ✅ 通过: 自动恢复成功，超过7天后自动恢复正常，不会永久降速')
else:
    print(f'  ❌ 失败: 自动恢复失败，可能永久降速')

# 步骤6: 清理测试数据
print('\n【步骤6】清理测试数据')
# 恢复初始状态
with open(FATIGUE_STATE_FILE, 'w', encoding='utf-8') as f:
    json.dump(initial_state, f, ensure_ascii=False, indent=2)
print(f'  已恢复初始倦怠状态')

# 清理日志中的测试记录
if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8') as f:
        log = json.load(f)
    original_count = len(log)
    cleaned_log = [entry for entry in log if 'V6-1' not in entry.get('reason', '') and '自动恢复测试' not in entry.get('reason', '')]
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_log, f, ensure_ascii=False, indent=2)
    print(f'  已清理倦怠日志: 删除{original_count - len(cleaned_log)}条测试记录，剩余{len(cleaned_log)}条')

print('\n' + '=' * 60)
print('V6-1 端到端验证完成')
print('=' * 60)
