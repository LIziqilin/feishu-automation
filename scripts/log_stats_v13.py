#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
log_stats_v13.py - 运行日志统计分析（AI大系统 analyze_run_logs 深度融合版 V13）
============================================================
统计系统运行健康度：读取系统事件日志表，按 severity/log_type/source 聚合，
输出近 7 天 / 近 30 天异常分布 TOP、成功率趋势，推送到总控群并写审计日志。

用法：
  python log_stats_v13.py                 # 近 7 天统计
  python log_stats_v13.py --days 30       # 近 30 天统计
  python log_stats_v13.py --json          # 仅输出 JSON（供其他模块调用）
"""
import sys
import os
import json
import subprocess
from datetime import datetime, timedelta
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from v19_integration import BASE_TOKEN, EVENT_LOG_TABLE, TARGET_CHAT_ID


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


def get_all_events():
    """分页读取事件日志表全部记录"""
    result = []
    offset = 0
    while True:
        cmd = ["lark-cli", "base", "+record-list", "--base-token", BASE_TOKEN,
               "--table-id", EVENT_LOG_TABLE, "--as", "user",
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


def cell_text(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return ",".join(str(x) for x in v)
    return str(v)


def to_naive(v):
    """datetime 值归一化为 naive 本地 datetime"""
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


def analyze(days=7):
    events = get_all_events()
    cutoff = datetime.now() - timedelta(days=days)
    recent = []
    for e in events:
        ts = to_naive(e.get("timestamp") or e.get("客户端时间戳"))
        if ts and ts >= cutoff:
            recent.append(e)

    sev = Counter(cell_text(e.get("severity")) or "UNKNOWN" for e in recent)
    ltype = Counter(cell_text(e.get("log_type")) or "SYSTEM" for e in recent)
    src = Counter(cell_text(e.get("source")) or "system" for e in recent)

    # 异常消息 TOP10
    abnormal = [e for e in recent if cell_text(e.get("severity")) in ("ERROR", "CRITICAL", "WARN")]
    top_msg = Counter((e.get("message") or "")[:60] for e in abnormal).most_common(10)

    total = len(recent)
    abnormal_count = sum(sev.get(k, 0) for k in ("ERROR", "CRITICAL"))
    rate = abnormal_count / total * 100 if total else 0

    return {
        "days": days,
        "total": total,
        "severity": dict(sev),
        "log_type": dict(ltype),
        "source_top": src.most_common(5),
        "abnormal_count": abnormal_count,
        "abnormal_rate": round(rate, 1),
        "top_abnormal": [(m, c) for m, c in top_msg],
    }


def format_report(a):
    lines = [
        "📊 系统运行日志统计（近 {} 天）".format(a["days"]),
        "事件总数：{} 条 ｜ 异常(ERROR/CRITICAL)：{} 条（{:.1f}%）".format(
            a["total"], a["abnormal_count"], a["abnormal_rate"]),
        "— 严重度分布 —",
        "  ".join("{}:{}".format(k, v) for k, v in sorted(a["severity"].items(), key=lambda x: -x[1])),
        "— 日志类型 TOP —",
        "  ".join("{}:{}".format(k, v) for k, v in sorted(a["log_type"].items(), key=lambda x: -x[1])[:5]),
        "— 来源 TOP5 —",
        "  ".join("{}:{}".format(k, v) for k, v in a["source_top"]),
    ]
    if a["top_abnormal"]:
        lines.append("— 异常消息 TOP10 —")
        for m, c in a["top_abnormal"][:10]:
            lines.append("  {}（×{}）".format(m, c))
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    days = 7
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
