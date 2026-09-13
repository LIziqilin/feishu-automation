#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S8-06 消费索引健康检查单元级验证（使用mock，不发送真实请求）"""
import sys
import os
import json
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('═══ S8-06 消费索引健康检查单元级验证 ═══')
print()

# 导入ConsumeIndexHealthChecker
try:
    from v19_integration import ConsumeIndexHealthChecker
    print('【1 ConsumeIndexHealthChecker导入成功】')
except Exception as e:
    print(f'【1 ConsumeIndexHealthChecker导入失败】{e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 检查关键方法和属性
print()
print('【2 关键方法和属性检查】')
if hasattr(ConsumeIndexHealthChecker, 'check'):
    print('  check方法: 存在 ✅')
else:
    print('  check方法: 不存在 ❌')

# 检查V21修正说明
import inspect
source = inspect.getsource(ConsumeIndexHealthChecker)
has_v21_correction = 'V21修正' in source or 'V21_corrected' in source
has_new_criteria = '有未消费消息' in source or 'unconsumed' in source
has_no_false_positive = '无新消息' in source or '正常现象' in source
has_60_minutes = '60' in source

print(f'  V21修正说明: {has_v21_correction}')
print(f'  新判据（有未消费消息）: {has_new_criteria}')
print(f'  消除误报（无新消息正常）: {has_no_false_positive}')
print(f'  阈值提高到60分钟: {has_60_minutes}')

# 测试场景1：索引正常（刚更新）→ 健康
print()
print('【3 场景1：索引正常（刚更新）→ 健康】')
# 创建临时消费索引文件（刚更新）
test_index_file = os.path.join(r'D:\AI-Tools\feishu\V13方案增强\scripts', '.consume_index_test.json')
test_data = {
    "current_index": 100,
    "updated_at": datetime.now().isoformat(),
    "last_message_id": "om_test_001"
}
with open(test_index_file, 'w', encoding='utf-8') as f:
    json.dump(test_data, f)

with patch('v19_integration.CONSUME_INDEX_FILE', test_index_file):
    result = ConsumeIndexHealthChecker.check(check_unconsumed_messages=False)
    print(f'  healthy: {result["healthy"]}')
    print(f'  age_minutes: {result["age_minutes"]:.1f}')
    print(f'  stale: {result["stale"]}')
    print(f'  issues: {result["issues"]}')
    assert result["healthy"] == True
    assert result["stale"] == False
    print('  → 索引正常时健康（不误报）✅')

# 测试场景2：索引过期但无新消息 → 正常，不告警（消除永久误报）
print()
print('【4 场景2：索引过期但无新消息 → 正常，不告警（消除永久误报）】')
# 创建过期的消费索引文件（2小时前更新）
stale_data = {
    "current_index": 100,
    "updated_at": (datetime.now() - timedelta(hours=2)).isoformat(),
    "last_message_id": "om_test_001"
}
with open(test_index_file, 'w', encoding='utf-8') as f:
    json.dump(stale_data, f)

# mock：没有用户消息（只有机器人消息）
mock_no_user_messages = {
    "data": {
        "messages": [
            {"sender": {"sender_type": "app"}, "message_id": "om_bot_001"},
            {"sender": {"sender_type": "app"}, "message_id": "om_bot_002"},
        ]
    }
}

with patch('v19_integration.CONSUME_INDEX_FILE', test_index_file), \
     patch('v19_integration.run_cmd') as mock_run_cmd:
    mock_run_cmd.return_value = (True, json.dumps(mock_no_user_messages), '')
    
    result = ConsumeIndexHealthChecker.check(stale_threshold_minutes=60, check_unconsumed_messages=True)
    print(f'  healthy: {result["healthy"]}')
    print(f'  age_minutes: {result["age_minutes"]:.1f}')
    print(f'  stale: {result["stale"]}')
    print(f'  has_unconsumed_messages: {result["has_unconsumed_messages"]}')
    print(f'  unconsumed_count: {result["unconsumed_count"]}')
    print(f'  issues: {result["issues"]}')
    
    # 索引过期但无新消息 → 健康（不告警）
    assert result["healthy"] == True, "索引过期但无新消息应健康（不告警）"
    assert result["stale"] == True
    assert result["has_unconsumed_messages"] == False
    print('  → 索引过期但无新消息时正常，不告警（消除永久误报）✅')

# 测试场景3：索引过期且有未消费消息 → 异常，告警
print()
print('【5 场景3：索引过期且有未消费消息 → 异常，告警】')
# mock：有用户消息
mock_with_user_messages = {
    "data": {
        "messages": [
            {"sender": {"sender_type": "user"}, "message_id": "om_user_001"},
            {"sender": {"sender_type": "user"}, "message_id": "om_user_002"},
            {"sender": {"sender_type": "user"}, "message_id": "om_user_003"},
        ]
    }
}

with patch('v19_integration.CONSUME_INDEX_FILE', test_index_file), \
     patch('v19_integration.run_cmd') as mock_run_cmd:
    mock_run_cmd.return_value = (True, json.dumps(mock_with_user_messages), '')
    
    result = ConsumeIndexHealthChecker.check(stale_threshold_minutes=60, check_unconsumed_messages=True)
    print(f'  healthy: {result["healthy"]}')
    print(f'  age_minutes: {result["age_minutes"]:.1f}')
    print(f'  stale: {result["stale"]}')
    print(f'  has_unconsumed_messages: {result["has_unconsumed_messages"]}')
    print(f'  unconsumed_count: {result["unconsumed_count"]}')
    print(f'  issues: {result["issues"]}')
    
    # 索引过期且有未消费消息 → 不健康（告警）
    assert result["healthy"] == False, "索引过期且有未消费消息应不健康（告警）"
    assert result["stale"] == True
    assert result["has_unconsumed_messages"] == True
    assert result["unconsumed_count"] == 3
    print('  → 索引过期且有未消费消息时异常，告警（正确检测）✅')

# 测试场景4：消费索引文件不存在 → 异常
print()
print('【6 场景4：消费索引文件不存在 → 异常】')
nonexistent_file = os.path.join(r'D:\AI-Tools\feishu\V13方案增强\scripts', '.consume_index_nonexistent.json')
if os.path.exists(nonexistent_file):
    os.remove(nonexistent_file)

with patch('v19_integration.CONSUME_INDEX_FILE', nonexistent_file):
    result = ConsumeIndexHealthChecker.check(check_unconsumed_messages=False)
    print(f'  healthy: {result["healthy"]}')
    print(f'  issues: {result["issues"]}')
    assert result["healthy"] == False
    assert "不存在" in result["issues"][0]
    print('  → 消费索引文件不存在时正确告警 ✅')

# 检查已接线到learning_system.py主流程
print()
print('【7 接线检查：已接线到learning_system.py主流程】')
try:
    with open(r'D:\AI-Tools\feishu\V13方案增强\scripts\learning_system.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    has_import = 'ConsumeIndexHealthChecker' in content
    has_call = 'ConsumeIndexHealthChecker.check()' in content
    has_warn_log = '消费索引健康检查异常' in content or 'WARN' in content
    
    print(f'  导入ConsumeIndexHealthChecker: {has_import}')
    print(f'  调用ConsumeIndexHealthChecker.check(): {has_call}')
    print(f'  不健康时记录WARN日志: {has_warn_log}')
    
    if all([has_import, has_call, has_warn_log]):
        print('  → 已完整接线到learning_system.py主流程 ✅')
    else:
        print('  → 接线不完整 ⚠️')
except Exception as e:
    print(f'  接线检查失败: {e}')

# 清理测试文件
if os.path.exists(test_index_file):
    os.remove(test_index_file)

print()
print('═══ 单元级验证完成 ═══')
