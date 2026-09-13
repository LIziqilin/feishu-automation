#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S6-08 倦怠设置与恢复单元级验证（使用临时文件，不影响生产状态）"""
import sys
import os
import json
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('═══ S6-08 倦怠设置与恢复单元级验证 ═══')
print()

# 导入FatigueManager
try:
    from v19_integration import FatigueManager
    print('【1 FatigueManager导入成功】')
except Exception as e:
    print(f'【1 FatigueManager导入失败】{e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 检查关键方法和属性
print()
print('【2 关键方法和属性检查】')
methods = ['get_daily_card_count', 'is_fatigue_mode', 'enter_fatigue_mode', 'exit_fatigue_mode', 
           'get_fatigue_status', '_check_auto_recovery', '_load_state', '_save_state', '_log_fatigue_event']
for method in methods:
    if hasattr(FatigueManager, method):
        print(f'  {method}: 存在 ✅')
    else:
        print(f'  {method}: 不存在 ❌')

print(f'  MAX_FATIGUE_DAYS: {FatigueManager.MAX_FATIGUE_DAYS} (期望7)')
assert FatigueManager.MAX_FATIGUE_DAYS == 7
print(f'  DEFAULT_REDUCED_COUNT: {FatigueManager.DEFAULT_REDUCED_COUNT} (期望1)')
print('  → 7天自动恢复限制配置正确（不得永久降速）✅')

# 临时测试文件
test_state_file = os.path.join(r'D:\AI-Tools\feishu\V13方案增强\scripts', '.fatigue_state_test.json')
test_log_file = os.path.join(r'D:\AI-Tools\feishu\V13方案增强\scripts', '.fatigue_log_test.json')

# 清理测试文件
for f in [test_state_file, test_log_file]:
    if os.path.exists(f):
        os.remove(f)

# 测试场景1：手动进入倦怠模式 → 卡片数降速
print()
print('【3 场景1：手动进入倦怠模式 → 卡片数降速】')
with patch('v19_integration.FATIGUE_STATE_FILE', test_state_file), \
     patch('v19_integration.FatigueManager.FATIGUE_LOG_FILE', test_log_file):
    
    # 进入前：正常卡片数3
    count_before = FatigueManager.get_daily_card_count(default_count=3)
    print(f'  进入前卡片数: {count_before} (期望3)')
    assert count_before == 3
    
    # 进入倦怠模式
    result = FatigueManager.enter_fatigue_mode(reason="测试手动进入", reduced_card_count=1)
    print(f'  enter结果: success={result["success"]}, message={result["message"]}')
    assert result["success"] == True
    
    # 进入后：卡片数降为1
    count_after = FatigueManager.get_daily_card_count(default_count=3)
    print(f'  进入后卡片数: {count_after} (期望1)')
    assert count_after == 1
    
    # is_fatigue_mode返回True
    is_fatigue = FatigueManager.is_fatigue_mode()
    print(f'  is_fatigue_mode: {is_fatigue} (期望True)')
    assert is_fatigue == True
    
    print('  → 手动进入倦怠模式，卡片数降速（3→1）✅')

# 测试场景2：手动退出倦怠模式 → 卡片数恢复
print()
print('【4 场景2：手动退出倦怠模式 → 卡片数恢复】')
with patch('v19_integration.FATIGUE_STATE_FILE', test_state_file), \
     patch('v19_integration.FatigueManager.FATIGUE_LOG_FILE', test_log_file):
    
    # 退出倦怠模式
    result = FatigueManager.exit_fatigue_mode(reason="测试手动恢复")
    print(f'  exit结果: success={result["success"]}, message={result["message"]}')
    assert result["success"] == True
    
    # 退出后：卡片数恢复为3
    count_after = FatigueManager.get_daily_card_count(default_count=3)
    print(f'  退出后卡片数: {count_after} (期望3)')
    assert count_after == 3
    
    # is_fatigue_mode返回False
    is_fatigue = FatigueManager.is_fatigue_mode()
    print(f'  is_fatigue_mode: {is_fatigue} (期望False)')
    assert is_fatigue == False
    
    print('  → 手动退出倦怠模式，卡片数恢复（1→3）✅')

# 测试场景3：反证 - 7天自动恢复（不得永久降速）
print()
print('【5 场景3：反证 - 7天自动恢复（不得永久降速）】')
with patch('v19_integration.FATIGUE_STATE_FILE', test_state_file), \
     patch('v19_integration.FatigueManager.FATIGUE_LOG_FILE', test_log_file):
    
    # 先进入倦怠模式
    FatigueManager.enter_fatigue_mode(reason="测试自动恢复", reduced_card_count=1)
    
    # 手动修改start_time为8天前（模拟已持续8天，超过7天限制）
    with open(test_state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)
    state["start_time"] = (datetime.now() - timedelta(days=8)).isoformat()
    with open(test_state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    print(f'  模拟倦怠已持续8天（超过MAX_FATIGUE_DAYS=7）')
    
    # 调用get_daily_card_count，应触发自动恢复
    count = FatigueManager.get_daily_card_count(default_count=3)
    print(f'  自动恢复后卡片数: {count} (期望3，已自动恢复)')
    assert count == 3, f"超过7天应自动恢复，卡片数应为3，实际为{count}"
    
    # is_fatigue_mode应返回False
    is_fatigue = FatigueManager.is_fatigue_mode()
    print(f'  is_fatigue_mode: {is_fatigue} (期望False，已自动恢复)')
    assert is_fatigue == False
    
    # 检查状态文件中的恢复原因
    with open(test_state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)
    print(f'  recovery_reason: {state.get("recovery_reason", "N/A")}')
    assert "自动恢复" in state.get("recovery_reason", "")
    assert "7天" in state.get("recovery_reason", "")
    
    print('  → 7天自动恢复生效（不得永久降速）✅')

# 测试场景4：状态记录与事件日志
print()
print('【6 场景4：状态记录与事件日志】')
with patch('v19_integration.FATIGUE_STATE_FILE', test_state_file), \
     patch('v19_integration.FatigueManager.FATIGUE_LOG_FILE', test_log_file):
    
    # 清理后重新进入
    if os.path.exists(test_state_file):
        os.remove(test_state_file)
    if os.path.exists(test_log_file):
        os.remove(test_log_file)
    
    # 进入倦怠
    FatigueManager.enter_fatigue_mode(reason="测试日志记录", reduced_card_count=2)
    
    # 检查状态文件
    with open(test_state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)
    print(f'  状态文件: fatigue_mode={state["fatigue_mode"]}, start_time={state["start_time"][:19]}')
    print(f'  reduced_card_count={state["reduced_card_count"]}, reason={state["reason"]}')
    print(f'  auto_recovery_time={state["auto_recovery_time"][:19]}')
    assert state["fatigue_mode"] == True
    assert state["reduced_card_count"] == 2
    assert state["reason"] == "测试日志记录"
    
    # 检查事件日志
    with open(test_log_file, 'r', encoding='utf-8') as f:
        log = json.load(f)
    print(f'  事件日志条数: {len(log)}')
    print(f'  最新事件: type={log[-1]["event_type"]}, reason={log[-1]["reason"]}')
    assert len(log) >= 1
    assert log[-1]["event_type"] == "enter"
    
    # 退出倦怠
    FatigueManager.exit_fatigue_mode(reason="测试退出日志")
    
    # 再次检查事件日志
    with open(test_log_file, 'r', encoding='utf-8') as f:
        log = json.load(f)
    print(f'  退出后事件日志条数: {len(log)}')
    print(f'  最新事件: type={log[-1]["event_type"]}, reason={log[-1]["reason"]}')
    assert log[-1]["event_type"] == "exit"
    
    print('  → 状态记录与事件日志正常 ✅')

# 测试场景5：重复进入/退出的幂等性
print()
print('【7 场景5：重复进入/退出的幂等性】')
with patch('v19_integration.FATIGUE_STATE_FILE', test_state_file), \
     patch('v19_integration.FatigueManager.FATIGUE_LOG_FILE', test_log_file):
    
    # 清理
    if os.path.exists(test_state_file):
        os.remove(test_state_file)
    
    # 第一次进入：成功
    r1 = FatigueManager.enter_fatigue_mode(reason="第一次")
    print(f'  第一次进入: success={r1["success"]}')
    assert r1["success"] == True
    
    # 第二次进入：应失败（已处于倦怠模式）
    r2 = FatigueManager.enter_fatigue_mode(reason="第二次")
    print(f'  第二次进入: success={r2["success"]}, message={r2["message"]}')
    assert r2["success"] == False
    assert "已处于倦怠模式" in r2["message"]
    
    # 第一次退出：成功
    r3 = FatigueManager.exit_fatigue_mode(reason="第一次退出")
    print(f'  第一次退出: success={r3["success"]}')
    assert r3["success"] == True
    
    # 第二次退出：应失败（当前未处于倦怠模式）
    r4 = FatigueManager.exit_fatigue_mode(reason="第二次退出")
    print(f'  第二次退出: success={r4["success"]}, message={r4["message"]}')
    assert r4["success"] == False
    assert "当前未处于倦怠模式" in r4["message"]
    
    print('  → 重复进入/退出的幂等性正常 ✅')

# 清理测试文件
for f in [test_state_file, test_log_file]:
    if os.path.exists(f):
        os.remove(f)

print()
print('═══ 单元级验证完成 ═══')
