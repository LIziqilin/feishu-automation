#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修改send_immediate方法，不再发送即时回执"""

# 读取文件
with open('learning_system.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到send_immediate方法
found = False
for i, line in enumerate(lines):
    if 'def send_immediate(self, result, card_title=None, explicit=False):' in line:
        print(f'找到send_immediate在第{i+1}行')
        # 修改这个方法的内容，改成不发送
        # 替换接下来的几行
        lines[i+1] = '        """第一段：即时确认（V15优化：不发送到群里，只打印）"""\n'
        lines[i+2] = '        # V15优化：不发送即时回执，避免大量消息打扰\n'
        lines[i+3] = '        # 只在控制台打印，减少群消息量\n'
        lines[i+4] = '        print(f"  [答题记录] {result} - {card_title[:20] if card_title else \'\'}...")\n'
        lines[i+5] = '        return "已记录"\n'
        # 删除原来的代码行
        j = i + 6
        while j < len(lines) and not lines[j].strip().startswith('def send_delayed'):
            lines[j] = ''  # 清空原来的代码行
            j += 1
        found = True
        break

if found:
    with open('learning_system.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print('✅ 已修改send_immediate方法，不再发送即时回执')
else:
    print('❌ 未找到send_immediate方法')
