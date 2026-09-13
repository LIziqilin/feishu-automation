#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V4-1 S5-05 DLQ真实重试验证 - 代码逻辑验证（不修改生产数据）"""
import sys
import os
import json
sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('=== V4-1 S5-05 DLQ真实重试验证 - 代码逻辑验证 ===')
print()

# 模拟InstructionParser.parse返回的answer数据结构
print('【1 模拟InstructionParser.parse返回的answer数据结构】')
mock_answer_data = {
    "result": "会",
    "card_index": 0,
    "explicit": False
}
print('mock_answer_data:', json.dumps(mock_answer_data, ensure_ascii=False))
print()

# 检查retry_pending中的条件
print('【2 检查retry_pending第1140行条件】')
print('条件: if action == "answer" and data and data.get("card_id"):')
print()
print('action = "answer"')
print('data =', json.dumps(mock_answer_data, ensure_ascii=False))
print('data.get("card_id") =', mock_answer_data.get("card_id"))
print()

if mock_answer_data.get("card_id"):
    print('✅ 条件满足，会进入写入流水分支（第1142-1180行）')
else:
    print('❌ 条件不满足，会进入else分支（第1182-1188行）')
    print('   即：标记为成功，但不写入流水！')
    print()
    print('【问题确认】')
    print('InstructionParser.parse返回的answer数据中字段名是"card_index"，不是"card_id"')
    print('retry_pending第1140行检查data.get("card_id")，永远返回None')
    print('因此answer类型的DLQ消息重试时，不会写入流水，只是被标记为成功')
    print('这是一个真实的bug：DLQ重试对answer类型消息无效！')

print()
print('【3 验证其他action类型】')
test_actions = {
    "answer": {"result": "会", "card_index": 0},
    "batch_answer": {"answers": [{"result": "会", "card_index": 0}]},
    "revoke": {"target_event_id": "test"},
    "insight": {"content": "测试洞察"},
    "ignore": None,
    "parse_error": {"raw": "测试"}
}

for action, data in test_actions.items():
    if action == "answer" and data and data.get("card_id"):
        result = "进入写入流水分支"
    elif action in ("answer", "batch_answer", "revoke", "insight"):
        if action == "answer":
            result = "进入else分支（标记成功，不写流水）❌"
        else:
            result = "进入第1182行else分支（标记成功）"
    elif action == "ignore":
        result = "进入第1189行ignore分支（标记成功）"
    else:
        result = "进入第1197行else分支（重试失败）"
    print(f'  action={action}: {result}')

print()
print('【4 结论】')
print('DLQ重试对answer类型消息存在bug：')
print('  - 原因：第1140行检查data.get("card_id")，但实际字段名是card_index')
print('  - 影响：answer类型的DLQ消息重试时不会写入流水，只是被标记为成功')
print('  - 修复：将data.get("card_id")改为根据card_index从today_cards中获取card_id')
print()
print('其他类型消息（batch_answer/revoke/insight）也只是标记为成功，没有真正重新处理')
print('只有ignore类型消息的处理是合理的（闲聊无需处理）')
