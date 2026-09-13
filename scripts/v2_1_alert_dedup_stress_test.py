#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V2-1 S8-04 告警去重60次真实压测"""
import sys
import os
import json
import time
sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
from v19_integration import AlertManager

print('=' * 60)
print('V2-1 S8-04 告警去重60次真实压测')
print('=' * 60)

# 压测前状态
print('\n【压测前状态】')
print('去重缓存大小:', len(AlertManager._dedup_cache))
print('去重窗口:', AlertManager._DEDUP_WINDOW_SECONDS, '秒')

# 记录压测前alerts.log行数
alerts_log = os.path.join(r'D:\AI-Tools\feishu\V13方案增强\scripts', 'alerts.log')
before_lines = 0
if os.path.exists(alerts_log):
    with open(alerts_log, 'r', encoding='utf-8') as f:
        before_lines = len(f.readlines())
print('压测前alerts.log行数:', before_lines)

# 执行60次相同告警压测
print('\n【执行60次相同告警压测】')
print('告警级别: WARN')
print('告警标题: V31压测_测试告警去重')
print('告警内容: 这是一条测试告警，用于验证60次连续触发只发1条飞书消息')

results = []
feishu_sent_count = 0
feishu_deduped_count = 0
local_written_count = 0

for i in range(60):
    result = AlertManager.send_alert(
        level="WARN",
        title="V31压测_测试告警去重",
        message=f"这是第{i+1}次测试告警，用于验证去重功能",
        channel="both"
    )
    results.append(result)
    if result.get("local"):
        local_written_count += 1
    if result.get("feishu") and not result.get("deduped"):
        feishu_sent_count += 1
    if result.get("deduped"):
        feishu_deduped_count += 1
    
    if (i + 1) % 10 == 0:
        print(f'  已执行 {i+1}/60 次，飞书发送: {feishu_sent_count}, 去重: {feishu_deduped_count}, 本地写入: {local_written_count}')

# 压测后状态
print('\n【压测后状态】')
print('总执行次数:', len(results))
print('飞书实际发送次数:', feishu_sent_count)
print('飞书去重次数:', feishu_deduped_count)
print('本地写入次数:', local_written_count)

# 验证alerts.log行数
after_lines = 0
if os.path.exists(alerts_log):
    with open(alerts_log, 'r', encoding='utf-8') as f:
        after_lines = len(f.readlines())
print('压测后alerts.log行数:', after_lines)
print('alerts.log新增行数:', after_lines - before_lines)

# 验证去重缓存
print('\n【去重缓存验证】')
print('去重缓存大小:', len(AlertManager._dedup_cache))
for key, timestamp in AlertManager._dedup_cache.items():
    print(f'  key: {key}, timestamp: {timestamp}')

# 验证小时摘要
print('\n【小时摘要验证】')
print('小时统计:', json.dumps(AlertManager._hourly_stats, ensure_ascii=False, indent=2))
print('最后摘要小时:', AlertManager._last_summary_hour)

# 结论
print('\n' + '=' * 60)
print('压测结论')
print('=' * 60)
print(f'✅ 60次相同告警，飞书实际发送: {feishu_sent_count}次（预期1次）')
print(f'✅ 飞书去重: {feishu_deduped_count}次（预期59次）')
print(f'✅ 本地写入: {local_written_count}次（预期60次，本地通道不去重用于审计）')
print(f'✅ alerts.log新增: {after_lines - before_lines}行（预期60行）')

if feishu_sent_count == 1 and feishu_deduped_count == 59 and local_written_count == 60:
    print('\n🎉 告警去重功能验证通过！')
else:
    print('\n⚠️  告警去重功能存在异常，需要进一步检查')
