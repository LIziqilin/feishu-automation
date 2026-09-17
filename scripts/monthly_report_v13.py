#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
monthly_report_v13.py - 月度总结报告（AI大系统 monthly_report 深度融合版 V13）
============================================================
汇总本月：任务完成、学习答题、洞察沉淀、系统健康，生成月报并推送总控群。

用法：
  python monthly_report_v13.py                # 本月报告
  python monthly_report_v13.py --days 30      # 近 30 天
  python monthly_report_v13.py --json
"""
import sys
import os
import json
import subprocess
from datetime import datetime, timedelta
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from v19_integration import (
    BASE_TOKEN, FLOW_TABLE, TASK_TABLE, EVENT_LOG_TABLE,
    INSIGHT_TABLE, TARGET_CHAT_ID,
)


def run_cmd(cmd, timeout=90):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, shell=False)
        out = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        err = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return r.returncode == 0, out, err
    except Exception as e:
        return False, "", str(e)


def send_message(text):
    cmd = ["lark-cli", "im", "+messages-send",
           "--chat-id", TARGET_CHAT_ID, "--as", "user", "--text", text]
    return run_cmd(cmd)


def get_all_records(table_id):
    result = []
    offset = 0
    while True:
        cmd = ["lark-cli", "base", "+record-list", "--base-token", BASE_TOKEN,
               "--table-id", table_id, "--as", "user",
               "--limit", "200", "--offset", str(offset), "--format", "json"]
        ok, stdout, stderr = run_cmd(cmd)
        if not ok:
            break
        try:
            data = json.loads(stdout).get("data", {})
        except Exception:
            break
        records = data.get("data", [])
        record_ids = data.get("record_id_list", [])
        fields = data.get("fields", [])
        for i, rec in enumerate(records):
            if isinstance(rec, list):
                d = {"_record_id": record_ids[i] if i < len(record_ids) else ""}
                for j, f in enumerate(fields):
                    if j < len(rec):
                        d[f] = rec[j]
                result.append(d)
        offset += len(records)
        if not data.get("has_more", False) or not records:
            break
    return result


def to_naive(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        ts = v / 1000.0 if v > 1e11 else v
        return datetime.fromtimestamp(ts)
    if isinstance(v, str):
        try:
            d = datetime.fromisoformat(v)
            return d.replace(tzinfo=None) if d.tzinfo else d
        except Exception:
            return None
    return None


def cell_text(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return ",".join(str(x) for x in v)
    return str(v)


def analyze(days=30):
    cutoff = datetime.now() - timedelta(days=days)

    # 学习流水
    flows = get_all_records(FLOW_TABLE)
    flow_recent = [f for f in flows if (to_naive(f.get("客户端时间戳")) or datetime.min) >= cutoff]
    correct = sum(1 for f in flow_recent if "会" in cell_text(f.get("结果")))
    acc = correct / len(flow_recent) * 100 if flow_recent else 0

    # 任务
    tasks = get_all_records(TASK_TABLE)
    task_recent = [t for t in tasks if (to_naive(t.get("创建日期") or t.get("开始日期")) or datetime.min) >= cutoff]
    done = sum(1 for t in task_recent if cell_text(t.get("状态")) in ("已完成", "完成"))
    pending = sum(1 for t in task_recent if cell_text(t.get("状态")) in ("待办", "进行中", "待开始"))
    overdue = sum(1 for t in task_recent if cell_text(t.get("状态")) == "已逾期")

    # 洞察
    insights = get_all_records(INSIGHT_TABLE)
    insight_recent = len([x for x in insights if (to_naive(x.get("创建时间") or x.get("created_at")) or datetime.min) >= cutoff])

    # 系统健康：近 7 天告警
    events = get_all_records(EVENT_LOG_TABLE)
    week_cut = datetime.now() - timedelta(days=7)
    ev_week = [e for e in events if (to_naive(e.get("timestamp")) or datetime.min) >= week_cut]
    alerts = sum(1 for e in ev_week if cell_text(e.get("severity")) in ("WARN", "ERROR", "CRITICAL"))

    return {
        "days": days,
        "flows": len(flow_recent),
        "accuracy": round(acc, 1),
        "tasks_total": len(task_recent),
        "tasks_done": done,
        "tasks_pending": pending,
        "tasks_overdue": overdue,
        "insights": insight_recent,
        "alerts_7d": alerts,
    }


def format_report(a):
    lines = [
        "📅 月度总结报告（近 {} 天）".format(a["days"]),
        "📚 学习：答题 {} 次 ｜ 正确率 {:.1f}%".format(a["flows"], a["accuracy"]),
        "📋 任务：新增 {} ｜ 完成 {} ｜ 进行中/待办 {} ｜ 逾期 {}".format(
            a["tasks_total"], a["tasks_done"], a["tasks_pending"], a["tasks_overdue"]),
        "💡 洞察：新增 {} 条".format(a["insights"]),
        "🖥️ 系统：近 7 天告警 {} 条".format(a["alerts_7d"]),
    ]
    if a["alerts_7d"] > 3:
        lines.append("⚠️ 系统告警偏多，建议运行系统体检排查")
    if a["tasks_pending"] > a["tasks_done"]:
        lines.append("💪 待办多于完成，建议聚焦高优任务")
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    days = 30
    as_json = False
    if "--days" in args:
        try:
            days = int(args[args.index("--days") + 1])
        except Exception:
            pass
    if "--json" in args:
        as_json = True

    a = analyze(days)
    if as_json:
        print(json.dumps(a, ensure_ascii=False, default=str))
        return

    report = format_report(a)
    print(report)
    send_ok, _, _ = send_message(report)
    print("\n[OK] 已推送总控群" if send_ok else "\n[!] 群推送失败")


if __name__ == "__main__":
    main()
