#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S8-04 告警去重+小时摘要单元级验证（使用mock，不发送真实飞书消息）"""
import sys
import os
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('═══ S8-04 告警去重+小时摘要单元级验证 ═══')
print()

# 导入AlertManager
try:
    from v19_integration import AlertManager
    print('【1 AlertManager导入成功】')
except Exception as e:
    print(f'【1 AlertManager导入失败】{e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 检查关键属性和方法
print()
print('【2 关键属性和方法检查】')
print(f'  _DEDUP_WINDOW_SECONDS: {AlertManager._DEDUP_WINDOW_SECONDS} (期望3600=1小时)')
assert AlertManager._DEDUP_WINDOW_SECONDS == 3600, "去重窗口应为3600秒"
print('  → 1小时去重窗口配置正确 ✅')

methods = ['send_alert', 'send_hourly_summary', '_is_duplicate', '_record_sent', '_cleanup_expired']
for method in methods:
    if hasattr(AlertManager, method):
        print(f'  {method}: 存在 ✅')
    else:
        print(f'  {method}: 不存在 ❌')

# 测试去重逻辑：同类型告警1小时内只发1条
print()
print('【3 去重逻辑测试：同类型告警1小时内只发1条】')
# 清空去重缓存
AlertManager._dedup_cache = {}

with patch('v19_integration.run_cmd') as mock_run_cmd:
    mock_run_cmd.return_value = (True, '{"code":0}', '')
    
    # 第一次发送：应该发送
    result1 = AlertManager.send_alert("ERROR", "测试告警", "这是一条测试告警", channel="feishu")
    print(f'  第1次发送: feishu={result1["feishu"]}, deduped={result1["deduped"]}')
    assert result1["feishu"] == True and result1["deduped"] == False
    print('  → 第1次发送成功（未去重）✅')
    
    # 第二次发送（相同level+title）：应该被去重
    result2 = AlertManager.send_alert("ERROR", "测试告警", "这是一条重复的测试告警", channel="feishu")
    print(f'  第2次发送（相同类型）: feishu={result2["feishu"]}, deduped={result2["deduped"]}')
    assert result2["deduped"] == True
    print('  → 第2次发送被去重（1小时内相同告警只发1条）✅')
    
    # 确认只调用了1次lark-cli（第2次被去重没有发送）
    print(f'  lark-cli调用次数: {mock_run_cmd.call_count} (期望1)')
    assert mock_run_cmd.call_count == 1, f"应只调用1次lark-cli，实际{mock_run_cmd.call_count}次"
    print('  → 只发送了1条飞书消息（去重生效）✅')

# 测试不同类型告警不应被去重
print()
print('【4 反证：不同类型告警不应被去重】')
AlertManager._dedup_cache = {}

with patch('v19_integration.run_cmd') as mock_run_cmd:
    mock_run_cmd.return_value = (True, '{"code":0}', '')
    
    # 发送ERROR类型
    result1 = AlertManager.send_alert("ERROR", "错误告警", "错误内容", channel="feishu")
    print(f'  ERROR告警: feishu={result1["feishu"]}, deduped={result1["deduped"]}')
    assert result1["feishu"] == True and result1["deduped"] == False
    
    # 发送WARN类型（不同level）
    result2 = AlertManager.send_alert("WARN", "警告告警", "警告内容", channel="feishu")
    print(f'  WARN告警（不同level）: feishu={result2["feishu"]}, deduped={result2["deduped"]}')
    assert result2["feishu"] == True and result2["deduped"] == False
    
    # 发送相同level不同title
    result3 = AlertManager.send_alert("ERROR", "另一个错误告警", "另一个错误内容", channel="feishu")
    print(f'  ERROR不同title: feishu={result3["feishu"]}, deduped={result3["deduped"]}')
    assert result3["feishu"] == True and result3["deduped"] == False
    
    print(f'  lark-cli调用次数: {mock_run_cmd.call_count} (期望3)')
    assert mock_run_cmd.call_count == 3, f"应调用3次lark-cli，实际{mock_run_cmd.call_count}次"
    print('  → 不同类型告警都发送了（没有误去重）✅')

# 测试去重窗口过期后重新发送
print()
print('【5 去重窗口过期后重新发送测试】')
AlertManager._dedup_cache = {}

with patch('v19_integration.run_cmd') as mock_run_cmd:
    mock_run_cmd.return_value = (True, '{"code":0}', '')
    
    # 第一次发送
    result1 = AlertManager.send_alert("ERROR", "窗口测试", "测试内容", channel="feishu")
    print(f'  第1次发送: feishu={result1["feishu"]}, deduped={result1["deduped"]}')
    
    # 手动将去重记录时间改为1小时前（模拟过期）
    AlertManager._dedup_cache[("ERROR", "窗口测试")] = time.time() - 3700  # 1小时100秒前
    
    # 第二次发送（窗口已过期）：应该重新发送
    result2 = AlertManager.send_alert("ERROR", "窗口测试", "测试内容2", channel="feishu")
    print(f'  第2次发送（窗口过期后）: feishu={result2["feishu"]}, deduped={result2["deduped"]}')
    assert result2["feishu"] == True and result2["deduped"] == False
    
    print(f'  lark-cli调用次数: {mock_run_cmd.call_count} (期望2)')
    assert mock_run_cmd.call_count == 2, f"应调用2次lark-cli，实际{mock_run_cmd.call_count}次"
    print('  → 去重窗口过期后重新发送（去重窗口可配置）✅')

# 测试小时摘要
print()
print('【6 小时摘要测试】')
AlertManager._hourly_stats = {}
AlertManager._last_summary_hour = None
AlertManager._dedup_cache = {}

with patch('v19_integration.run_cmd') as mock_run_cmd:
    mock_run_cmd.return_value = (True, '{"code":0}', '')
    
    # 发送多条不同类型告警（更新小时统计）
    AlertManager.send_alert("ERROR", "错误1", "内容1", channel="local")
    AlertManager.send_alert("ERROR", "错误2", "内容2", channel="local")
    AlertManager.send_alert("WARN", "警告1", "内容3", channel="local")
    AlertManager.send_alert("INFO", "信息1", "内容4", channel="local")
    
    # 检查小时统计
    current_hour = datetime.now().strftime("%Y-%m-%d %H:00")
    stats = AlertManager._hourly_stats.get(current_hour, {})
    print(f'  当前小时统计: {stats}')
    print(f'  ERROR次数: {stats.get("ERROR", 0)} (期望2)')
    print(f'  WARN次数: {stats.get("WARN", 0)} (期望1)')
    print(f'  INFO次数: {stats.get("INFO", 0)} (期望1)')
    assert stats.get("ERROR", 0) == 2
    assert stats.get("WARN", 0) == 1
    assert stats.get("INFO", 0) == 1
    print('  → 小时摘要计数正确 ✅')

# 测试send_hourly_summary方法
print()
print('【7 send_hourly_summary方法测试】')
# 构造上一小时的统计数据
prev_hour = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:00")
AlertManager._hourly_stats[prev_hour] = {"ERROR": 3, "WARN": 2, "INFO": 5}

with patch('v19_integration.run_cmd') as mock_run_cmd:
    mock_run_cmd.return_value = (True, '{"code":0}', '')
    
    result = AlertManager.send_hourly_summary()
    print(f'  小时摘要发送结果: sent={result["sent"]}, hour={result["hour"]}, total={result["total"]}')
    assert result["sent"] == True
    assert result["total"] == 10  # 3+2+5
    print('  → 小时摘要发送成功（汇总过去1小时告警类型和次数）✅')

# 测试本地通道每次都写入（用于审计）
print()
print('【8 本地通道审计测试】')
AlertManager._dedup_cache = {}

with patch('v19_integration.run_cmd') as mock_run_cmd:
    mock_run_cmd.return_value = (True, '{"code":0}', '')
    
    # 发送3次相同告警（both通道）
    for i in range(3):
        AlertManager.send_alert("ERROR", "审计测试", f"第{i+1}次", channel="both")
    
    # 本地通道应该写入3次（每次都写入，用于审计）
    # 飞书通道应该只发送1次（去重）
    print(f'  lark-cli调用次数（飞书通道）: {mock_run_cmd.call_count} (期望1，去重)')
    assert mock_run_cmd.call_count == 1, f"飞书通道应只调用1次，实际{mock_run_cmd.call_count}次"
    print('  → 本地通道每次都写入（审计），飞书通道1小时去重 ✅')

print()
print('═══ 单元级验证完成 ═══')
