#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用dulwich创建提交（索引已通过git rm --cached更新）"""
import os
from dulwich.repo import Repo
from dulwich import porcelain

repo_path = r'D:\AI-Tools\feishu\V13方案增强'
repo = Repo(repo_path)

# 检查当前索引状态
index = repo.open_index()
print(f'索引中文件数: {len(list(index))}')

# 确认.gitignore在索引中
gitignore_in_index = any(name == b'.gitignore' for name in index)
print(f'.gitignore在索引中: {gitignore_in_index}')

# 创建提交
author = 'LIziqilin <liyang307876436@qq.com>'.encode()
message = 'chore: remove 37 test scripts from git tracking (keep local files)'.encode()

try:
    commit_id = porcelain.commit(
        repo,
        message=message,
        author=author,
        committer=author,
    )
    cid = commit_id.decode() if isinstance(commit_id, bytes) else str(commit_id)
    print(f'提交成功: {cid}')
except Exception as e:
    print(f'提交失败: {e}')
    import traceback
    traceback.print_exc()

# 验证提交历史
print()
print('最近3次提交:')
try:
    walker = repo.get_walker(max_entries=3)
    for entry in walker:
        c = entry.commit
        cid = c.id.decode() if isinstance(c.id, bytes) else str(c.id)
        msg = c.message.decode() if isinstance(c.message, bytes) else str(c.message)
        print(f'  {cid[:8]}: {msg[:60]}')
except Exception as e:
    print(f'读取历史失败: {e}')
