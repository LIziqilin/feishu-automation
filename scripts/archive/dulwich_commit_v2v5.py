#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用dulwich创建提交：移除v2-v5测试脚本"""
from dulwich.repo import Repo
from dulwich import porcelain

repo_path = r'D:\AI-Tools\feishu\V13方案增强'
repo = Repo(repo_path)

# 添加.gitignore变更
porcelain.add(repo, ['.gitignore'])

# 创建提交
author = 'LIziqilin <liyang307876436@qq.com>'.encode()
message = 'chore: remove 12 v2-v5 test scripts from git tracking'.encode()

commit_id = porcelain.commit(
    repo,
    message=message,
    author=author,
    committer=author,
)
cid = commit_id.decode() if isinstance(commit_id, bytes) else str(commit_id)
print(f'提交成功: {cid}')

# 验证提交历史
print()
print('最近3次提交:')
walker = repo.get_walker(max_entries=3)
for entry in walker:
    c = entry.commit
    cid = c.id.decode() if isinstance(c.id, bytes) else str(c.id)
    msg = c.message.decode() if isinstance(c.message, bytes) else str(c.message)
    print(f'  {cid[:8]}: {msg[:60]}')
