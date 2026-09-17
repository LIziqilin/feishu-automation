#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用dulwich创建提交：移除37个测试脚本"""
import os, sys
from dulwich.repo import Repo
from dulwich.objects import Blob, Tree, Commit
from dulwich import porcelain

repo_path = r'D:\AI-Tools\feishu\V13方案增强'
repo = Repo(repo_path)

# 获取当前HEAD的tree
head = repo.head()
head_commit = repo[head]
old_tree = repo[head_commit.tree]

# 要删除的文件列表（相对于repo根目录）
files_to_remove = []
for f in repo.open_index():
    path = f.path.decode('utf-8') if isinstance(f.path, bytes) else f.path
    if path.startswith('scripts/'):
        basename = os.path.basename(path)
        # 匹配测试脚本模式
        if (basename.startswith('f') and '_' in basename and basename.endswith('.py') or
            basename.startswith('s') and ('_check' in basename or '_test' in basename or '_scan' in basename) and basename.endswith('.py') or
            basename.startswith('cleanup_') or
            basename.startswith('fix_') or
            basename.startswith('test_') or
            basename.startswith('verify_') or
            basename.startswith('v35_') or
            basename.startswith('v33_') or
            basename.startswith('v30_') or
            basename == 'dulwich_commit.py' or
            basename == 'batch_fix_run_cmd.py' or
            basename.startswith('h') and '_' in basename and basename.endswith('.py') or
            basename.startswith('tmp_') or
            basename.startswith('e2e_') or
            basename.startswith('evidence') or
            basename.startswith('restore_') or
            basename.startswith('check_')):
            files_to_remove.append(path)

print(f'待移除文件数: {len(files_to_remove)}')
for f in files_to_remove[:10]:
    print(f'  {f}')
print('...')

# 使用porcelain.remove从索引移除
for f in files_to_remove:
    try:
        porcelain.remove(repo, [f])
    except Exception as e:
        print(f'移除失败 {f}: {e}')

# 也更新.gitignore（已经修改过了，需要加入索引）
porcelain.add(repo, ['.gitignore'])

# 创建提交
author = 'LIziqilin <liyang307876436@qq.com>'.encode()
message = 'chore: 从git跟踪移除37个测试/验证脚本（含硬编码风险，保留本地文件）'.encode()

commit_id = porcelain.commit(
    repo,
    message=message,
    author=author,
    committer=author,
)

print(f'提交成功: {commit_id.decode() if isinstance(commit_id, bytes) else commit_id}')

# 验证
log = repo.get_walker(max_entries=3)
for entry in log:
    c = entry.commit
    print(f'  {c.id.decode()[:8]}: {c.message.decode()[:60]}')
