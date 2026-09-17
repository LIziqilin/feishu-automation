#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
cost_audit_v13.py - 月度成本审计（AI大系统 cost_audit 深度融合版 V13）
============================================================
系统运行成本审计：统计系统自身运行指标（任务执行、报告推送、心跳、告警）作为成本代理，
评估系统运行开销与异常损耗，生成审计报告推送总控群。

用法：
  python cost_audit_v13.py              # 近 30 天审计
  python cost_audit_v13.py --days 30
  python cost_audit_v13.py --json
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


def cell_text(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return ",".join(str(x) for x in v)
    return str(v)


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


def audit(days=30):
    events = get_all_records(EVENT_LOG_TABLE)
    cutoff = datetime.now() - timedelta(days=days)
    recent = [e for e in events if (to_naive(e.get("timestamp")) or datetime.min) >= cutoff]

    by_type = Counter(cell_text(e.get("log_type")) or "SYSTEM" for e in recent)
    by_sev = Counter(cell_text(e.get("severity")) or "UNKNOWN" for e in recent)
    # 异常损耗：告警/错误事件的运营成本代理
    warn_err = sum(1 for e in recent if cell_text(e.get("severity")) in ("WARN", "ERROR", "CRITICAL"))
    # 日报/周报类推送成本代理（INSTRUCTION 处理量）
    instructions = sum(1 for e in recent if cell_text(e.get("log_type")) == "INSTRUCTION")

    est_cost = {
        "instructions": instructions,
        "alerts": warn_err,
        "estimate_rmb": round(instructions * 0.02 + warn_err * 0.05, 2),  # 代理估算：处理0.02元/条、告警排查0.05元/条
    }

    return {
        "days": days,
        "total_events": len(recent),
        "by_type": dict(by_type),
        "by_severity": dict(by_sev),
        "alert_count": warn_err,
        "alert_rate": round(warn_err / len(recent) * 100, 1) if recent else 0,
        "est_cost": est_cost,
    }


def format_report(a):
    lines = [
        "💰 系统成本审计（近 {} 天）".format(a["days"]),
        "事件总量：{} 条".format(a["total_events"]),
        "— 事件类型分布 —",
        "  ".join("{}:{}".format(k, v) for k, v in sorted(a["by_type"].items(), key=lambda x: -x[1])[:6]),
        "— 告警损耗 —",
        "  告警/错误：{} 条（{:.1f}%）".format(a["alert_count"], a["alert_rate"]),
        "  指令处理：{} 条".format(a["est_cost"]["instructions"]),
        "— 成本估算（代理口径）—",
        "  ≈ {} 元（指令处理{:.2f}元 + 告警排查{:.2f}元）".format(
            a["est_cost"]["estimate_rmb"],
            a["est_cost"]["instructions"] * 0.02,
            a["alert_count"] * 0.05),
    ]
    if a["alert_rate"] > 5:
        lines.append("⚠️ 告警占比偏高，建议检查看门狗/健康检查配置")
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

    a = audit(days)
    if as_json:
        print(json.dumps(a, ensure_ascii=False, default=str))
        return

    report = format_report(a)
    print(report)
    send_ok, _, _ = send_message(report)
    print("\n[OK] 已推送总控群" if send_ok else "\n[!] 群推送失败")


if __name__ == "__main__":
    main()
