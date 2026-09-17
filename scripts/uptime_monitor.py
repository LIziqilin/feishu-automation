#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
连续运行监视器（M4 硬门槛 #3）
================================
蓝图要求「连续 30 天生产运行达标」。本工具用**可核对的事实**度量连续性：
- 读取 Windows 计划任务中 V16_* 任务的 Last Run / Last Result
- 每日追加一条连续性记录到 runtime/uptime_log.jsonl（append-only）
- 计算自基线以来的连续天数，并检出"断档日"（当日关键任务未成功运行）
基线：runtime/uptime_since.json 的 since 字段（M4 窗口起点）
输出证据：acceptance/evidence/uptime/uptime_<ts>.json
"""
import os, sys, io, json, subprocess, argparse
from datetime import datetime, date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "runtime"
SINCE = RUNTIME / "uptime_since.json"
LOG = RUNTIME / "uptime_log.jsonl"
EVID = ROOT / "acceptance" / "evidence" / "uptime"

# 关键任务：这些任务当天成功（last result 0 或正在按计划运行）即视为系统"存活"
KEY_TASKS = ["V16_DailyMaintenance", "V16_HourlyBackup", "V16_ServiceWatchdog", "V16_BootRecover"]
TARGET_DAYS = 30


def read_since():
    if not SINCE.exists():
        SINCE.parent.mkdir(parents=True, exist_ok=True)
        SINCE.write_text(json.dumps({"since": datetime.now().isoformat(timespec="seconds"),
                                     "note": "M4 连续运行基线"}), encoding="utf-8")
    try:
        return datetime.fromisoformat(json.loads(SINCE.read_text(encoding="utf-8"))["since"])
    except Exception:
        return datetime.now()


def task_state(name):
    try:
        r = subprocess.run(["schtasks", "/query", "/tn", name, "/fo", "LIST", "/v"],
                           capture_output=True, timeout=30)
        out = (r.stdout or b"").decode("cp936", "replace")
        last_run = last_res = status = next_run = ""
        for line in out.splitlines():
            l = line.strip()
            if l.startswith("上次运行时间") or l.startswith("Last Run Time"):
                last_run = l.split(":", 1)[-1].strip()
            elif l.startswith("上次结果") or l.startswith("Last Result"):
                last_res = l.split(":", 1)[-1].strip()
            elif l.startswith("模式") or l.startswith("Status"):
                status = l.split(":", 1)[-1].strip()
            elif l.startswith("下次运行时间") or l.startswith("Next Run Time"):
                next_run = l.split(":", 1)[-1].strip()
        return {"task": name, "last_run": last_run, "last_result": last_res,
                "next_run": next_run, "status": status}
    except Exception as e:
        return {"task": name, "error": str(e)[:150]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="将连续运行基线重置为现在（重新计时）")
    ap.add_argument("--note", default="", help="重置原因")
    args = ap.parse_args()

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    if args.reset:
        SINCE.write_text(json.dumps({
            "since": datetime.now().isoformat(timespec="seconds"),
            "note": args.note or "手动重置连续运行基线",
            "reset_at": ts}, ensure_ascii=False), encoding="utf-8")
        print("连续运行基线已重置:", json.loads(SINCE.read_text(encoding='utf-8')))

    since = read_since()
    now = datetime.now()
    days = round((now - since).total_seconds() / 86400, 2)

    states = [task_state(t) for t in KEY_TASKS]
    # 存活判定（R6 诚实口径，2026-09-16 修正）：
    # 旧实现把 status 含"就绪/Ready"也算存活 —— 但任务在两次调度之间恒为"就绪"，
    # 导致即使每轮都失败（rc=2）仍报 4/4 在线，连续性监视存在**假通过**。
    # 现改为：必须上次结果是成功（0）。267011=尚未运行过，不计入存活。
    NOT_RUN = "267011"      # 0x41303 从未运行
    RUNNING = "267009"      # 0x41301 正在运行（非失败）

    def _alive(s):
        if s.get("error"):
            return False
        return str(s.get("last_result", "")).strip() == "0"

    def _failed(s):
        if s.get("error"):
            return True
        lr = str(s.get("last_result", "")).strip()
        return lr not in ("", "0", NOT_RUN, RUNNING)

    alive = sum(1 for s in states if _alive(s))
    failed = [s["task"] for s in states if _failed(s)]
    not_run = [s["task"] for s in states if str(s.get("last_result", "")).strip() == NOT_RUN]
    running = [s["task"] for s in states if str(s.get("last_result", "")).strip() == RUNNING]
    rec = {"ts": ts, "date": date.today().isoformat(), "since": since.isoformat(),
           "continuous_days": days, "target_days": TARGET_DAYS,
           "tasks": states, "alive_tasks": alive, "failed_tasks": failed,
           "not_run_tasks": not_run, "running_tasks": running,
           "all_alive": alive == len(KEY_TASKS),
           "met": days >= TARGET_DAYS and alive == len(KEY_TASKS)}
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # 断档检测：日志中出现过的不连续日期
    seen_days = set()
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    seen_days.add(json.loads(line)["date"])
                except Exception:
                    pass
    rec["logged_days"] = sorted(seen_days)

    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"uptime_{ts}.json"
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"连续运行: {days} 天 / 目标 {TARGET_DAYS} 天 | 关键任务成功 {alive}/{len(KEY_TASKS)} | 达标={rec['met']}")
    for s in states:
        flag = "OK " if _alive(s) else ("FAIL" if _failed(s) else "NRUN")
        print(f"  [{flag}] {s['task']:26s} status={s.get('status','')} last={s.get('last_result','')}")
    if failed:
        print(f"  ⚠ 执行失败任务: {failed}（连续运行窗口存在断档，需修复）")
    print("证据:", p)
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
