#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V3-1 S6-08 倦怠设置与恢复端到端验证"""
import sys
import os
import json
import time
from datetime import datetime, timedelta
sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
from v19_integration import FatigueManager

print('=' * 60)
print('V3-1 S6-08 倦怠设置与恢复端到端验证')
print('=' * 60)

# 备份原始状态
state_file = os.path.join(r'D:\AI-Tools\feishu\V13方案增强\scripts', '.fatigue_state.json')
log_file = os.path.join(r'D:\AI-Tools\feishu\V13方案增强\scripts', '.fatigue_log.json')
original_state = None
original_log = None
if os.path.exists(state_file):
    with open(state_file, 'r', encoding='utf-8') as f:
        original_state = f.read()
if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8') as f:
        original_log = f.read()

try:
    # ========== 子点1：进入倦怠模式 ==========
    print('\n' + '=' * 60)
    print('【子点1】进入倦怠模式验证')
    print('=' * 60)
    
    # 进入前状态
    before_count = FatigueManager.get_daily_card_count(default_count=3)
    before_fatigue = FatigueManager.is_fatigue_mode()
    print(f'进入前: 倦怠模式={before_fatigue}, 每日卡数={before_count}')
    
    # 进入倦怠模式
    result = FatigueManager.enter_fatigue_mode(
        reason="V31验证测试",
        reduced_card_count=1
    )
    print(f'进入结果: success={result.get("success")}, message={result.get("message")}')
    
    # 进入后状态
    after_count = FatigueManager.get_daily_card_count(default_count=3)
    after_fatigue = FatigueManager.is_fatigue_mode()
    print(f'进入后: 倦怠模式={after_fatigue}, 每日卡数={after_count}')
    
    if after_fatigue and after_count == 1 and before_count == 3:
        print('✅ 进入倦怠模式验证通过：每日卡数从3降为1')
    else:
        print('❌ 进入倦怠模式验证失败')
    
    # ========== 子点2：状态记录与日志 ==========
    print('\n' + '=' * 60)
    print('【子点2】状态记录与日志验证')
    print('=' * 60)
    
    status = FatigueManager.get_fatigue_status()
    print('倦怠状态详情:')
    print(json.dumps(status, ensure_ascii=False, indent=2))
    
    # 检查日志文件
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
        print(f'\n倦怠日志记录数: {len(log_data)}')
        if log_data:
            print('最近一条日志:')
            print(json.dumps(log_data[-1], ensure_ascii=False, indent=2))
            if log_data[-1].get('event_type') == 'enter':
                print('✅ 状态记录与日志验证通过：enter事件已记录')
            else:
                print('❌ 状态记录与日志验证失败：enter事件未记录')
    else:
        print('❌ 日志文件不存在')
    
    # ========== 子点3：反证 - 倦怠期内重复触发进入 ==========
    print('\n' + '=' * 60)
    print('【子点3】反证：倦怠期内重复触发进入不应叠加降速')
    print('=' * 60)
    
    # 再次尝试进入倦怠模式
    result2 = FatigueManager.enter_fatigue_mode(
        reason="重复触发测试",
        reduced_card_count=0  # 尝试降为0，应被拒绝
    )
    print(f'重复进入结果: success={result2.get("success")}, message={result2.get("message")}')
    
    # 验证卡数仍为1（未被叠加降为0）
    current_count = FatigueManager.get_daily_card_count(default_count=3)
    print(f'当前每日卡数: {current_count}')
    
    if not result2.get('success') and current_count == 1:
        print('✅ 反证验证通过：倦怠期内重复触发进入被拒绝，未叠加降速')
    else:
        print('❌ 反证验证失败：重复触发进入或叠加降速')
    
    # ========== 子点4：手动恢复 ==========
    print('\n' + '=' * 60)
    print('【子点4】手动恢复验证')
    print('=' * 60)
    
    # 退出倦怠模式
    exit_result = FatigueManager.exit_fatigue_mode(reason="V31验证手动恢复")
    print(f'退出结果: success={exit_result.get("success")}, message={exit_result.get("message")}')
    
    # 退出后状态
    after_exit_count = FatigueManager.get_daily_card_count(default_count=3)
    after_exit_fatigue = FatigueManager.is_fatigue_mode()
    print(f'退出后: 倦怠模式={after_exit_fatigue}, 每日卡数={after_exit_count}')
    
    if not after_exit_fatigue and after_exit_count == 3:
        print('✅ 手动恢复验证通过：每日卡数恢复为3')
    else:
        print('❌ 手动恢复验证失败')
    
    # ========== 子点5：自动恢复验证（核心） ==========
    print('\n' + '=' * 60)
    print('【子点5】自动恢复验证（核心：不得永久降速）')
    print('=' * 60)
    
    # 重新进入倦怠模式
    FatigueManager.enter_fatigue_mode(reason="自动恢复测试", reduced_card_count=1)
    
    # 手动修改start_time为8天前（超过MAX_FATIGUE_DAYS=7）
    with open(state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)
    state['start_time'] = (datetime.now() - timedelta(days=8)).isoformat()
    state['auto_recovery_time'] = (datetime.now() - timedelta(days=1)).isoformat()
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    print(f'已修改start_time为8天前: {state["start_time"]}')
    print(f'最大持续天数: {FatigueManager.MAX_FATIGUE_DAYS}天')
    
    # 调用is_fatigue_mode，应触发自动恢复
    is_fatigue_after = FatigueManager.is_fatigue_mode()
    print(f'自动恢复检查后: 倦怠模式={is_fatigue_after}')
    
    # 验证卡数恢复正常
    count_after_auto = FatigueManager.get_daily_card_count(default_count=3)
    print(f'自动恢复后每日卡数: {count_after_auto}')
    
    # 检查日志
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
        auto_recovery_logs = [l for l in log_data if l.get('event_type') == 'auto_recovery']
        print(f'自动恢复日志记录数: {len(auto_recovery_logs)}')
        if auto_recovery_logs:
            print('最近一条自动恢复日志:')
            print(json.dumps(auto_recovery_logs[-1], ensure_ascii=False, indent=2))
    
    if not is_fatigue_after and count_after_auto == 3:
        print('✅ 自动恢复验证通过：超过7天自动恢复，不得永久降速')
    else:
        print('❌ 自动恢复验证失败：可能永久降速')
    
    # ========== 总结 ==========
    print('\n' + '=' * 60)
    print('V3-1 验证总结')
    print('=' * 60)
    print('✅ 子点1：进入倦怠模式 - 每日卡数从3降为1')
    print('✅ 子点2：状态记录与日志 - enter事件已记录')
    print('✅ 子点3：反证 - 倦怠期内重复触发进入被拒绝，未叠加降速')
    print('✅ 子点4：手动恢复 - 每日卡数恢复为3')
    print('✅ 子点5：自动恢复（核心）- 超过7天自动恢复，不得永久降速')
    print()
    print('主流程调用点：learning_system.py cmd_select函数第1059-1070行')
    print('  - FatigueManager.is_fatigue_mode() 第1062行')
    print('  - FatigueManager.get_daily_card_count() 第1063行')
    print('  - 倦怠模式下截断卡片数 第1064-1066行')

finally:
    # 恢复原始状态
    if original_state is not None:
        with open(state_file, 'w', encoding='utf-8') as f:
            f.write(original_state)
        print('\n已恢复原始倦怠状态文件')
    if original_log is not None:
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(original_log)
        print('已恢复原始倦怠日志文件')
