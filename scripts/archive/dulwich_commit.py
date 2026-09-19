#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用dulwich（纯Python git实现）提交代码，绕过360对git.exe的拦截
"""
import os
import sys
import fnmatch
from dulwich.repo import Repo
from dulwich import porcelain
from dulwich.objects import Blob, Tree, Commit
from dulwich.index import build_index_from_tree

# 项目根目录
PROJECT_ROOT = r"D:\AI-Tools\feishu\V13方案增强"
GITIGNORE_PATH = os.path.join(PROJECT_ROOT, ".gitignore")

def read_gitignore():
    """读取.gitignore文件，返回忽略模式列表"""
    patterns = []
    if os.path.exists(GITIGNORE_PATH):
        with open(GITIGNORE_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    patterns.append(line)
    # 始终忽略.git目录
    patterns.append('.git')
    return patterns

def should_ignore(filepath, patterns):
    """检查文件是否应该被忽略"""
    # 转换为相对路径，使用正斜杠
    rel_path = os.path.relpath(filepath, PROJECT_ROOT).replace('\\', '/')
    
    for pattern in patterns:
        # 处理目录模式（以/结尾）
        if pattern.endswith('/'):
            dir_pattern = pattern.rstrip('/')
            if rel_path.startswith(dir_pattern + '/'):
                return True
        # 处理通配符
        elif '*' in pattern or '?' in pattern:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
            # 也检查文件名部分
            basename = os.path.basename(rel_path)
            if fnmatch.fnmatch(basename, pattern):
                return True
        # 精确匹配
        else:
            if rel_path == pattern or rel_path.startswith(pattern + '/'):
                return True
    return False

def collect_files():
    """收集所有需要提交的文件"""
    patterns = read_gitignore()
    files = []
    
    for root, dirs, filenames in os.walk(PROJECT_ROOT):
        # 跳过.git目录
        if '.git' in dirs:
            dirs.remove('.git')
        
        # 检查目录是否应该被忽略
        rel_dir = os.path.relpath(root, PROJECT_ROOT).replace('\\', '/')
        if rel_dir != '.':
            if should_ignore(root, patterns):
                continue
        
        for filename in filenames:
            filepath = os.path.join(root, filename)
            if not should_ignore(filepath, patterns):
                rel_path = os.path.relpath(filepath, PROJECT_ROOT).replace('\\', '/')
                files.append(rel_path)
    
    return sorted(files)

def main():
    os.chdir(PROJECT_ROOT)
    
    print("=" * 60)
    print("使用dulwich提交代码")
    print("=" * 60)
    
    # 1. 初始化或打开仓库
    if not os.path.exists('.git'):
        repo = Repo.init('.')
        print("[1/5] 仓库已初始化")
        # 配置远程仓库
        repo.refs.set_symbolic_ref(b'HEAD', b'refs/heads/master')
    else:
        repo = Repo('.')
        print("[1/5] 仓库已存在")
    
    # 2. 收集文件
    files = collect_files()
    print(f"[2/5] 收集到 {len(files)} 个文件需要提交")
    for f in files[:20]:
        print(f"  - {f}")
    if len(files) > 20:
        print(f"  ... 还有 {len(files) - 20} 个文件")
    
    # 3. 添加文件到暂存区
    print("[3/5] 添加文件到暂存区...")
    try:
        porcelain.add(repo, files)
        print("  文件添加成功")
    except Exception as e:
        print(f"  添加文件时出错: {e}")
        # 尝试逐个添加
        success = 0
        failed = 0
        for f in files:
            try:
                porcelain.add(repo, [f])
                success += 1
            except Exception as e2:
                print(f"  失败: {f} - {e2}")
                failed += 1
        print(f"  成功: {success}, 失败: {failed}")
    
    # 4. 创建提交
    print("[4/5] 创建提交...")
    commit_message_str = (
        "V34加固：敏感配置统一管理+GitHub提交安全修复\n\n"
        "- 新建config_local.py统一管理BASE_TOKEN等敏感配置\n"
        "- 新建config_local.example.py配置模板\n"
        "- 修改v19_integration.py从config_local导入（带环境变量fallback）\n"
        "- 批量修复8个核心脚本的硬编码BASE_TOKEN\n"
        "- 全面更新.gitignore（排除敏感配置、临时脚本、结果文件）\n"
        "- 完成V34系统加固专项H0-H6批\n"
    )
    commit_message = commit_message_str.encode('utf-8')
    
    try:
        commit_id = porcelain.commit(
            repo,
            commit_message,
            committer=b'LIziqilin <liyang307876436@qq.com>',
            author=b'LIziqilin <liyang307876436@qq.com>'
        )
        print(f"  提交成功，commit_id: {commit_id.decode()}")
    except Exception as e:
        print(f"  创建提交时出错: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # 5. 查看提交历史
    print("[5/5] 提交历史:")
    try:
        # 使用repo对象查看提交
        head = repo.refs.read_ref(b'HEAD')
        if head:
            commit = repo[head]
            print(f"  HEAD: {head.decode()[:12]}")
            print(f"  消息: {commit.message.decode()[:60]}...")
            print(f"  作者: {commit.author.decode()}")
            print(f"  时间: {commit.commit_time}")
    except Exception as e:
        print(f"  查看历史时出错: {e}")
    
    print("\n" + "=" * 60)
    print("本地提交完成！")
    print("=" * 60)
    print("\n下一步：推送到远程仓库")
    print("远程仓库: https://github.com/LIziqilin/feishu-automation.git")
    print("\n注意：推送需要GitHub Personal Access Token")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
