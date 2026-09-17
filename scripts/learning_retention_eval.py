#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学习有效性后测（R-10 闭环）
================================
目的：用学习卡片表的真实快照，量化"学了到底有没有效"——
     毕业率、掌握度分布、复习正确率趋势，作为延迟后测/留存证据，
     替代"凭感觉"的提效宣称。只读，不写生产表。

用法：
    python learning_retention_eval.py            # 拉学习卡片表算后测指标
    python learning_retention_eval.py --dry-run  # 不调飞书，仅演示口径

输出：acceptance/evidence/retention/retention_<ts>.json
"""
import sys, io, os, json, subprocess, argparse
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
EVID = ROOT / "acceptance" / "evidence" / "retention"
sys.path.insert(0, str(SCRIPTS))

try:
    from config_local import LARK_CLI, BASE_TOKEN, CARD_TABLE
except Exception:
    LARK_CLI = os.environ.get("LARK_CLI", "")
    BASE_TOKEN = os.environ.get("FEISHU_BASE_TOKEN", "")
    CARD_TABLE = os.environ.get("CARD_TABLE", "")


def _run(cmd, timeout=60):
    r = subprocess.run(cmd, capture_output=True, timeout=60,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    out = (r.stdout or b"").decode("utf-8", "replace")
    err = (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode == 0, out, err


def list_cards():
    """拉学习卡片表全部记录（只读，bot 身份）。lark-cli 返回 fields(列名)+data(行数组)。"""
    cmd = [LARK_CLI, "base", "+record-list",
           "--base-token", BASE_TOKEN,
           "--table-id", CARD_TABLE,
           "--as", "bot", "--format", "json", "--page-size", "200"]
    ok, out, err = _run(cmd, timeout=90)
    if not ok:
        raise RuntimeError(f"record-list 失败: {err[:200]}")
    data = json.loads(out)
    dd = data.get("data", {})
    names = dd.get("fields", [])
    rows = dd.get("data", [])
    records = []
    for row in rows:
        rec = {names[i]: (row[i] if i < len(row) else None)
               for i in range(len(names))}
        records.append({"fields": rec})
    return records, dd.get("has_more", False)


def _field(rec, *names):
    """按候选字段名容错取值。"""
    fields = rec.get("fields", rec)
    for n in names:
        if n in fields and fields[n] not in (None, ""):
            return fields[n]
    return None


def analyze(items):
    total = len(items)
    status_dist, level_buckets = {}, {}
    levels, corrects = [], []
    passed_reviews, total_reviews = 0, 0
    for rec in items:
        f = rec.get("fields", {})
        st = f.get("卡片状态")
        if isinstance(st, list):
            st = st[0] if st else None
        st = str(st) if st else "未知"
        status_dist[st] = status_dist.get(st, 0) + 1
        lv = f.get("记忆等级")
        if isinstance(lv, (int, float)):
            levels.append(float(lv))
            level_buckets[int(lv)] = level_buckets.get(int(lv), 0) + 1
        cc = f.get("连续正确次数")
        if isinstance(cc, (int, float)):
            corrects.append(float(cc))
        # 复习结果列可能叫“费曼/复习结果”，容错
        rv = f.get("复习结果") or f.get("费曼答题")
        if isinstance(rv, list):
            total_reviews += 1
            if any("通过" in str(x) or "对" in str(x) for x in rv):
                passed_reviews += 1
    mastered = sum(1 for x in levels if x >= 4)
    return {
        "total_cards": total,
        "status_distribution": status_dist,
        "mastery_level_buckets(0-5)": level_buckets,
        "mastery_avg": round(sum(levels)/len(levels), 2) if levels else None,
        "mastery_ge_4": mastered,
        "mastery_rate": round(mastered/total, 3) if total else None,
        "review_pass_rate": round(passed_reviews/total_reviews, 3) if total_reviews else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    EVID.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    result = {"ts": ts, "script": "learning_retention_eval", "dry_run": args.dry_run}

    if args.dry_run:
        result["status"] = "dry_run"
        result["note"] = "演示口径：实跑时拉学习卡片表算毕业率/掌握度/正确率"
    else:
        try:
            items, has_more = list_cards()
            metrics = analyze(items)
            metrics["has_more_beyond_500"] = bool(has_more)
            result.update(metrics)
            result["status"] = "PASS"
            # 后测结论：毕业率<30% 视为学习闭环未达预期
            mr = metrics.get("mastery_rate")
            if mr is not None:
                result["verdict"] = ("掌握率>=40%，学习闭环有效" if mr >= 0.4
                                     else "掌握率<40%，复习/掌握度需加强")
        except Exception as e:
            result["status"] = "FAIL"
            result["error"] = str(e)[:200]

    p = EVID / f"retention_{ts}.json"
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("证据:", p)
    return 0 if result.get("status") in ("PASS", "dry_run") else 3


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
