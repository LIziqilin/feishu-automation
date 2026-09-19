#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修改send_immediate方法，减少消息量"""

# 读取文件
with open('learning_system.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 找到send_immediate方法，改成不发送即时回执
old_code = '''    def send_immediate(self, result, card_title=None, explicit=False):
        """第一段：即时确认（<3s）"""
        if explicit:
            return msg'''

new_code = '''    def send_immediate(self, result, card_title=None, explicit=False):
        """第一段：即时确认（<3s）- V15优化：不发送即时回执，减少消息量"""
        # V15优化：不发送即时回执，避免大量消息打扰
        # 只在控制台打印，不发送到群里
        print(f"  [答题记录] {result} - {card_title[:20] if card_title else ''}...")
        return "已记录"'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('learning_system.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('✅ 已修改send_immediate方法，不再发送即时回执')
else:
    print('❌ 未找到目标代码')
    # 打印一下附近的代码
    lines = content.split('\\n')
    for i, line in enumerate(lines):
        if 'def send_immediate' in line:
            print(f'第{i+1}行: {line}')
            for j in range(i, min(i+10, len(lines))):
                print(f'  {j+1}: {lines[j]}')
