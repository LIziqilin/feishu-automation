#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
时间块规划（V15 Phase2 智能日程）
================================
读飞书任务总表活跃任务（待办/进行中），按优先级自动排进固定时间块，
生成「时间块/今日时间块_YYYY-MM-DD.md」，并刷新「时间块规划.md」今日区块。
- 高优先级 → 上午深度工作块（吃青蛙）
- 中优先级 → 下午深度/协作块
- 学习块   → 错题本/复习卡片（对接 wrong_book）
建议：早报推送后由调度自动跑一次；也可群里发「时间块」手动重排。
"""
import sys, io
from datetime import datetime
sys.path.insert(0, '.')
from v15_features import *

BLOCKS = [
    ("07:30-08:00", "早报+学习规划", "routine"),
    ("08:00-10:00", "深度工作块1", "deep"),
    ("10:00-10:15", "休息+答题", "rest"),
    ("10:15-12:00", "深度工作块2", "deep"),
    ("12:00-13:00", "午休+午报", "routine"),
    ("13:00-15:00", "协作工作块", "collab"),
    ("15:00-15:15", "休息+答题", "rest"),
    ("15:15-17:30", "深度工作块3", "deep"),
    ("17:30-19:00", "学习时间", "study"),
    ("19:00-20:30", "晚餐+休息", "routine"),
    ("20:30-21:00", "晚报+复盘", "routine"),
    ("21:00-22:00", "洞察/阅读", "study"),
]

def load_today_tasks():
    items=list_records(T_TASK)
    active=[]
    for it in items:
        f=it["fields"]
        st=cell_select(f.get("状态"))
        if st not in ("待办","进行中","待开始"): continue
        active.append({"name":cell_text(f.get("任务名称")),
                       "p":cell_select(f.get("优先级")) or "中",
                       "cat":cell_select(f.get("类别")) or "",
                       "due":ts_to_date(f.get("截止日期"))})
    p_order={"高":0,"中":1,"低":2}
    active.sort(key=lambda t:(p_order.get(t["p"],1), t["due"] or "9999"))
    return active

def schedule(tasks, wrong_titles):
    """把任务分配到 deep/collab 块；学习块放错题/复习"""
    highs=[t for t in tasks if t["p"]=="高"]
    mids =[t for t in tasks if t["p"]!="高"]
    plan={}
    # 深度块1：最多2个高优
    plan["deep"]=[t["name"] for t in highs[:2]]
    rest_high=highs[2:]
    # 深度块2：剩余高优 + 中优前2
    plan["deep2"]=[t["name"] for t in rest_high]+[t["name"] for t in mids[:2]]
    # 协作块：中优接下来2个（会议/沟通/对接类优先）
    collab=[t for t in mids[2:4]]
    plan["collab"]=[t["name"] for t in collab]
    # 深度块3：剩余
    used=set(plan["deep"]+plan["deep2"]+plan["collab"])
    plan["deep3"]=[t["name"] for t in tasks if t["name"] not in used][:4]
    # 学习块
    plan["study"]=([f"错题攻克：{w}" for w in wrong_titles[:3]] or ["复习今日闪卡（会/不会/模糊）"])
    return plan

def build(tasks, wrong_titles):
    today=datetime.now().strftime("%Y-%m-%d")
    plan=schedule(tasks, wrong_titles)
    L=[f"# 📋 今日时间块 {today}（自动排程）\n",
       f"> 生成：{now_str()}　|　活跃任务 {len(tasks)} 个　|　错题 {len(wrong_titles)} 张待攻克\n","---\n",
       "| 时间 | 时间块 | 安排 |","|---|---|---|"]
    idx={"deep":0,"deep2":0,"collab":0,"deep3":0}
    for time,title,kind in BLOCKS:
        if kind=="deep":
            items=plan["deep"]; tag="deep"
        elif kind=="collab":
            items=plan["collab"]; tag="collab"
        elif kind=="study":
            items=plan["study"]; tag="study"
        elif kind=="rest":
            items=["起身活动+答2-3张卡"]; tag=""
        elif kind=="routine":
            items={"早报+学习规划":["看早报、定今日三件事"],"午休+午报":["午餐、看午报进度"],
                   "晚餐+休息":["晚餐放松"],"晚报+复盘":["看晚报、销项、写复盘"],
                   "洞察/阅读":["写洞察/自由阅读"]}.get(title,[]); tag=""
        else:
            items=[]; tag=""
        # 深度块2/3映射
        if title=="深度工作块2": items=plan["deep2"]
        if title=="深度工作块3": items=plan["deep3"]
        cell="<br>".join(f"▸ {x}" for x in items) if items else "—"
        L.append(f"| {time} | **{title}** | {cell} |")
    # 未排入的任务
    scheduled=set(plan["deep"]+plan["deep2"]+plan["collab"]+plan["deep3"])
    unscheduled=[t["name"] for t in tasks if t["name"] not in scheduled]
    L.append("")
    L.append("## 📌 任务池（按优先级）\n")
    L.append("**高优**："+("；".join(t["name"] for t in tasks if t["p"]=="高") or "无"))
    L.append("\n**中/低优**："+("；".join(t["name"] for t in tasks if t["p"]!="高") or "无"))
    if unscheduled:
        L.append("\n> 未排入今日时间块（可顺延）："+"；".join(unscheduled))
    L.append("\n---\n## 🍅 执行建议\n")
    L.append("- 每个深度工作块=4个番茄（25min×4），中途不切换、关通知")
    L.append("- 完成一个任务立刻在群发「完成：任务名」销项，然后重排时间块")
    L.append("- 时间块为建议框架，可按实际微调；晚上复盘对照完成率")
    return "\n".join(L)

def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    tasks=load_today_tasks()
    try:
        from wrong_book import collect_wrong
        wrong=[w["title"] for w in collect_wrong()]
    except Exception as e:
        print(f"  [warn] 错题读取失败: {e}"); wrong=[]
    note=build(tasks,wrong)
    today=datetime.now().strftime("%Y-%m-%d")
    p1=write_note(f"时间块/今日时间块_{today}.md", note)
    # 同时刷新根目录主文件
    p2=write_note("时间块规划.md", note.replace(f"# 📋 今日时间块 {today}（自动排程）",
                                                 "# ⏰ 时间块规划（今日自动排程）")+
                  "\n\n---\n## 🧭 固定时间块原则\n深度块吃青蛙、学习块间隔重复、休息块强制断开；历史排程见「时间块」文件夹。\n")
    print(f"✅ {p1}")
    print(f"✅ {p2}")
    print(f"活跃任务{len(tasks)}（高{sum(1 for t in tasks if t['p']=='高')}），错题{len(wrong)}")

if __name__=="__main__":
    main()
