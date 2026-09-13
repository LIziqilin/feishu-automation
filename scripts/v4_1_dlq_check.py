#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V4-1 S5-05 DLQ真实重试验证 - 现状取证"""
import sys
import os
import json
sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
from v19_integration import DLQManager

print('=== V4-1 S5-05 DLQ真实重试验证 - 现状取证 ===')
print()

# 检查DLQ队列状态
print('【1 DLQ队列当前状态】')
dlq_file = os.path.join(r'D:\AI-Tools\feishu\V13方案增强\scripts', '.dlq_queue.json')
if os.path.exists(dlq_file):
    with open(dlq_file, 'r', encoding='utf-8') as f:
        queue = json.load(f)
    print('DLQ文件存在:')
    print('  消息总数:', len(queue.get('messages', [])))
    print('  最后重试时间:', queue.get('last_retry'))
    print('  总重试次数:', queue.get('retry_count'))
    print()
    if queue.get('messages'):
        print('消息详情:')
        for i, msg in enumerate(queue['messages']):
            mid = msg.get('message_id', 'unknown')
            status = msg.get('status', 'unknown')
            rc = msg.get('retry_count', 0)
            mtext = msg.get('message_text', '')[:50]
            etype = msg.get('error_type', '')
            print(f'  [{i+1}] message_id={mid}, status={status}, retry_count={rc}')
            print(f'       message_text={mtext}')
            print(f'       error_type={etype}')
else:
    print('DLQ文件不存在（队列为空）')

print()
print('【2 DLQ队列统计】')
stats = DLQManager.get_queue_stats()
print(json.dumps(stats, ensure_ascii=False, indent=2))

print()
print('【3 关键代码审查】')
print('retry_pending方法第1140行: if action == "answer" and data and data.get("card_id"):')
print()
print('InstructionParser.parse返回的answer数据结构:')
print('  {"result": result, "card_index": card_index, "explicit": True}')
print()
print('⚠️  潜在问题: data中字段名是"card_index"，不是"card_id"')
print('   这意味着answer类型消息可能不会进入写入流水分支，而是被标记为成功（第1182行）')
