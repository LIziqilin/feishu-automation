import re

with open('learning_system.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 找到自然语态销项逻辑的位置，在它之前加洞察指令检查
old = "        # 自然语态销项：\"搞定 xxx\" / \"已完成 xxx\" / \"done xxx\" / \"做完了 xxx\"（V48新增）\n        if not is_task_instruction and not _is_display_cmd:"

new = """        # V49修复：如果是洞察指令，跳过自然语态销项（避免"洞察：...归档"被误判）
        if not is_task_instruction:
            try:
                from task_insight_extension import is_insight_command as _is_insight
                if _is_insight(text) or text.startswith('洞察') or text.startswith('写洞察') or text.startswith('记录洞察'):
                    is_task_instruction = False  # 不是任务指令，是洞察
                    print(f"  [V49] 检测到洞察指令，跳过自然语态销项: {text[:30]}...")
            except Exception:
                pass

        # 自然语态销项："搞定 xxx" / "已完成 xxx" / "done xxx" / "做完了 xxx"（V48新增）
        if not is_task_instruction and not _is_display_cmd:"""

if old in content:
    content = content.replace(old, new, 1)
    with open('learning_system.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK: 已修复洞察指令优先于自然语态销项')
else:
    print('FAIL: 未找到目标代码段')
    # 搜索附近的内容
    for i, line in enumerate(content.split('\n')):
        if '自然语态销项' in line:
            print(f'  line {i+1}: {line}')
