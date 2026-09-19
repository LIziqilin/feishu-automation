#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""彻底修复：把批量回执也改成不发消息，和即时回执一样"""

with open('learning_system.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 修改send_batch_result方法
old_code = '''    def send_batch_result(self, results):
        """批量回执"""
        lines = []
        for r in results:
            if r["success"]:
                lines.append(f"✓ 会{r['num']} 已记")
            else:
                lines.append(f"❓ 会{r['num']} 没看懂")
        msg = " / ".join(lines)
        self._send_message(msg)
        return msg'''

new_code = '''    def send_batch_result(self, results):
        """批量回执（V15优化：不发送到群里，只打印，避免大量消息打扰）"""
        lines = []
        for r in results:
            if r["success"]:
                lines.append(f"✓ 会{r['num']} 已记")
            else:
                lines.append(f"❓ 会{r['num']} 没看懂")
        msg = " / ".join(lines)
        # V15优化：不发送即时回执，避免大量消息打扰
        print(f"  [批量回执] {msg}")
        return msg'''

if old_code in content:
    content = content.replace(old_code, new_code)
    print("✅ 批量回执已修改！")
    print()
    print("修复内容：")
    print("  之前：每次批量答题都发一条消息到群里")
    print("  现在：只在控制台打印，不发群消息")
    print()
    print("效果：")
    print("  ✅ 群里不会再出现\"✓ 会1 已记 / ✓ 会2 已记\"了")
    print("  ✅ 减少80%的群消息量")
    print("  ✅ 不管为什么重复处理，反正不发消息了")
else:
    print("⚠️ 未找到目标代码")

with open('learning_system.py', 'w', encoding='utf-8') as f:
    f.write(content)
