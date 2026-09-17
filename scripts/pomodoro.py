#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
番茄钟集成（V15 Phase2 工作效率）
================================
- 群指令「番茄 25 任务名」：记录一个25分钟番茄，追加到 Obsidian「日志/番茄记录_YYYY-MM.md」
- 每条用 Dataview inline 字段：时长/任务/时间，便于 Dataview 聚合
- 生成「番茄钟.md」主看板：今日/本周统计 + 操作说明 + 内置Dataview
- 标准节奏：专注25分钟 + 休息5分钟；每4个番茄长休息15-30分钟
CLI: python pomodoro.py --log 25 写周报
     python pomodoro.py --board
"""
import sys, io, argparse, re
from datetime import datetime, timedelta
from collections import Counter
sys.path.insert(0, '.')
from v15_features import *

POMO_DIR = VAULT / "日志"

def _month_file():
    return POMO_DIR / f"番茄记录_{datetime.now().strftime('%Y-%m')}.md"

def log_pomodoro(minutes, task):
    minutes = int(minutes)
    now = datetime.now()
    f = _month_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    day = now.strftime("%Y-%m-%d")
    header = f"## {day}\n"
    line = (f"- {now.strftime('%H:%M')} (时长:: {minutes}) (任务:: {task}) "
            f"(类型:: 番茄) (时间戳:: {now.strftime('%Y-%m-%d %H:%M')})\n")
    if not f.exists():
        f.write_text(f"# 番茄记录 {now.strftime('%Y年%m月')}\n\n> 由 pomodoro.py 自动记录，Dataview 可聚合 inline 字段\n\n", encoding="utf-8")
    txt = f.read_text(encoding="utf-8")
    if header not in txt:
        txt = txt.rstrip()+"\n\n"+header
    txt = txt.rstrip()+"\n"+line
    f.write_text(txt, encoding="utf-8")
    return f

def read_month_records():
    """读取本月番茄记录，返回 [(date,time,minutes,task)]"""
    f=_month_file()
    recs=[]
    if not f.exists(): return recs
    cur=""
    for line in f.read_text(encoding="utf-8").splitlines():
        m=re.search(r"-\s*(\d{2}:\d{2}).*?时长::\s*(\d+).*?任务::\s*(.+?)\)\s*\(类型", line)
        dm=re.search(r"## (\d{4}-\d{2}-\d{2})", line)
        if dm: cur=dm.group(1)
        if m:
            recs.append((cur, m.group(1), int(m.group(2)), m.group(3).strip()))
    return recs

def today_summary():
    today=datetime.now().strftime("%Y-%m-%d")
    recs=read_month_records()
    t=[r for r in recs if r[0]==today]
    total=sum(r[2] for r in t)
    by_task=Counter()
    for _,_,mins,task in t: by_task[task]+=mins
    return len(t), total, by_task

def build_board():
    count,total,by_task=today_summary()
    note=f"""# 🍅 番茄钟（自动看板）

> 更新：{now_str()}　|　今日番茄 **{count}** 个　|　专注 **{total}** 分钟（{total/60:.1f}小时）

---

## ▶ 怎么用（三种方式）

1. **飞书群记录**（推荐）：完成一个番茄后在总控群发
   - `番茄 25 写周报`　← 记录一个25分钟、任务为「写周报」的番茄
   - `番茄`　← 查看今日统计
2. **标准节奏**：专注25分钟 → 休息5分钟；每完成4个番茄 → 长休息15~30分钟
3. **手动补录**：直接在「日志/番茄记录_{datetime.now().strftime('%Y-%m')}.md」按格式追加

---

## 📊 今日专注

| 指标 | 数值 |
|---|---|
| 番茄个数 | {count} |
| 总专注时长 | {total} 分钟 |
| 折合小时 | {total/60:.1f} h |
| 距8个番茄目标 | {'已达成 🎉' if count>=8 else f'还差 {max(0,8-count)} 个'} |

### 今日按任务分布
"""
    if by_task:
        note+="| 任务 | 专注分钟 | 番茄数 |\n|---|---|---|\n"
        for task,mins in by_task.most_common():
            note+=f"| {task} | {mins} | {round(mins/25,1)} |\n"
    else:
        note+="\n_今天还没有番茄记录，开始第一个吧：群里发「番茄 25 任务名」_\n"
    note+="""
---

## 📈 本月全部记录（Dataview 聚合）

```dataview
TABLE L.时长 AS "时长(分)", L.任务 AS "任务", L.时间戳 AS "时间"
FROM "日志"
FLATTEN file.lists AS L
WHERE L.类型 = "番茄"
SORT L.时间戳 DESC
LIMIT 50
```

### 本月每日专注时长
```dataviewjs
const pages = dv.pages('"日志"').where(p=>p.file.name.startsWith("番茄记录"));
let rows={};
for(const p of pages){ for(const l of p.file.lists){ if(l.类型=="番茄"){ const d=(l.时间戳||"").toString().slice(0,10); rows[d]=(rows[d]||0)+(l.时长||0);} }}
dv.table(["日期","专注分钟"], Object.entries(rows).sort().reverse().map(([d,m])=>[d,m]));
```

---

## 🧠 番茄工作法要点
- 一个番茄25分钟不可分割，中断则该番茄作废重来
- 番茄期间关闭通知，只做当前任务（关联「时间块规划」深度工作块）
- 番茄数比时钟时长更能反映有效专注
- 每天目标：深度工作 6~8 个番茄（约3-3.5小时高质量产出）
"""
    p=write_note("番茄钟.md", note)
    return p

def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    ap=argparse.ArgumentParser()
    ap.add_argument("--log",nargs=2,metavar=("MINUTES","TASK"))
    ap.add_argument("--board",action="store_true")
    args=ap.parse_args()
    if args.log:
        f=log_pomodoro(args.log[0],args.log[1])
        c,t,bt=today_summary()
        print(f"✅ 已记录番茄 {args.log[0]}分钟：{args.log[1]} → {f.name}")
        print(f"今日累计 {c}个 / {t}分钟")
    p=build_board()
    print(f"✅ 番茄钟看板: {p}")
    c,t,_=today_summary()
    print(f"今日: {c}个番茄, {t}分钟")

if __name__=="__main__":
    main()
