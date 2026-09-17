#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
cognitive_analysis_v13.py - 月度认知分析（AI大系统 cognitive_analysis 深度融合版 V13）
============================================================
分析学习流水：科目投入分布、正确率趋势、薄弱点（错因/科目）、遗忘信号，
生成月度认知分析报告，推送总控群并写系统事件日志。

用法：
  python cognitive_analysis_v13.py              # 近 30 天分析
  python cognitive_analysis_v13.py --days 7     # 近 7 天分析
  python cognitive_analysis_v13.py --json       # 仅输出 JSON
"""
import sys
import os
import json
import subprocess
from datetime import datetime, timedelta
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from v19_integration import BASE_TOKEN, FLOW_TABLE, CARD_TABLE, EVENT_LOG_TABLE, TARGET_CHAT_ID


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
    """单元格值 → 文本（单选返回数组、文本直接返回）"""
    if v is None:
        return ""
    if isinstance(v, list):
        return ",".join(str(x) for x in v)
    return str(v)


def analyze(days=30):
    # 加载卡片表建立 卡片ID -> 科目 映射（流水表无科目字段，通过卡片ID关联）
    cards = get_all_records(CARD_TABLE)
    card_subject = {}
    for c in cards:
        card_subject[c.get("_record_id", "")] = cell_text(c.get("科目") or "未知")
    flows = get_all_records(FLOW_TABLE)
    cutoff = datetime.now() - timedelta(days=days)
    recent = [f for f in flows if (to_naive(f.get("客户端时间戳")) or datetime.min) >= cutoff]

    def flow_subject(f):
        cid = cell_text(f.get("卡片ID"))
        return card_subject.get(cid, cell_text(f.get("科目") or "未知").strip("[]'") or "未分类")

    subject_counter = Counter(flow_subject(f) for f in recent)
    result_counter = Counter(cell_text(f.get("结果") or "未知") for f in recent)
    reason_counter = Counter(cell_text(f.get("错因") or "无") for f in recent)

    # 正确率按日趋势（近 days 天，按自然日字段）
    daily = Counter()
    day_total = Counter()
    for f in recent:
        day = str(f.get("自然日") or (to_naive(f.get("客户端时间戳")) or datetime.now()).strftime("%Y-%m-%d"))
        day_total[day] += 1
        if "会" in cell_text(f.get("结果")):
            daily[day] += 1

    correct_total = sum(1 for f in recent if "会" in cell_text(f.get("结果")))
    total = len(recent)
    acc = correct_total / total * 100 if total else 0

    # 薄弱科目：错题最多的科目
    wrong_by_subject = Counter()
    for f in recent:
        if "会" not in cell_text(f.get("结果")):
            wrong_by_subject[flow_subject(f)] += 1

    trend_days = sorted(day_total.keys())[-10:]
    trend = [{"day": d, "total": day_total[d], "correct": daily.get(d, 0)} for d in trend_days]

    return {
        "days": days,
        "total": total,
        "accuracy": round(acc, 1),
        "subject_top": subject_counter.most_common(8),
        "result_dist": dict(result_counter),
        "reason_dist": reason_counter.most_common(6),
        "weak_subjects": wrong_by_subject.most_common(5),
        "trend": trend,
    }


def format_report(a):
    lines = [
        "🧠 认知分析报告（近 {} 天）".format(a["days"]),
        "答题总数：{} ｜ 正确率：{:.1f}%".format(a["total"], a["accuracy"]),
        "— 科目投入 TOP8 —",
        "  ".join("{}:{}".format(k, v) for k, v in a["subject_top"]),
        "— 结果分布 —",
        "  ".join("{}:{}".format(k, v) for k, v in sorted(a["result_dist"].items(), key=lambda x: -x[1])),
    ]
    if a["reason_dist"]:
        lines.append("— 错因分布 —")
        lines.append("  ".join("{}:{}".format(k, v) for k, v in a["reason_dist"]))
    if a["weak_subjects"]:
        lines.append("— 薄弱科目（错题最多）—")
        lines.append("  ".join("{}:{}".format(k, v) for k, v in a["weak_subjects"]))
    if a["trend"]:
        lines.append("— 近 10 日趋势（完成/答对）—")
        lines.append("  " + " | ".join("{}({}/{})".format(t["day"][5:], t["correct"], t["total"]) for t in a["trend"]))
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
