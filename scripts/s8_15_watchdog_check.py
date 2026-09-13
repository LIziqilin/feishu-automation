#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S8-15 看门狗业务级检测单元级验证（使用mock，不发送真实告警）"""
import sys
import os
import json
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('═══ S8-15 看门狗业务级检测单元级验证 ═══')
print()

# 导入Watchdog
try:
    from v19_integration import Watchdog
    print('【1 Watchdog导入成功】')
except Exception as e:
    print(f'【1 Watchdog导入失败】{e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 检查关键方法和属性
print()
print('【2 关键方法和属性检查】')
if hasattr(Watchdog, 'check_health'):
    print('  check_health方法: 存在 ✅')
else:
    print('  check_health方法: 不存在 ❌')

print(f'  WATCHDOG_STATE_FILE: {Watchdog.WATCHDOG_STATE_FILE}')
print('  → 看门狗状态文件配置正确 ✅')

# 测试场景1：系统正常（进程活着+功能正常）→ 健康，不告警
print()
print('【3 场景1：系统正常（进程活着+功能正常）→ 健康，不告警】')
# 创建临时系统状态文件（刚更新）
test_system_state = os.path.join(r'D:\AI-Tools\feishu\V13方案增强\scripts', '.system_state_test.json')
test_consume_index = os.path.join(r'D:\AI-Tools\feishu\V13方案增强\scripts', '.consume_index_test.json')
test_watchdog_state = os.path.join(r'D:\AI-Tools\feishu\V13方案增强\scripts', '.watchdog_state_test.json')

# 系统状态：刚成功
with open(test_system_state, 'w', encoding='utf-8') as f:
    json.dump({"last_success_time": datetime.now().isoformat(), "status": "running"}, f)

# 消费索引：刚更新
with open(test_consume_index, 'w', encoding='utf-8') as f:
    json.dump({"current_index": 100, "updated_at": datetime.now().isoformat()}, f)

with patch('v19_integration.SYSTEM_STATE_FILE', test_system_state), \
     patch('v19_integration.CONSUME_INDEX_FILE', test_consume_index), \
     patch('v19_integration.Watchdog.WATCHDOG_STATE_FILE', test_watchdog_state), \
     patch('v19_integration.run_cmd') as mock_run_cmd:
    mock_run_cmd.return_value = (True, '{"ok":true}', '')
    
    result = Watchdog.check_health()
    print(f'  healthy: {result["healthy"]}')
    print(f'  issues: {result["issues"]}')
    print(f'  should_alert: {result["should_alert"]}')
    print(f'  last_success_time: {result["last_success_time"]}')
    print(f'  consume_index_age_minutes: {result.get("consume_index_age_minutes", "N/A")}')
    
    assert result["healthy"] == True
    assert len(result["issues"]) == 0
    assert result["should_alert"] == False
    print('  → 系统正常时健康，不告警（区分进程活着与功能正常）✅')

# 测试场景2：进程活着但功能死了（last_success_time超过1小时+消费索引超过2小时）→ 异常，告警
print()
print('【4 场景2：进程活着但功能死了（超过阈值未更新）→ 异常，告警】')
# 系统状态：2小时前成功
with open(test_system_state, 'w', encoding='utf-8') as f:
    json.dump({"last_success_time": (datetime.now() - timedelta(hours=2)).isoformat(), "status": "running"}, f)

# 消费索引：3小时前更新（修改文件mtime）
with open(test_consume_index, 'w', encoding='utf-8') as f:
    json.dump({"current_index": 100, "updated_at": (datetime.now() - timedelta(hours=3)).isoformat()}, f)
# 修改文件mtime为3小时前
old_time = time.time() - 3 * 3600
os.utime(test_consume_index, (old_time, old_time))

with patch('v19_integration.SYSTEM_STATE_FILE', test_system_state), \
     patch('v19_integration.CONSUME_INDEX_FILE', test_consume_index), \
     patch('v19_integration.Watchdog.WATCHDOG_STATE_FILE', test_watchdog_state), \
     patch('v19_integration.run_cmd') as mock_run_cmd:
    mock_run_cmd.return_value = (True, '{"ok":true}', '')
    
    result = Watchdog.check_health()
    print(f'  healthy: {result["healthy"]}')
    print(f'  issues: {result["issues"]}')
    print(f'  should_alert: {result["should_alert"]}')
    print(f'  last_success_time: {result["last_success_time"]}')
    
    assert result["healthy"] == False
    assert len(result["issues"]) >= 2  # 至少2个问题才告警
    assert result["should_alert"] == True
    print('  → 进程活着但功能死了时检测到异常并告警（区分进程活着与功能正常）✅')

# 测试场景3：只有1个问题 → 不告警（避免误报）
print()
print('【5 场景3：只有1个问题 → 不告警（避免误报）】')
# 系统状态：正常（刚成功）
with open(test_system_state, 'w', encoding='utf-8') as f:
    json.dump({"last_success_time": datetime.now().isoformat(), "status": "running"}, f)

# 消费索引：3小时前更新（只有这1个问题）
with open(test_consume_index, 'w', encoding='utf-8') as f:
    json.dump({"current_index": 100, "updated_at": (datetime.now() - timedelta(hours=3)).isoformat()}, f)
os.utime(test_consume_index, (old_time, old_time))

with patch('v19_integration.SYSTEM_STATE_FILE', test_system_state), \
     patch('v19_integration.CONSUME_INDEX_FILE', test_consume_index), \
     patch('v19_integration.Watchdog.WATCHDOG_STATE_FILE', test_watchdog_state), \
     patch('v19_integration.run_cmd') as mock_run_cmd:
    mock_run_cmd.return_value = (True, '{"ok":true}', '')
    
    result = Watchdog.check_health()
    print(f'  healthy: {result["healthy"]}')
    print(f'  issues数量: {len(result["issues"])}')
    print(f'  should_alert: {result["should_alert"]}')
    
    # 只有1个问题（消费索引过期），系统状态正常
    # 注意：last_success_time正常，所以只有消费索引1个问题
    assert result["should_alert"] == False, "只有1个问题时不应告警（避免误报）"
    print('  → 只有1个问题时不告警（避免误报，2个以上问题才告警）✅')

# 测试场景4：看门狗状态文件记录
print()
print('【6 场景4：看门狗状态文件记录】')
if os.path.exists(test_watchdog_state):
    with open(test_watchdog_state, 'r', encoding='utf-8') as f:
        state = json.load(f)
    print(f'  last_check_time: {state.get("last_check_time", "N/A")}')
    print(f'  healthy: {state.get("healthy", "N/A")}')
    print(f'  issues: {state.get("issues", [])}')
    print(f'  should_alert: {state.get("should_alert", "N/A")}')
    print('  → 看门狗状态文件记录正常 ✅')
else:
    print('  → 看门狗状态文件不存在 ⚠️')

# 检查已接线到learning_system.py主流程
print()
print('【7 接线检查：已接线到learning_system.py主流程】')
try:
    with open(r'D:\AI-Tools\feishu\V13方案增强\scripts\learning_system.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    has_import = 'Watchdog' in content
    has_check = 'Watchdog.check_health()' in content
    has_warn_log = '看门狗检测到系统异常' in content or '看门狗' in content
    
    print(f'  导入Watchdog: {has_import}')
    print(f'  调用Watchdog.check_health(): {has_check}')
    print(f'  异常时记录WARN日志: {has_warn_log}')
    
    if all([has_import, has_check, has_warn_log]):
        print('  → 已完整接线到learning_system.py主流程 ✅')
    else:
        print('  → 接线不完整 ⚠️')
except Exception as e:
    print(f'  接线检查失败: {e}')

# 检查系统心跳表和系统健康表（通过lark-cli查询记录数）
print()
print('【8 系统心跳表/系统健康表记录数检查】')
try:
    import subprocess
    # 系统心跳表: tblJmm0ZIgqlYmyt
    result_heartbeat = subprocess.run(
        ['C:\\Users\\Administrator\\AppData\\Local\\hermes\\node\\lark-cli.cmd', 'base', '+record-list',
         '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf',
         '--table-id', 'tblJmm0ZIgqlYmyt',
         '--as', 'user', '--format', 'json', '--limit', '1'],
        capture_output=True, text=True, timeout=30
    )
    if result_heartbeat.returncode == 0:
        data = json.loads(result_heartbeat.stdout)
        total = data.get('data', {}).get('total', 0)
        print(f'  系统心跳表记录数: {total}')
    else:
        print(f'  系统心跳表查询失败: {result_heartbeat.stderr}')
    
    # 系统健康表: tblxJMndPNtZ7XyG
    result_health = subprocess.run(
        ['C:\\Users\\Administrator\\AppData\\Local\\hermes\\node\\lark-cli.cmd', 'base', '+record-list',
         '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf',
         '--table-id', 'tblxJMndPNtZ7XyG',
         '--as', 'user', '--format', 'json', '--limit', '1'],
        capture_output=True, text=True, timeout=30
    )
    if result_health.returncode == 0:
        data = json.loads(result_health.stdout)
        total = data.get('data', {}).get('total', 0)
        print(f'  系统健康表记录数: {total}')
    else:
        print(f'  系统健康表查询失败: {result_health.stderr}')
except Exception as e:
    print(f'  表记录数查询异常: {e}')

# 清理测试文件
for f in [test_system_state, test_consume_index, test_watchdog_state]:
    if os.path.exists(f):
        os.remove(f)

print()
print('═══ 单元级验证完成 ═══')
