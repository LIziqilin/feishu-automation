#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""obsidian_reverse_archive.py — D5 反向归档（飞书"已完成" -> Obsidian 移动目录）

背景：sync_tasks.js 已能把完成态写入 待办任务/已完成/，但它只在 Obsidian 内触发。
本脚本提供 headless 反向归档：读取飞书任务总表终态（已完成/已取消/已归档），
把 Obsidian 里对应仍留在 待办/ 或 进行中/ 的 md 移动到 已完成/ 目录。
只移动不删除（R3/R4）；默认 dry-run，--apply 才实际移动。
"""
import os, sys, re, shutil, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v15_features as v15

T_TASK = "tblz3H4lV7PCrBrX"
VAULT = r"D:\AI\finished Brain"
TASK_ROOT = os.path.join(VAULT, "待办任务")
DONE_DIR = os.path.join(TASK_ROOT, "已完成")
TERMINAL = ("已完成", "已取消", "已归档", "完成", "done", "archive")
_ACTIVE_DIRS = ("待办", "进行中")


def norm(s):
    s = str(s).lower().replace(".md", "")
    s = re.sub(r"^[中低高]_", "", s)
    s = re.sub(r"[【】\[\]（）()]", "", s)
    # 2026-09-17 修复：飞书用 "/" 分隔（规范图集/创优PPT），Obsidian 文件名用 "_"（Windows 不允许 /），
    # 统一归一化，避免同一任务因分隔符不同被判为不同键而同步失败
    s = s.replace("/", "_")
    return re.sub(r"\s+", "", s)


def feishu_terminal():
    """返回 飞书已终态任务 的规范化键集合"""
    out = set()
    for it in v15.list_records(T_TASK, max_pages=80):
        f = it.get("fields", {})
        title = v15.cell_text(f.get("任务名称") or f.get("标题") or f.get("名称") or "")
        status = f.get("状态", "")
        if isinstance(status, list):
            status = status[0].get("text", "") if status else ""
        if status in TERMINAL:
            out.add(norm(title))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="实际移动（默认dry-run）")
    args = ap.parse_args()

    terminal = feishu_terminal()
    print(f"飞书终态任务键: {len(terminal)}")
    if not os.path.exists(TASK_ROOT):
        print("待办任务目录不存在"); return
    if not os.path.exists(DONE_DIR):
        if args.apply:
            os.makedirs(DONE_DIR, exist_ok=True)
        else:
            print(f"[dry-run] 将创建 {DONE_DIR}")

    moved, skipped = 0, 0
    for d in _ACTIVE_DIRS:
        adir = os.path.join(TASK_ROOT, d)
        if not os.path.isdir(adir):
            continue
        for fn in os.listdir(adir):
            if not fn.endswith(".md"):
                continue
            if norm(fn) in terminal:
                src = os.path.join(adir, fn)
                dst = os.path.join(DONE_DIR, fn)
                if args.apply:
                    shutil.move(src, dst)
                    moved += 1
                    print(f"  移动: {d}/{fn} -> 已完成/")
                else:
                    moved += 1
                    print(f"  [dry-run] {d}/{fn} -> 已完成/")
            else:
                skipped += 1
    print(f"\n{'已移动' if args.apply else '待移动(dry-run)'} {moved} 个；保持活跃 {skipped} 个")
    if not args.apply:
        print("（未改动任何文件；加 --apply 实际执行）")


if __name__ == "__main__":
    main()
