#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
知识体系演进图（V15 Phase3 知识连接）
================================
数据源：学习卡表（创建日期/科目/状态/掌握度）+ 洞察笔记表（洞察日期）
产出：
  1. Obsidian「知识体系演进图.md」：累计增长/科目矩阵/掌握漏斗（真实数据）
  2. Obsidian「00-仪表盘/知识体系演进看板.html」：ECharts四图（增长曲线/科目/状态漏斗/洞察）
建议：每月1号由调度自动生成，看知识体系成长
"""
import sys, io, json
from collections import Counter, defaultdict
from datetime import datetime
sys.path.insert(0, '.')
from v15_features import *

STATUS_ORDER = ["NOT_STARTED","LEARNING","REVIEWING","MASTERED","ARCHIVED"]
STATUS_CN = {"NOT_STARTED":"未开始","LEARNING":"学习中","REVIEWING":"复习中","MASTERED":"已掌握","ARCHIVED":"已归档"}

def gather():
    cards = list_records(T_CARD)
    insights = list_records(T_INSIGHT)
    crows=[]
    for c in cards:
        f=c["fields"]
        crows.append({
            "created": ts_to_date(f.get("创建日期"))[:7] or "未知",  # YYYY-MM
            "created_full": ts_to_date(f.get("创建日期")),
            "subject": cell_select(f.get("科目")) or "未分类",
            "status": cell_select(f.get("卡片状态")) or "NOT_STARTED",
            "m": cell_num(f.get("掌握度M")),
            "title": cell_text(f.get("卡片问题正面")),
        })
    irows=[]
    for it in insights:
        f=it["fields"]
        d = ts_to_date(f.get("洞察日期") or f.get("创建日期"))
        irows.append({"month": d[:7] or "未知", "date": d})
    return crows, irows

def build_md(crows, irows):
    now=now_str()
    total=len(crows)
    # 月度累计增长
    month_new=Counter(r["created"] for r in crows)
    months=sorted(month_new)
    cum=0; growth=[]
    for m in months:
        cum+=month_new[m]; growth.append((m,month_new[m],cum))
    # 科目矩阵
    subj=defaultdict(lambda: Counter())
    subj_m=defaultdict(list)
    for r in crows:
        subj[r["subject"]][r["status"]]+=1
        subj_m[r["subject"]].append(r["m"])
    # 状态漏斗
    stc=Counter(r["status"] for r in crows)
    mastered=stc.get("MASTERED",0)
    rate = mastered/total*100 if total else 0

    L=["# 🗺 知识体系演进图（自动生成）\n",
       f"> 更新：{now}　|　学习卡片 {total} 张　|　洞察笔记 {len(irows)} 条　|　整体掌握率 {rate:.0f}%\n","---\n",
       "## 📈 卡片累计增长\n","| 月份 | 当月新增 | 累计 |","|---|---|---|"]
    for m,n,c in growth: L.append(f"| {m} | {n} | {c} |")
    L.append("")
    # 文本条形
    L.append("**增长条形**（█=1张）\n")
    for m,n,c in growth:
        L.append(f"- {m}：{'█'*n} +{n}（累计{c}）")
    L.append("")
    L.append("## 🧩 科目 × 掌握度矩阵\n")
    L.append("| 科目 | 总数 | 未开始 | 学习中 | 复习中 | 已掌握 | 平均掌握度M |")
    L.append("|---|---|---|---|---|---|---|")
    for s in sorted(subj, key=lambda k:-sum(subj[k].values())):
        cc=subj[s]; ms=subj_m[s]; avg=sum(ms)/len(ms) if ms else 0
        L.append(f"| {s} | {sum(cc.values())} | {cc.get('NOT_STARTED',0)} | {cc.get('LEARNING',0)} | {cc.get('REVIEWING',0)} | {cc.get('MASTERED',0)} | {avg:.1f} |")
    L.append("")
    L.append("## 🔻 掌握阶段漏斗\n")
    for s in STATUS_ORDER:
        n=stc.get(s,0)
        if n: L.append(f"- {STATUS_CN[s]}（{s}）：{'█'*n} {n}张")
    L.append("")
    L.append("## 💡 洞察积累\n")
    im=Counter(r["month"] for r in irows)
    L.append("| 月份 | 洞察数 |")
    L.append("|---|---|")
    for m in sorted(im): L.append(f"| {m} | {im[m]} |")
    L.append("")
    L.append("> 可视化看板见：`00-仪表盘/知识体系演进看板.html`（浏览器或Obsidian打开）")
    return "\n".join(L), dict(months=months, month_new={m:month_new[m] for m in months},
        subj={s:dict(subj[s]) for s in subj}, stc=dict(stc),
        insight_month={m:im[m] for m in sorted(im)}, total=total, insights=len(irows), rate=rate)

HTML_TPL = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>知识体系演进看板</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>body{{font-family:'Microsoft YaHei',sans-serif;margin:0;background:#f5f6fa}}
.h{{background:#2c3e50;color:#fff;padding:14px 24px;font-size:18px}}
.grid{{display:flex;flex-wrap:wrap;gap:16px;padding:16px}}
.card{{flex:1 1 46%;min-width:420px;background:#fff;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.08);padding:8px}}
.chart{{height:340px}}</style></head><body>
<div class="h">🗺 知识体系演进看板　|　更新 {now}　|　卡片 {total} 张 · 洞察 {insights} 条 · 掌握率 {rate:.0f}%</div>
<div class="grid">
<div class="card"><div id="g1" class="chart"></div></div>
<div class="card"><div id="g2" class="chart"></div></div>
<div class="card"><div id="g3" class="chart"></div></div>
<div class="card"><div id="g4" class="chart"></div></div>
</div>
<script>
const D={data};
echarts.init(document.getElementById('g1')).setOption({{title:{{text:'卡片累计增长',left:'center',textStyle:{{fontSize:14}}}},
 tooltip:{{trigger:'axis'}},grid:{{left:50,right:20,top:45,bottom:30}},
 xAxis:{{type:'category',data:D.months}},yAxis:{{type:'value'}},
 series:[{{name:'当月新增',type:'bar',data:D.months.map(m=>D.month_new[m]),itemStyle:{{color:'#5b8ff9'}}}},
 {{name:'累计',type:'line',smooth:true,data:D.months.map((m,i)=>D.months.slice(0,i+1).reduce((a,x)=>a+D.month_new[x],0)),itemStyle:{{color:'#f6bd16'}}}}]}});
const subs=Object.keys(D.subj);
echarts.init(document.getElementById('g2')).setOption({{title:{{text:'各科目掌握结构',left:'center',textStyle:{{fontSize:14}}}},
 tooltip:{{trigger:'axis',axisPointer:{{type:'shadow'}}}},legend:{{bottom:0}},grid:{{left:50,right:20,top:45,bottom:50}},
 xAxis:{{type:'category',data:subs}},yAxis:{{type:'value'}},
 ['NOT_STARTED','LEARNING','REVIEWING','MASTERED'].map((st,i)=>({{name:{{'NOT_STARTED':'未开始','LEARNING':'学习中','REVIEWING':'复习中','MASTERED':'已掌握'}}[st],type:'bar',stack:'x',data:subs.map(s=>(D.subj[s][st]||0))}}))]}});
const so=['NOT_STARTED','LEARNING','REVIEWING','MASTERED'];const scn=['未开始','学习中','复习中','已掌握'];
echarts.init(document.getElementById('g3')).setOption({{title:{{text:'掌握阶段漏斗',left:'center',textStyle:{{fontSize:14}}}},
 tooltip:{{}},series:[{{type:'funnel',left:'10%',width:'80%',label:{{formatter:'{{b}}: {{c}}'}},
 data:so.map((s,i)=>({{name:scn[i],value:D.stc[s]||0}}))}}]}});
const im=Object.keys(D.insight_month);
echarts.init(document.getElementById('g4')).setOption({{title:{{text:'洞察笔记积累',left:'center',textStyle:{{fontSize:14}}}},
 tooltip:{{trigger:'axis'}},grid:{{left:50,right:20,top:45,bottom:30}},xAxis:{{type:'category',data:im}},yAxis:{{type:'value'}},
 series:[{{type:'line',smooth:true,areaStyle:{{}},data:im.map(m=>D.insight_month[m]),itemStyle:{{color:'#5ad8a6'}}}}]}});
</script></body></html>"""

def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    crows,irows=gather()
    md,data=build_md(crows,irows)
    p1=write_note("知识体系演进图.md", md)
    html=HTML_TPL.format(now=now_str(),total=data["total"],insights=data["insights"],rate=data["rate"],data=json.dumps(data,ensure_ascii=False))
    p2=write_note("00-仪表盘/知识体系演进看板.html", html)
    print(f"✅ {p1}")
    print(f"✅ {p2}")
    print(f"卡片{data['total']} 洞察{data['insights']} 掌握率{data['rate']:.0f}% 月份{data['months']}")

if __name__=="__main__":
    main()
