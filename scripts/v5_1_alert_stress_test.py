#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V5-1 S8-04 告警去重+小时摘要 60次真实压测脚本"""
import sys, os, json, time
sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

from v19_integration import AlertManager

print('=' * 60)
print('V5-1 S8-04 告警去重+小时摘要 60次真实压测')
print('=' * 60)

# 步骤0: 清空去重缓存和小时统计（确保压测从干净状态开始）
print('\n【步骤0】清空去重缓存和小时统计')
AlertManager._dedup_cache.clear()
AlertManager._hourly_stats.clear()
AlertManager._last_summary_hour = None
print(f'  去重缓存已清空: {len(AlertManager._dedup_cache)} 条')
print(f'  小时统计已清空: {len(AlertManager._hourly_stats)} 条')

# 步骤1: 连续触发60次同类告警
print('\n【步骤1】连续触发60次同类告警 (level=WARN, title="V33压测-同类告警")')
test_level = "WARN"
test_title = "V33压测-同类告警"
test_message = "这是一条V33压测测试告警，用于验证去重逻辑"

sent_count = 0
deduped_count = 0
local_count = 0
results = []

for i in range(60):
    result = AlertManager.send_alert(test_level, test_title, f"{test_message} #{i+1}", channel="both")
    results.append(result)
    if result.get("local"):
        local_count += 1
    if result.get("deduped"):
        deduped_count += 1
    elif result.get("feishu"):
        sent_count += 1
    
    if (i + 1) % 10 == 0:
        print(f'  已触发 {i+1}/60 次: 实际发送={sent_count}, 被去重={deduped_count}, 本地日志={local_count}')

print(f'\n  压测完成:')
print(f'    总触发次数: 60')
print(f'    实际发送飞书消息: {sent_count} 条')
print(f'    被去重跳过: {deduped_count} 条')
print(f'    本地日志写入: {local_count} 条')

# 验证去重效果
print(f'\n  去重验证:')
if sent_count == 1:
    print(f'    ✅ 通过: 60次同类告警只发送了1条飞书消息（去重生效）')
else:
    print(f'    ❌ 失败: 60次同类告警发送了{sent_count}条飞书消息（去重未生效）')

if deduped_count == 59:
    print(f'    ✅ 通过: 59次被正确去重')
else:
    print(f'    ⚠️  注意: {deduped_count}次被去重（预期59次）')

# 步骤2: 检查小时摘要
print('\n【步骤2】检查小时摘要')
print(f'  小时统计: {json.dumps(AlertManager._hourly_stats, ensure_ascii=False)}')
print(f'  最后摘要小时: {AlertManager._last_summary_hour}')

# 手动触发小时摘要发送
print(f'\n  手动触发小时摘要发送:')
summary_result = AlertManager.send_hourly_summary()
print(f'    发送结果: {json.dumps(summary_result, ensure_ascii=False)}')

# 步骤3: 反证 - 改变告警类型再触发，应作为新类型重新发送
print('\n【步骤3】反证: 改变告警类型再触发，应作为新类型重新发送')
new_level = "ERROR"
new_title = "V33压测-不同类型"
new_message = "这是一条不同类型的告警，验证不会被误去重"

result_new = AlertManager.send_alert(new_level, new_title, new_message, channel="both")
print(f'  新告警结果:')
print(f'    feishu发送: {result_new.get("feishu")}')
print(f'    被去重: {result_new.get("deduped")}')
print(f'    本地日志: {result_new.get("local")}')

if result_new.get("feishu") and not result_new.get("deduped"):
    print(f'    ✅ 反证通过: 不同类型告警被正常发送（未被误去重）')
else:
    print(f'    ❌ 反证失败: 不同类型告警被误去重或发送失败')

# 步骤4: 检查本地告警日志
print('\n【步骤4】检查本地告警日志')
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alerts.log')
if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    print(f'  日志文件: {log_file}')
    print(f'  总日志行数: {len(lines)}')
    print(f'  最近5条:')
    for line in lines[-5:]:
        print(f'    {line.strip()[:100]}')
else:
    print(f'  日志文件不存在: {log_file}')

# 步骤5: 清理测试数据
print('\n【步骤5】清理测试数据')
# 从告警日志中删除V33压测相关记录
if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    original_count = len(lines)
    cleaned_lines = [line for line in lines if 'V33压测' not in line]
    with open(log_file, 'w', encoding='utf-8') as f:
        f.writelines(cleaned_lines)
    print(f'  已清理告警日志: 删除{original_count - len(cleaned_lines)}条测试记录，剩余{len(cleaned_lines)}条')
else:
    print(f'  告警日志文件不存在，无需清理')

# 清空去重缓存中的测试数据
AlertManager._dedup_cache.clear()
print(f'  已清空去重缓存')

print('\n' + '=' * 60)
print('V5-1 压测完成')
print('=' * 60)
