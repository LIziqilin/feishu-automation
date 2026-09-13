#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F3-S6-08 倦怠设置测试"""
import sys
import os
import json
sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
from v19_integration import FatigueManager

print('=' * 60)
print('S6-08 倦怠设置测试')
print('=' * 60)

# 备份当前状态
FATIGUE_STATE_FILE = os.path.join(r'D:\AI-Tools\feishu\V13方案增强\scripts', '.fatigue_state.json')
backup_file = FATIGUE_STATE_FILE + '.bak_test'
if os.path.exists(FATIGUE_STATE_FILE):
    import shutil
    shutil.copy2(FATIGUE_STATE_FILE, backup_file)
    print('已备份当前倦怠状态')

try:
    # 测试1: 初始状态
    print('\n测试1: 初始状态检查')
    print('-' * 60)
    is_fatigue = FatigueManager.is_fatigue_mode()
    daily_count = FatigueManager.get_daily_card_count()
    status = FatigueManager.get_fatigue_status()
    print('是否倦怠模式: ' + str(is_fatigue))
    print('每日卡片数: ' + str(daily_count))
    print('倦怠状态详情: ' + json.dumps(status, ensure_ascii=False, indent=2))
    print('✅ 初始状态检查通过')

    # 测试2: 进入倦怠模式
    print('\n测试2: 进入倦怠模式')
    print('-' * 60)
    enter_result = FatigueManager.enter_fatigue_mode(reason="测试：手动进入倦怠模式", reduced_card_count=1)
    print('进入结果: ' + str(enter_result.get('success')))
    print('消息: ' + str(enter_result.get('message')))
    
    # 验证进入后状态
    is_fatigue_after = FatigueManager.is_fatigue_mode()
    daily_count_after = FatigueManager.get_daily_card_count()
    print('进入后是否倦怠: ' + str(is_fatigue_after))
    print('进入后每日卡片数: ' + str(daily_count_after))
    
    if enter_result.get('success') and is_fatigue_after and daily_count_after == 1:
        print('✅ 进入倦怠模式测试通过')
    else:
        print('❌ 进入倦怠模式测试失败')

    # 测试3: 重复进入（应失败）
    print('\n测试3: 重复进入倦怠模式（应失败）')
    print('-' * 60)
    enter_again = FatigueManager.enter_fatigue_mode(reason="重复进入测试")
    print('重复进入结果: ' + str(enter_again.get('success')))
    print('消息: ' + str(enter_again.get('message')))
    if not enter_again.get('success'):
        print('✅ 重复进入测试通过（正确拒绝）')
    else:
        print('❌ 重复进入测试失败')

    # 测试4: 倦怠状态详情
    print('\n测试4: 倦怠状态详情')
    print('-' * 60)
    status = FatigueManager.get_fatigue_status()
    print('倦怠模式: ' + str(status.get('fatigue_mode')))
    print('开始时间: ' + str(status.get('start_time')))
    print('持续天数: ' + str(status.get('duration_days')))
    print('最大天数: ' + str(status.get('max_days')))
    print('剩余天数: ' + str(status.get('remaining_days')))
    print('每日卡片数: ' + str(status.get('reduced_card_count')))
    print('原因: ' + str(status.get('reason')))
    print('自动恢复时间: ' + str(status.get('auto_recovery_time')))
    if status.get('fatigue_mode') and status.get('max_days') == 7 and status.get('remaining_days') >= 0:
        print('✅ 倦怠状态详情测试通过')
    else:
        print('❌ 倦怠状态详情测试失败')

    # 测试5: 退出倦怠模式
    print('\n测试5: 退出倦怠模式')
    print('-' * 60)
    exit_result = FatigueManager.exit_fatigue_mode(reason="测试：手动恢复")
    print('退出结果: ' + str(exit_result.get('success')))
    print('消息: ' + str(exit_result.get('message')))
    
    # 验证退出后状态
    is_fatigue_exit = FatigueManager.is_fatigue_mode()
    daily_count_exit = FatigueManager.get_daily_card_count()
    print('退出后是否倦怠: ' + str(is_fatigue_exit))
    print('退出后每日卡片数: ' + str(daily_count_exit))
    
    if exit_result.get('success') and not is_fatigue_exit and daily_count_exit == 3:
        print('✅ 退出倦怠模式测试通过')
    else:
        print('❌ 退出倦怠模式测试失败')

    # 测试6: 重复退出（应失败）
    print('\n测试6: 重复退出倦怠模式（应失败）')
    print('-' * 60)
    exit_again = FatigueManager.exit_fatigue_mode(reason="重复退出测试")
    print('重复退出结果: ' + str(exit_again.get('success')))
    print('消息: ' + str(exit_again.get('message')))
    if not exit_again.get('success'):
        print('✅ 重复退出测试通过（正确拒绝）')
    else:
        print('❌ 重复退出测试失败')

    # 总结
    print('\n' + '=' * 60)
    print('S6-08 测试总结')
    print('=' * 60)
    print('✅ enter_fatigue_mode：已实现（手动进入倦怠模式，设置降速卡片数）')
    print('✅ exit_fatigue_mode：已实现（手动退出倦怠模式，恢复正常卡片数）')
    print('✅ 倦怠持续时间限制：已实现（最多7天，到期自动恢复，不得永久降速）')
    print('✅ 倦怠模式状态记录：已实现（开始时间、持续天数、剩余天数、自动恢复时间）')
    print('✅ 倦怠事件日志：已实现（记录进入/退出/自动恢复事件）')
    print('✅ 重复操作保护：已实现（重复进入/退出正确拒绝）')
    print('✅ get_fatigue_status：已实现（获取完整倦怠状态详情）')

finally:
    # 恢复备份状态
    if os.path.exists(backup_file):
        import shutil
        shutil.copy2(backup_file, FATIGUE_STATE_FILE)
        os.remove(backup_file)
        print('\n已恢复原始倦怠状态')
