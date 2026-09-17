#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
个性化学习推荐优化（V15 Phase3 学习效率 9.7）
============================================
三大算法：
  1) 掌握度动态间隔：M≥4 间隔×1.5（拉长）；M 2-3 标准；M<2 ×1.2（缩短、更频繁）
  2) 多维加权：错题+30 / 薄弱(M<2)+30 / 兴趣科目+20 / 上次不会模糊+15 / 已掌握(M≥4)-20
  3) 疲劳度调节：近10次复习“不会/模糊”≥50% → 今日减量并混合简单卡，避免挫败
数据：学习卡表 + 复习流水表（取最后复习时间）+ 用户画像表（兴趣）
产出：推荐队列 + Obsidian「个性化学习推荐.md」；供“今日推荐/今日卡片”调用
"""
import sys, io, argparse
from collections import defaultdict
from datetime import datetime, timedelta
sys.path.insert(0, '.')
from v15_features import *

# 记忆等级 → 标准艾宾浩斯间隔（天）
LEVEL_INTERVAL = {0:0, 1:1, 2:2, 3:4, 4:7, 5:15, 6:30}
SUBJECT_KEYS = {"酒店工程":["机电","酒店","工程","维保","给排水","空调","消防","供电"],"认知":["认知","思维","学习方法","模型"],
                "财商":["财商","投资","商业","财务","复利"],"沟通":["沟通","管理","项目管理"],"考证":["考证","一建","二建"],"商业":["商业","项目管理"]}

def _num(v, default=0):
    try: return float(str(v).strip())
    except: return default

def load_flow_stats():
    """聚合每卡：最后复习时间、近期结果序列"""
    last={}; recent=defaultdict(list)
    for r in list_records(T_FLOW):
        f=r["fields"]
        cid = cell_text(f.get("卡片ID"))
        if not cid: continue
        t = ts_to_date(f.get("复习时间") or f.get("创建日期") or f.get("创建时间"))
        res = cell_select(f.get("结果"))
        if t:
            if cid not in last or t>last[cid]: last[cid]=t
        if res in ("会","不会","模糊"):
            recent[cid].append((t,res))
    for cid in recent: recent[cid]=sorted(recent[cid],key=lambda x:x[0] or "")[-10:]
    return last, recent

def interest_subjects():
    """从用户画像推断兴趣科目"""
    text=""
    for r in list_records(T_PROFILE):
        f=r["fields"]
        text += cell_text(f.get("画像值"))+" "
    hit=set()
    for sub,kws in SUBJECT_KEYS.items():
        if any(k in text for k in kws): hit.add(sub)
    return hit

def dynamic_interval_days(level, m):
    """掌握度动态间隔"""
    base=LEVEL_INTERVAL.get(int(level),2)
    if base==0: return 0
    if m>=4: return round(base*1.5,1)
    if m<2:  return round(base*1.2,1)
    return float(base)

def recommend(top_n=12):
    cards=list_records(T_CARD)
    last, recent = load_flow_stats()
    interests = interest_subjects()
    # 全局疲劳度：近10条流水（所有卡）
    global_recent=[]
    for seq in recent.values(): global_recent+=[r for _,r in seq]
    global_recent=global_recent[-10:]
    bad=sum(1 for r in global_recent if r in ("不会","模糊"))
    fatigue = len(global_recent)>=6 and bad/len(global_recent)>=0.5
    if fatigue: top_n=min(top_n,8)

    wrong_titles=set()
    try:
        from wrong_book import collect_wrong
        wrong_titles={w["title"] for w in collect_wrong()}
    except Exception: pass

    now=datetime.now(); scored=[]
    for c in cards:
        f=c["fields"]; rid=c["record_id"]
        status=cell_select(f.get("卡片状态"))
        if status in ("MASTERED","ARCHIVED"): continue
        title=cell_text(f.get("卡片问题正面")); subj=cell_select(f.get("科目")) or "未分类"
        m=_num(cell_num(f.get("掌握度M")))
        level=int(_num(f.get("记忆等级"),0)); reps=int(_num(f.get("复习次数"),0))
        lastres=cell_select(f.get("last_result"))
        score=0.0; reasons=[]
        # 1 到期分
        if reps==0:
            score+=50; reasons.append("新卡")
        else:
            lt=last.get(rid)
            interval=dynamic_interval_days(level,m)
            if lt and interval>0:
                try:
                    ltd=datetime.strptime(lt[:10],"%Y-%m-%d"); ratio=(now-ltd).days/interval
                    if ratio>=1: score+=40+min(ratio*10,30); reasons.append(f"已到期{ratio:.1f}倍")
                    else: score+=max(0,10*(1-ratio))
                except: score+=20
            else: score+=20
        # 2 错题
        if title in wrong_titles: score+=30; reasons.append("错题优先")
        # 3 掌握度
        if m<2: score+=30; reasons.append("薄弱")
        elif m<=3: score+=10
        elif m>=4: score-=20; reasons.append("较熟降权")
        # 4 兴趣
        if subj in interests: score+=20; reasons.append("兴趣领域")
        # 5 上次结果
        if lastres in ("不会","模糊"): score+=15; reasons.append(f"上次{lastres}")
        scored.append({"rid":rid,"title":title,"subj":subj,"m":m,"level":level,"reps":reps,
                       "next_interval":dynamic_interval_days(level,m),"score":round(score,1),
                       "reasons":reasons,"easy": m})
    # 疲劳时保证混入简单卡（m相对高的）
    scored.sort(key=lambda x:-x["score"])
    pick=scored[:top_n]
    if fatigue:
        easy=sorted(scored,key=lambda x:-x["m"])[:2]
        have={p["rid"] for p in pick}
        for e in easy:
            if e["rid"] not in have: pick.insert(0,e)
        pick=pick[:top_n]
    return pick, {"fatigue":fatigue,"bad":bad,"n":len(global_recent),"interests":sorted(interests)}

def build_note(pick, meta):
    L=["# 🎯 个性化学习推荐（自动生成）\n",
       f"> 更新：{now_str()}　|　推荐 {len(pick)} 张　|　兴趣领域：{'、'.join(meta['interests']) or '未识别'}",
       ("\n> ⚠️ **疲劳保护已触发**：近期答错率偏高，今日减量并混入简单卡，先找回正反馈\n" if meta["fatigue"] else ""),
       "\n---\n","## 今日推荐队列（按优先级）\n",
       "| # | 卡片 | 科目 | 掌握M | 建议间隔(天) | 推荐理由 |","|---|---|---|---|---|---|"]
    for i,c in enumerate(pick,1):
        L.append(f"| {i} | {c['title']} | {c['subj']} | {c['m']:.0f} | {c['next_interval']} | {'、'.join(c['reasons'])} |")
    L.append("\n## 算法说明\n")
    L.append("- **动态间隔**：M≥4 间隔×1.5（少打扰）；M 2-3 标准；M<2 ×1.2（多巩固）")
    L.append("- **加权**：错题+30｜薄弱(M<2)+30｜兴趣+20｜上次不会/模糊+15｜已掌握-20")
    L.append("- **疲劳保护**：近10次答错≥50% 自动减量并混合简单卡")
    L.append("\n> 在总控群发「今日卡片」开始复习，答「会/不会/模糊」后推荐会自动更新")
    return "\n".join(L)

def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    ap=argparse.ArgumentParser(); ap.add_argument("--n",type=int,default=12); ap.add_argument("--quiet",action="store_true")
    args=ap.parse_args()
    pick,meta=recommend(args.n)
    note=build_note(pick,meta)
    p=write_note("个性化学习推荐.md",note)
    print(f"✅ {p}")
    print(f"推荐{len(pick)}张 疲劳保护={meta['fatigue']} 兴趣={meta['interests']}")
    for i,c in enumerate(pick[:5],1):
        print(f"  {i}. [{c['score']}] {c['title'][:30]} ({'、'.join(c['reasons'])})")

if __name__=="__main__":
    main()
