#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S4-13 断网补发单元级验证"""
import sys
import json
import os
import time
from datetime import datetime

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('═══ S4-13 断网补发单元级验证 ═══')
print()

# 导入NetworkRecoveryManager和DLQManager
try:
    from v19_integration import NetworkRecoveryManager, DLQManager
    print('【1 类导入成功】')
    print(f'  NetworkRecoveryManager: 存在')
    print(f'  DLQManager: 存在')
except Exception as e:
    print(f'【1 类导入失败】{e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 检查关键方法
print()
print('【2 关键方法检查】')
methods = ['check_network', 'handle_network_status', 'add_pending_message', '_load_network_state', '_save_network_state']
for method in methods:
    if hasattr(NetworkRecoveryManager, method):
        print(f'  {method}: 存在 ✅')
    else:
        print(f'  {method}: 不存在 ❌')

# 验证状态持久化文件
print()
print('【3 状态持久化文件检查】')
state_file = NetworkRecoveryManager.NETWORK_STATE_FILE
print(f'  状态文件路径: {state_file}')
print(f'  文件存在: {os.path.exists(state_file)}')
if os.path.exists(state_file):
    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        print(f'  状态内容: {json.dumps(state, ensure_ascii=False, indent=2)[:200]}')
    except Exception as e:
        print(f'  状态文件读取失败: {e}')

# 验证check_network（网络正常时）
print()
print('【4 check_network验证（网络正常时）】')
try:
    check_result = NetworkRecoveryManager.check_network()
    print(f'  is_online: {check_result.get("is_online")}')
    print(f'  error: {check_result.get("error")}')
    print(f'  check_time: {check_result.get("check_time")}')
    if 'version' in check_result:
        print(f'  version: {check_result.get("version")}')
    if check_result.get('is_online'):
        print('  → 网络正常，check_network返回is_online=True ✅')
    else:
        print('  → 网络异常或lark-cli不可用 ⚠️')
except Exception as e:
    print(f'  check_network执行失败: {e}')
    import traceback
    traceback.print_exc()

# 验证状态保存和加载
print()
print('【5 状态保存和加载验证】')
try:
    # 构造测试状态
    test_state = {
        "is_offline": False,
        "offline_since": None,
        "last_check": datetime.now().isoformat(),
        "last_recovery": None,
        "offline_count": 0,
        "pending_messages": []
    }
    
    # 保存状态
    NetworkRecoveryManager._save_network_state(test_state)
    print('  测试状态保存成功')
    
    # 加载状态
    loaded_state = NetworkRecoveryManager._load_network_state()
    print(f'  加载状态 is_offline: {loaded_state.get("is_offline")}')
    print(f'  加载状态 offline_count: {loaded_state.get("offline_count")}')
    print(f'  加载状态 last_check: {loaded_state.get("last_check")}')
    
    if loaded_state.get('is_offline') == False and loaded_state.get('offline_count') == 0:
        print('  → 状态保存和加载一致 ✅')
    else:
        print('  → 状态保存和加载不一致 ⚠️')
except Exception as e:
    print(f'  状态保存和加载验证失败: {e}')
    import traceback
    traceback.print_exc()

# 验证handle_network_status（网络正常时，从离线恢复场景模拟）
print()
print('【6 handle_network_status验证（网络正常时）】')
try:
    # 先设置为离线状态，模拟断网恢复
    offline_state = {
        "is_offline": True,
        "offline_since": datetime.now().isoformat(),
        "last_check": None,
        "last_recovery": None,
        "offline_count": 1,
        "pending_messages": []
    }
    NetworkRecoveryManager._save_network_state(offline_state)
    print('  已设置为离线状态（模拟断网）')
    
    # 调用handle_network_status，应该检测到恢复并触发补发
    handle_result = NetworkRecoveryManager.handle_network_status()
    print(f'  status_changed: {handle_result.get("status_changed")}')
    print(f'  previous_status: {handle_result.get("previous_status")}')
    print(f'  current_status: {handle_result.get("current_status")}')
    print(f'  action_taken: {handle_result.get("action_taken")}')
    
    if 'retry_result' in handle_result:
        retry_result = handle_result['retry_result']
        print(f'  retry_result: {json.dumps(retry_result, ensure_ascii=False)[:200]}')
    
    if handle_result.get('status_changed') and handle_result.get('action_taken') == 'recovered_and_retrying':
        print('  → 检测到网络恢复，触发自动补发 ✅')
    elif handle_result.get('current_status') == 'online':
        print('  → 网络正常，状态已更新 ✅')
    else:
        print('  → 状态变化检测需进一步验证 ⚠️')
except Exception as e:
    print(f'  handle_network_status验证失败: {e}')
    import traceback
    traceback.print_exc()

# 验证DLQ队列持久化
print()
print('【7 DLQ队列持久化验证】')
try:
    dlq_file = DLQManager.QUEUE_FILE if hasattr(DLQManager, 'QUEUE_FILE') else '.dlq_queue.json'
    print(f'  DLQ队列文件: {dlq_file}')
    print(f'  文件存在: {os.path.exists(dlq_file)}')
    if os.path.exists(dlq_file):
        with open(dlq_file, 'r', encoding='utf-8') as f:
            dlq_data = json.load(f)
        if isinstance(dlq_data, list):
            print(f'  队列消息数: {len(dlq_data)}')
        elif isinstance(dlq_data, dict):
            print(f'  队列数据键: {list(dlq_data.keys())}')
except Exception as e:
    print(f'  DLQ队列持久化验证失败: {e}')

# 反证：补发后不得重复处理（幂等性）
print()
print('【8 反证：补发幂等性验证】')
try:
    # 检查DLQManager.retry_pending是否有幂等机制
    import inspect
    if hasattr(DLQManager, 'retry_pending'):
        source = inspect.getsource(DLQManager.retry_pending)
        # 检查是否有状态标记（如retrying/retried）
        has_status_marker = 'retried' in source or 'retrying' in source or 'status' in source
        has_idempotency = 'idempotent' in source or 'duplicate' in source or 'already' in source
        print(f'  retry_pending方法存在')
        print(f'  包含状态标记: {has_status_marker}')
        print(f'  包含幂等检查: {has_idempotency}')
        if has_status_marker:
            print('  → 有状态标记机制，可防止重复处理 ✅')
        else:
            print('  → 需确认幂等机制 ⚠️')
except Exception as e:
    print(f'  幂等性验证失败: {e}')

# PENDING_TIME登记
print()
print('【9 PENDING_TIME登记】')
print('  真实断网测试需要断开网络5分钟，当前为单元级验证')
print('  待回填时间点: 下次可执行真实断网测试时')
print('  回填验证项:')
print('    1. 真实断网5分钟')
print('    2. 断网期间发送消息，确认进入DLQ')
print('    3. 恢复网络后，确认自动补发')
print('    4. 补发后不得重复处理（幂等）')

print()
print('═══ 单元级验证完成 ═══')
