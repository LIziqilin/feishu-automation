#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
效率提升度量（M3）— 人工基线 vs 辅助 vs 全自动
============================================
方法：对同类任务记录三组耗时/错误率；无实测数据时输出"测量框架+待填模板"。
不伪造数据：未测则标 pending，不参与提分。
产出 acceptance/evidence/efficiency/baseline_<ts>.json
"""
import sys, io, json, argparse
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVID = ROOT / "acceptance" / "evidence" / "efficiency"
DATA = ROOT / "acceptance" / "efficiency_data.json"   # 人工录入实测

TASK_TYPES = ["建任务", "销项", "纪要整理", "三报生成", "知识问答", "卡片复习"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", action="store_true", help="输出待填模板")
    args = ap.parse_args()

    measured = {}
    if DATA.exists():
        try:
            measured = json.loads(DATA.read_text(encoding="utf-8"))
        except Exception:
            measured = {}

    rows = []
    for t in TASK_TYPES:
        m = measured.get(t, {})
        manual = m.get("manual_min")
        assisted = m.get("assisted_min")
        auto = m.get("auto_min")
        speedup = None
        if manual and auto:
            speedup = round(manual / auto, 2)
        elif manual and assisted:
            speedup = round(manual / assisted, 2)
        rows.append({
            "task": t, "manual_min": manual, "assisted_min": assisted, "auto_min": auto,
            "speedup_x": speedup,
            "error_rate": m.get("error_rate"),
            "status": "measured" if speedup else "pending",
        })

    done = [r for r in rows if r["status"] == "measured"]
    avg = round(sum(r["speedup_x"] for r in done) / len(done), 2) if done else None
    report = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "method": "同任务三组对照（纯人工/助理辅助/全自动），记录耗时与错误率",
        "sample_size_target": "每任务类型≥10次",
        "avg_speedup_x": avg,
        "measured_count": len(done),
        "pending_count": len(rows) - len(done),
        "rows": rows,
        "note": ("尚无实测数据：请按 acceptance/efficiency_data.json 模板录入后复跑。"
                 "未实测不参与提分（禁止伪造）。") if not done else "已部分实测",
    }
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"baseline_{datetime.now().strftime('%Y%m%d-%H%M')}.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.template or not DATA.exists():
        tpl = {t: {"manual_min": None, "assisted_min": None, "auto_min": None, "error_rate": None, "n": 0}
               for t in TASK_TYPES}
        DATA.write_text(json.dumps(tpl, ensure_ascii=False, indent=2), encoding="utf-8")
        print("已生成待填模板:", DATA)

    print(json.dumps({k: report[k] for k in ("avg_speedup_x","measured_count","pending_count")},
                     ensure_ascii=False, indent=2))
    print("证据:", p)
    return 0

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
