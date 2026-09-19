#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""彻底修复：把创建任务指令移到扩展指令之前"""

with open('learning_system.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 找到要替换的代码
old_code = '''            continue  # 跳过系统回执，避免循环解析

        # 扩展指令处理（S7随手记/S8快速销项/S9到期提醒）
        if EXTENSION_AVAILABLE:
            handled, result = handle_extension_command(text)
            if handled:
                print(f"  消息: {text[:30]}... → 扩展指令已处理: {result}")
                # V38修复：标记消息为已处理
                mark_message_processed(msg_id, processed_messages, action="extension")
                new_processed_count += 1
                continue

        # 知识链路扩展指令（S10知识检索）
        if KNOWLEDGE_EXTENSION_AVAILABLE:
            handled, result = handle_knowledge_command(text)
            if handled:
                print(f"  消息: {text[:30]}... → 知识检索已处理: {result}")
                # V38修复：标记消息为已处理
                mark_message_processed(msg_id, processed_messages, action="knowledge")
                new_processed_count += 1'''

new_code = '''            continue  # 跳过系统回执，避免循环解析

        # P0修复：先处理基础任务指令（创建/完成/归档），不要被扩展指令吃掉
        task_prefixes = [
            "新建任务：", "新建任务:", "创建任务：", "创建任务:",
            "记录任务：", "记录任务:", "新增任务：", "新增任务:",
            "完成：", "完成:", "归档：", "归档:"
        ]
        is_task_instruction = any(text.startswith(p) for p in task_prefixes)

        # 只有不是基础任务指令时，才走扩展指令处理
        if not is_task_instruction and EXTENSION_AVAILABLE:
            handled, result = handle_extension_command(text)
            if handled:
                print(f"  消息: {text[:30]}... → 扩展指令已处理: {result}")
                # V38修复：标记消息为已处理
                mark_message_processed(msg_id, processed_messages, action="extension")
                new_processed_count += 1
                continue

        # 知识链路扩展指令（S10知识检索）- 同样跳过基础任务指令
        if not is_task_instruction and KNOWLEDGE_EXTENSION_AVAILABLE:
            handled, result = handle_knowledge_command(text)
            if handled:
                print(f"  消息: {text[:30]}... → 知识检索已处理: {result}")
                # V38修复：标记消息为已处理
                mark_message_processed(msg_id, processed_messages, action="knowledge")
                new_processed_count += 1'''

if old_code in content:
    content = content.replace(old_code, new_code)
    print("✅ 代码已修改！")
    print()
    print("修复内容：")
    print("  1. 先判断是不是基础任务指令（创建/完成/归档）")
    print("  2. 如果是，跳过扩展指令处理")
    print("  3. 直接交给parser.parse()处理")
    print()
    print("为什么之前不行？")
    print("  扩展指令handle_extension_command先处理消息")
    print("  它把\"创建任务：xxx\"当成了普通消息")
    print("  然后标记为已处理，不会走到parser.parse()")
    print()
    print("现在修复后：")
    print("  创建/完成/归档指令会优先处理")
    print("  不会被扩展指令吃掉了！")
else:
    print("⚠️ 未找到目标代码")
    # 打印附近的代码看看
    idx = content.find("# 扩展指令处理")
    if idx > 0:
        print("找到扩展指令位置，附近代码：")
        print(content[idx-100:idx+500])

with open('learning_system.py', 'w', encoding='utf-8') as f:
    f.write(content)
