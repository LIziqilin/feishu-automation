#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""飞书任务总表 <-> Obsidian 待办任务 双向对账（只读，不改写）
定位真实差异：飞书有但Obsidian缺 / Obsidian有但飞书缺 / 状态不一致。
匹配键：飞书记录标题 vs Obsidian 文件名（去"中_/低_/【】"前缀与.md）。
"""
import os, sys, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v15_features as v15

T_TASK = "tblz3H4lV7PCrBrX"
VAULT = r"D:\AI\finished Brain"
TASK_ROOT = os.path.join(VAULT, "待办任务")
DONE_MARK = ("完成", "已完成", "归档", "done", "archive")

def norm(s):
    s = s.lower().replace(".md", "")
    s = re.sub(r"^[中低高]_", "", s)
    s = re.sub(r"[【】\[\]（）()]", "", s)
    return re.sub(r"\s+", "", s)

def feishu_tasks():
    # D5修复：只收活跃状态（待办/进行中/空），与 Obsidian 活跃口径对齐；
    # 终态（已完成/已取消/已归档）不入集合，避免把已归档项误报为“飞书有/Obsidian缺”。
    items = v15.list_records(T_TASK, max_pages=80)
    out = {}
    for it in items:
        f = it.get("fields", {})
        title = v15.cell_text(f.get("任务名称") or f.get("标题") or f.get("名称") or "")
        status = f.get("状态", "")
        if isinstance(status, list):
            status = status[0].get("text", "") if status else ""
        if any(m in str(status).lower() for m in DONE_MARK):
            continue
        out[norm(title)] = {"title": title, "status": status, "rid": it.get("record_id")}
    return out

def obsidian_tasks():
    out = {}
    if not os.path.exists(TASK_ROOT):
        return out
    for root, dirs, files in os.walk(TASK_ROOT):
        # D5修复：完成态优先看目录名（Obsidian 将已完成放入 待办任务/已完成/）
        rel = os.path.relpath(root, TASK_ROOT)
        if any(m in rel for m in DONE_MARK):
            continue
        for fn in files:
            if not fn.endswith(".md"):
                continue
            low = fn.lower()
            if any(m in low for m in DONE_MARK):
                continue
            out[norm(fn)] = {"file": fn, "dir": os.path.relpath(root, VAULT)}
    return out

def main():
    print("=== 飞书<->Obsidian 双向对账 ===")
    fs = feishu_tasks()
    ob = obsidian_tasks()
    print(f"飞书活跃任务(去重键): {len(fs)}   Obsidian活跃md(去重键): {len(ob)}")
    only_fs = [fs[k]["title"] for k in fs if k not in ob]
    only_ob = [ob[k]["file"] for k in ob if k not in fs]
    print(f"\n[飞书有 / Obsidian缺] {len(only_fs)} 条:")
    for t in only_fs:
        print("  -", t)
    print(f"\n[Obsidian有 / 飞书缺] {len(only_ob)} 条:")
    for t in only_ob:
        print("  -", t)
    # 状态不一致（同键但飞书非活跃）
    mismatch = []
    for k in fs:
        if k in ob and fs[k]["status"] not in ("待办", "进行中", "", None):
            mismatch.append((fs[k]["title"], fs[k]["status"]))
    print(f"\n[状态不一致] {len(mismatch)} 条:")
    for t, s in mismatch:
        print(f"  - {t} -> 飞书状态={s}")
    print("\n对账完成（只读，未改动任何数据）")

if __name__ == "__main__":
    main()
