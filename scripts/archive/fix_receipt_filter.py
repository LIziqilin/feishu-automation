#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""根因修复：把批量回执加入系统回执过滤列表，避免死循环"""

with open('learning_system.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 修改系统回执过滤列表
old_patterns = '''        system_receipt_patterns = [
            "❓ 没看懂", "✓ 已记录", "💡 答案", "📅 下次复习",
            "📋 到期提醒", "📇 今日复习", "🔍 知识检索",
            "✅ 洞察已记录", "✅ 任务已完成", "↩️ 已撤销",
            "⚠ 已记录但标记", "🔴 权限失效", "📭 今日无待复习",
            "请发：会/不会/模糊", "未找到相关知识",
        ]'''

new_patterns = '''        system_receipt_patterns = [
            "❓ 没看懂", "✓ 已记录", "💡 答案", "📅 下次复习",
            "📋 到期提醒", "📇 今日复习", "🔍 知识检索",
            "✅ 洞察已记录", "✅ 任务已完成", "↩️ 已撤销",
            "⚠ 已记录但标记", "🔴 权限失效", "📭 今日无待复习",
            "请发：会/不会/模糊", "未找到相关知识",
            # V15根因修复：批量回执也是系统消息，不要当成用户指令
            "✓ 会", "❓ 会",
        ]'''

if old_patterns in content:
    content = content.replace(old_patterns, new_patterns)
    print("✅ 系统回执过滤列表已更新！")
    print()
    print("根因分析：")
    print("  1. 机器人发了\"✓ 会1 已记 / ✓ 会2 已记\"")
    print("  2. 下次poll读到这条自己发的消息")
    print("  3. 过滤列表里没有这个模式，没拦住")
    print("  4. 然后parse把它当成了用户答题指令")
    print("  5. 然后又处理一遍，又发一条回执")
    print("  6. 死循环！越刷越多！")
    print()
    print("修复方案：")
    print("  把\"✓ 会\"和\"❓ 会\"加入系统回执过滤列表")
    print("  以后读到自己发的批量回执，直接跳过，不再处理")
    print()
    print("为什么之前没发现？")
    print("  1. 之前只过滤了单题回执\"✓ 已记录\"")
    print("  2. 忘了过滤批量回执\"✓ 会1 已记\"")
    print("  3. 自己发的消息把自己搞死循环了")
else:
    print("⚠️ 未找到目标代码")

with open('learning_system.py', 'w', encoding='utf-8') as f:
    f.write(content)
