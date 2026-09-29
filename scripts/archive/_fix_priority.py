with open('learning_system.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 在第791行（0-indexed 790）之前插入洞察指令检查
# 找到 "# D2修复：自然语态销项/归档" 这一行
target_idx = None
for i, line in enumerate(lines):
    if '# D2修复：自然语态销项/归档' in line:
        target_idx = i
        break

if target_idx is None:
    print('FAIL: 未找到目标行')
else:
    # 在目标行之前插入
    insert_lines = [
        '        # V49修复：如果是洞察指令，跳过自然语态销项（避免"洞察：...归档"被误判）\n',
        '        _skip_nl = False\n',
        '        try:\n',
        '            from task_insight_extension import is_insight_command as _is_insight\n',
        '            if _is_insight(text):\n',
        '                _skip_nl = True\n',
        '                print(f"  [V49] 检测到洞察指令，跳过自然语态销项: {text[:30]}...")\n',
        '        except Exception:\n',
        '            pass\n',
    ]
    # 修改原来的if条件
    old_if = lines[target_idx + 1]  # "        if not is_task_instruction and not _is_display_cmd:"
    new_if = old_if.replace('if not is_task_instruction', 'if not _skip_nl and not is_task_instruction')
    
    lines[target_idx + 1] = new_if
    
    # 插入新行
    for j, il in enumerate(insert_lines):
        lines.insert(target_idx + 1 + j, il)
    
    with open('learning_system.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f'OK: 已在第{target_idx+1}行插入洞察指令检查')
    # 验证
    with open('learning_system.py', 'r', encoding='utf-8') as f:
        content = f.read()
    if '_skip_nl' in content:
        print('验证: _skip_nl 已存在')
    else:
        print('验证失败')
