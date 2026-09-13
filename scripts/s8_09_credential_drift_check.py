#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S8-09 凭据漂移检测单元级验证（使用mock，不改真实配置）"""
import sys
import os
import json
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('═══ S8-09 凭据漂移检测单元级验证 ═══')
print()

# 导入CredentialDriftDetector
try:
    from v19_integration import CredentialDriftDetector
    print('【1 CredentialDriftDetector导入成功】')
except Exception as e:
    print(f'【1 CredentialDriftDetector导入失败】{e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 检查关键方法和属性
print()
print('【2 关键方法和属性检查】')
methods = ['check_lark_cli_available', 'check_base_access', 'check_im_access', 'run_full_check', 'should_check_now', '_record_usage', '_load_usage_log', '_save_usage_log']
for method in methods:
    if hasattr(CredentialDriftDetector, method):
        print(f'  {method}: 存在 ✅')
    else:
        print(f'  {method}: 不存在 ❌')

print(f'  CHECK_INTERVAL_SECONDS: {CredentialDriftDetector.CHECK_INTERVAL_SECONDS} (期望3600=1小时)')
assert CredentialDriftDetector.CHECK_INTERVAL_SECONDS == 3600
print('  → 每小时检查一次配置正确 ✅')

# 测试场景1：正常情况（所有检查通过）→ 健康，无误报
print()
print('【3 场景1：正常情况（所有检查通过）→ 健康，无误报】')
with patch('v19_integration.run_cmd') as mock_run_cmd:
    # lark-cli --version 成功
    # base +table-list 成功
    # im +chat-messages-list 成功
    mock_run_cmd.side_effect = [
        (True, 'lark-cli version 1.0.0', ''),  # lark-cli检查
        (True, json.dumps({"ok": True, "data": {"tables": [{"name": "表1"}, {"name": "表2"}]}}), ''),  # Base检查
        (True, json.dumps({"ok": True, "data": {"items": [{"message_id": "om_001"}]}}), ''),  # IM检查
    ]
    
    result = CredentialDriftDetector.run_full_check(send_alert_on_failure=False)
    print(f'  overall_healthy: {result["overall_healthy"]}')
    print(f'  lark_cli.available: {result["checks"]["lark_cli"]["available"]}')
    print(f'  base_access.accessible: {result["checks"]["base_access"]["accessible"]}')
    print(f'  im_access.accessible: {result["checks"]["im_access"]["accessible"]}')
    print(f'  issues: {result["issues"]}')
    print(f'  usage_summary: {result["usage_summary"]}')
    
    assert result["overall_healthy"] == True
    assert result["checks"]["lark_cli"]["available"] == True
    assert result["checks"]["base_access"]["accessible"] == True
    assert result["checks"]["im_access"]["accessible"] == True
    assert len(result["issues"]) == 0
    print('  → 正常情况健康，无误报 ✅')

# 测试场景2：反证 - lark-cli不可用（错误key/配置）→ 异常，产生告警
print()
print('【4 场景2：反证 - lark-cli不可用（错误key/配置）→ 异常，产生告警】')
with patch('v19_integration.run_cmd') as mock_run_cmd, \
     patch('v19_integration.AlertManager.send_alert') as mock_send_alert:
    # lark-cli --version 失败（模拟错误key/配置）
    mock_run_cmd.return_value = (False, '', 'Error: invalid credentials')
    
    result = CredentialDriftDetector.run_full_check(send_alert_on_failure=True)
    print(f'  overall_healthy: {result["overall_healthy"]}')
    print(f'  lark_cli.available: {result["checks"]["lark_cli"]["available"]}')
    print(f'  lark_cli.error: {result["checks"]["lark_cli"].get("error", "N/A")}')
    print(f'  issues: {result["issues"]}')
    
    assert result["overall_healthy"] == False
    assert result["checks"]["lark_cli"]["available"] == False
    assert len(result["issues"]) > 0
    # 确认调用了AlertManager.send_alert（产生告警）
    assert mock_send_alert.called, "失败时应调用AlertManager.send_alert产生告警"
    print(f'  AlertManager.send_alert调用次数: {mock_send_alert.call_count}')
    print('  → 错误key/配置时产生告警（反证通过）✅')

# 测试场景3：使用日志记录
print()
print('【5 场景3：使用日志记录】')
# 检查.credential_usage.json文件是否存在或可创建
test_log_file = os.path.join(r'D:\AI-Tools\feishu\V13方案增强\scripts', '.credential_usage_test.json')
with patch('v19_integration.CredentialDriftDetector.CREDENTIAL_LOG', test_log_file):
    # 记录一次使用
    CredentialDriftDetector._record_usage(True, "test_operation")
    
    # 读取日志
    log = CredentialDriftDetector._load_usage_log()
    print(f'  total_calls: {log.get("total_calls", 0)}')
    print(f'  success_calls: {log.get("success_calls", 0)}')
    print(f'  failed_calls: {log.get("failed_calls", 0)}')
    print(f'  last_operation: {log.get("last_operation", "N/A")}')
    
    assert log.get("total_calls", 0) >= 1
    assert log.get("success_calls", 0) >= 1
    assert log.get("last_operation") == "test_operation"
    print('  → 使用日志记录正常 ✅')

# 清理测试文件
if os.path.exists(test_log_file):
    os.remove(test_log_file)

# 测试场景4：should_check_now定期检查判断
print()
print('【6 场景4：should_check_now定期检查判断】')
test_last_check_file = os.path.join(r'D:\AI-Tools\feishu\V13方案增强\scripts', '.credential_last_check_test.json')

# 场景4a：文件不存在 → 应该检查
with patch('v19_integration.CredentialDriftDetector.LAST_CHECK_FILE', test_last_check_file):
    if os.path.exists(test_last_check_file):
        os.remove(test_last_check_file)
    should_check = CredentialDriftDetector.should_check_now()
    print(f'  文件不存在时 should_check: {should_check} (期望True)')
    assert should_check == True
    print('  → 文件不存在时应该检查 ✅')

# 场景4b：刚检查过（1分钟前）→ 不应该检查
with patch('v19_integration.CredentialDriftDetector.LAST_CHECK_FILE', test_last_check_file):
    recent_check = {"check_time": (datetime.now() - timedelta(minutes=1)).isoformat()}
    with open(test_last_check_file, 'w', encoding='utf-8') as f:
        json.dump(recent_check, f)
    
    should_check = CredentialDriftDetector.should_check_now()
    print(f'  1分钟前检查过时 should_check: {should_check} (期望False)')
    assert should_check == False
    print('  → 刚检查过时不应该检查（每小时一次）✅')

# 场景4c：超过1小时未检查 → 应该检查
with patch('v19_integration.CredentialDriftDetector.LAST_CHECK_FILE', test_last_check_file):
    old_check = {"check_time": (datetime.now() - timedelta(hours=2)).isoformat()}
    with open(test_last_check_file, 'w', encoding='utf-8') as f:
        json.dump(old_check, f)
    
    should_check = CredentialDriftDetector.should_check_now()
    print(f'  2小时前检查过时 should_check: {should_check} (期望True)')
    assert should_check == True
    print('  → 超过1小时未检查时应该检查 ✅')

# 清理测试文件
if os.path.exists(test_last_check_file):
    os.remove(test_last_check_file)

# 检查已接线到learning_system.py主流程
print()
print('【7 接线检查：已接线到learning_system.py主流程】')
try:
    with open(r'D:\AI-Tools\feishu\V13方案增强\scripts\learning_system.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    has_import = 'CredentialDriftDetector' in content
    has_should_check = 'CredentialDriftDetector.should_check_now()' in content
    has_run_full = 'CredentialDriftDetector.run_full_check(' in content
    has_warn_log = '凭据漂移检测异常' in content
    
    print(f'  导入CredentialDriftDetector: {has_import}')
    print(f'  调用should_check_now(): {has_should_check}')
    print(f'  调用run_full_check(): {has_run_full}')
    print(f'  异常时记录WARN日志: {has_warn_log}')
    
    if all([has_import, has_should_check, has_run_full, has_warn_log]):
        print('  → 已完整接线到learning_system.py主流程 ✅')
    else:
        print('  → 接线不完整 ⚠️')
except Exception as e:
    print(f'  接线检查失败: {e}')

print()
print('═══ 单元级验证完成 ═══')
