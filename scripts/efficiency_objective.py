# -*- coding: utf-8 -*-
"""生成效率提升性客观证据：真实自动化执行计数（非估计，非人工录入）"""
import json, io, sys, os, glob
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\AI-Tools\feishu\V13方案增强")
EVID = ROOT / "acceptance" / "evidence" / "efficiency"
EVID.mkdir(parents=True, exist_ok=True)

# 1) 真实埋点执行数
traces = 0
tpath = ROOT / "runtime" / "metrics" / "traces.jsonl"
if tpath.exists():
    for line in tpath.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            json.loads(line); traces += 1
        except Exception:
            pass

# 2) 真实业务事件量（来自最新备份，客观计数）
counts = {}
hb = sorted(glob.glob(str(ROOT / "backups" / "hourly_*.json")), key=os.path.getmtime)
if hb:
    H = json.load(open(hb[-1], encoding="utf-8"))
    for tb in H.get("tables", []):
        counts[tb["table_name"]] = tb.get("record_count", 0)

# 3) 自动化覆盖率：已挂维护步骤数 / 关键手工流程数
import re
mw = (ROOT / "scripts" / "run_maintenance_wrapper.py").read_text(encoding="utf-8", errors="ignore")
steps = re.findall(r"步骤\s*(\d+)", mw)
n_steps = max([int(s) for s in steps], default=0)

report = {
    "ts": datetime.now().isoformat(timespec="seconds"),
    "method": "客观自动化计数（来自真实埋点与生产数据，非人工估计）",
    "traces_total": traces,
    "maintenance_steps": n_steps,
    "production_counts": counts,
    "scheduled_tasks": ["V16_DailyMaintenance", "V16_HourlyBackup", "V16_MorningReport",
                        "V16_NoonReport", "V16_EveningReport", "V16_LearningPoll"],
    "auto_task_types": 6,
    "manual_baseline_required": True,
    "note": "A/B人工基线（3组对照耗时）仍需用户录入 acceptance/efficiency_data.json；本文件仅提供客观自动化计数，不计入 speedup 计算，禁止伪造。",
}
p = EVID / f"objective_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: report[k] for k in ("traces_total", "maintenance_steps", "auto_task_types")}, ensure_ascii=False))
print("生产计数:", json.dumps(counts, ensure_ascii=False))
print("证据:", p)
