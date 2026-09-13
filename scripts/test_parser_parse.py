#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试parser.parse对答题消息的解析行为"""
import sys, os
sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

from learning_system import InstructionParser, get_all_cards

parser = InstructionParser()
cards = get_all_cards()
print('今日卡片数:', len(cards))

# 测试不同消息格式的解析
test_messages = ['会', '1会', '第1张会', '卡片1会']
for msg in test_messages:
    try:
        action, data = parser.parse(msg, cards)
        card_idx = data.get('card_index') if data else None
        result = data.get('result') if data else None
        print(f'消息="{msg}" -> action={action}, card_index={card_idx}, result={result}')
    except Exception as e:
        print(f'消息="{msg}" -> 解析异常: {e}')
