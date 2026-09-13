import os
base = r'D:\AI-Tools\feishu\V13方案增强'
print(f'基础目录: {base}')
print(f'目录存在: {os.path.exists(base)}')
if os.path.exists(base):
    items = os.listdir(base)
    print(f'目录内容 ({len(items)}项):')
    for item in sorted(items):
        full = os.path.join(base, item)
        is_dir = os.path.isdir(full)
        size = os.path.getsize(full) if not is_dir else '-'
        prefix = '[DIR]' if is_dir else '     '
        print(f'  {prefix} {item} ({size})')
    
    scripts_dir = os.path.join(base, 'scripts')
    print(f'\nscripts目录存在: {os.path.exists(scripts_dir)}')
    if os.path.exists(scripts_dir):
        scripts = os.listdir(scripts_dir)
        print(f'scripts目录内容 ({len(scripts)}项):')
        for s in sorted(scripts):
            full = os.path.join(scripts_dir, s)
            is_dir = os.path.isdir(full)
            size = os.path.getsize(full) if not is_dir else '-'
            prefix = '[DIR]' if is_dir else '     '
            print(f'  {prefix} {s} ({size})')
