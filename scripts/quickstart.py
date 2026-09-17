#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
一键体检 + 快捷入口（提升"使用便捷性"）
=====================================
用法：
  python quickstart.py            # 一键体检（服务/备份/密钥/评估 一屏汇总）
  python quickstart.py --how      # 显示常用操作卡片（按钮路径级）
只读：不写生产表，不发送消息。
"""
import sys, io, os, json, glob, socket, argparse
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

HOW = """\
【常用操作 · 按钮路径级】
1) 建任务      → 飞书群发「建任务：<内容> 截止<日期> 优先级<高/中/低>」
2) 销项        → 发「搞定 <任务名>」或「完成 <任务名>」
3) 记一笔灵感  → 发「记一下：<内容>」（晚 21:30 汇总入洞察表）
4) 查知识      → 直接提问，答不了会明确说「无来源」
5) 复习闪卡    → 早 8:15 自动推；回复 0/1/2/3 打分
6) 三报        → 早8:00晨报 / 午12:00午报 / 晚18:00复盘（自动）
7) 健康体检    → python scripts/quickstart.py
8) 恢复演练    → python scripts/restore_drill.py（只写隔离库）
9) 回滚代码    → python scripts/rollback.py --list 然后 --plan <rev>
"""

def port_open(host, port, timeout=0.6):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

def check():
    rows = []
    for name, host, port in [("Ollama", "127.0.0.1", 11434),
                             ("AnythingLLM", "127.0.0.1", 3001),
                             ("ObsidianREST", "127.0.0.1", 27124)]:
        rows.append((name, "UP" if port_open(host, port) else "DOWN"))
    bk = sorted(glob.glob(str(ROOT / "backups" / "backup_*.json")), reverse=True)
    latest_age_h = None
    if bk:
        age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(bk[0]))).total_seconds()
        latest_age_h = round(age / 3600, 1)
    rows.append(("备份文件数", str(len(bk))))
    rows.append(("最新备份(小时前)", str(latest_age_h)))
    # 密钥硬编码扫描
    import re
    leak = 0
    for p in SCRIPTS.glob("*.py"):
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
            leak += len(re.findall(r"sk-[A-Za-z0-9]{20,}", t))
        except Exception:
            pass
    rows.append(("明文密钥命中", str(leak)))
    # 最近评测
    ev = sorted(glob.glob(str(ROOT / "acceptance" / "evidence" / "eval" / "*" / "report.json")))
    if ev:
        r = json.load(open(ev[-1], encoding="utf-8"))
        rows.append(("最新评测通过率", f"{r.get('overall_pass_rate', '?')}"))
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--how", action="store_true")
    a = ap.parse_args()
    if a.how:
        print(HOW); return 0
    print("=" * 40)
    print(" 紫麒麟智能助理 · 一键体检", datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 40)
    issues = []
    for k, v in check():
        flag = ""
        if k == "明文密钥命中" and v != "0":
            flag = "  ⚠需处理"; issues.append(k)
        if k.startswith("最新备份") and v not in ("None",) and float(v or 0) > 26:
            flag = "  ⚠偏旧"
        print(f"  {k:18} {v}{flag}")
    print("-" * 40)
    print("  用法: --how 查看常用操作卡片")
    print("=" * 40)
    return 0

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
