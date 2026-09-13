#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量修复所有Python脚本的run_cmd函数编码问题
- 添加shell=True
- 移除text=True，手动UTF-8解码
- 超时从30s增至60s
- 支持列表形式命令自动加引号
"""

import os
import re
import glob

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

# 新的run_cmd函数模板
NEW_RUN_CMD = '''def run_cmd(cmd, timeout=60):
    """执行命令并返回结果"""
    try:
        # 如果是列表，转换为带引号的字符串
        if isinstance(cmd, list):
            cmd_str = " ".join(f'"{c}"' if (" " in c or "\\\\" in c) else c for c in cmd)
        else:
            cmd_str = cmd
        r = subprocess.run(cmd_str, capture_output=True, timeout=timeout, shell=True)
        stdout = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        stderr = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return r.returncode == 0, stdout, stderr
    except Exception as e:
        return False, "", str(e)'''

def fix_run_cmd_in_file(filepath):
    """修复单个文件中的run_cmd函数"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return False, f"读取失败: {e}"

    # 检查是否包含run_cmd函数
    if "def run_cmd" not in content:
        return False, "无run_cmd函数"

    # 检查是否已经是修复后的格式（包含shell=True和utf-8解码）
    if "shell=True" in content and 'decode("utf-8"' in content:
        return False, "已是修复后格式"

    # 使用正则匹配run_cmd函数（从def run_cmd到下一个def或文件末尾）
    pattern = r'def run_cmd\(.*?\n(?:.*?\n)*?(?=\ndef |\nclass |\Z)'
    match = re.search(pattern, content)
    if not match:
        return False, "无法匹配run_cmd函数"

    old_func = match.group(0)
    new_content = content[:match.start()] + NEW_RUN_CMD + "\n" + content[match.end():]

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True, "修复成功"
    except Exception as e:
        return False, f"写入失败: {e}"

def main():
    print("="*60)
    print("批量修复Python脚本run_cmd函数编码问题")
    print(f"脚本目录: {SCRIPTS_DIR}")
    print("="*60)

    # 获取所有Python文件
    py_files = glob.glob(os.path.join(SCRIPTS_DIR, "*.py"))
    print(f"\n找到 {len(py_files)} 个Python文件")

    # 排除已经修复的核心脚本和包装脚本
    exclude_files = [
        "learning_system.py",
        "review_derive.py",
        "backup_with_rotation.py",
        "final_health_check.py",
        "task_insight_extension.py",
        "knowledge_extension.py",
        "phase5_daily_check.py",
        "run_poll_wrapper.py",
        "run_morning_wrapper.py",
        "run_maintenance_wrapper.py",
        "batch_fix_run_cmd.py",  # 本脚本
    ]

    fixed_count = 0
    skipped_count = 0
    failed_count = 0

    for filepath in sorted(py_files):
        filename = os.path.basename(filepath)

        if filename in exclude_files:
            print(f"\n⏭️  {filename}: 跳过（核心脚本已修复或包装脚本）")
            skipped_count += 1
            continue

        success, message = fix_run_cmd_in_file(filepath)
        if success:
            print(f"\n✅ {filename}: {message}")
            fixed_count += 1
        else:
            if "无run_cmd函数" in message or "已是修复后格式" in message:
                print(f"\n⏭️  {filename}: {message}")
                skipped_count += 1
            else:
                print(f"\n❌ {filename}: {message}")
                failed_count += 1

    print("\n" + "="*60)
    print("修复完成汇总")
    print("="*60)
    print(f"  修复成功: {fixed_count}")
    print(f"  跳过: {skipped_count}")
    print(f"  失败: {failed_count}")
    print(f"  总计: {len(py_files)}")

    return 0 if failed_count == 0 else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
