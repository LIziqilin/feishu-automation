#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
错题本机制（V15 Phase2）
================================
数据源：学习卡表 + 复习流水表（结果=不会/模糊）
产出：
  1. Obsidian「错题本.md」实时错题清单（真实数据，替代纯Dataview依赖本地frontmatter）
  2. get_wrong_cards()：错题优先复习队列（供个性化推荐调用）
  3. --chat：推送错题摘要到飞书总控群
判定：卡片 last_result∈{不会,模糊} 或 近30天流水有不会/模糊且未重新连对2次
"""
import sys, io, argparse
from collections import defaultdict, Counter
from datetime import datetime, timedelta
sys.path.insert(0, '.')
from v15_features import *

WRONG_RESULTS = {"不会", "模糊"}

def collect_wrong():
    """返回错题列表，每项 dict: card字段 + 累计错误次数 + 最近错误时间 + 错因统计"""
    cards = list_records(T_CARD)
    flows = list_records(T_FLOW)

    # 按卡片ID聚合流水：错误次数、最近错误日、错因分布、最近5条结果序列
    stat = defaultdict(lambda: {"wrong":0, "last_wrong":"", "err_types":Counter(), "recent":[]})
    cutoff = datetime.now() - timedelta(days=30)
    for fl in flows:
        f = fl.get("fields", {})
        result = cell_select(f.get("结果"))
        if result not in WRONG_RESULTS and result != "会":
            continue
        cid = cell_text(f.get("卡片ID")).strip()
        title = cell_text(f.get("卡片标题")).strip()
        key = cid or title
        d = ts_to_date(f.get("客户端时间戳"))
        if result in WRONG_RESULTS:
            stat[key]["wrong"] += 1
            if d and d > stat[key]["last_wrong"]:
                stat[key]["last_wrong"] = d
            et = cell_select(f.get("错因"))
            if et: stat[key]["err_types"][et] += 1
        stat[key]["recent"].append((d, result))

    wrong = []
    for c in cards:
        f = c.get("fields", {})
        rid = c.get("record_id", "")
        title = cell_text(f.get("卡片问题正面"))
        last = cell_select(f.get("last_result")) or cell_select(f.get("本次复习结果"))
        times = int(cell_num(f.get("复习次数")))
        streak = int(cell_num(f.get("连续正确次数")))
        m = cell_num(f.get("掌握度M"))
        subject = cell_select(f.get("科目"))
        err = cell_text(f.get("错因"))
        status = cell_select(f.get("卡片状态"))
        s = stat.get(rid) or stat.get(title)
        flow_wrong = s["wrong"] if s else 0
        last_wrong = s["last_wrong"] if s else ""
        err_types = dict(s["err_types"]) if s else {}
        if err and not err_types: err_types = {err: 1}

        # 错题判定：必须是真正学过（复习次数>0 且 非NOT_STARTED）
        learned = times > 0 and status != "NOT_STARTED"
        is_wrong = False
        if learned and last in WRONG_RESULTS:
            is_wrong = True
        elif learned and flow_wrong > 0 and streak < 2 and last_wrong >= cutoff.strftime("%Y-%m-%d"):
            is_wrong = True
        if not is_wrong:
            continue

        # 严重度：错误次数+掌握度
        severity = flow_wrong + (1 if last in WRONG_RESULTS else 0) + max(0, 3-int(m))
        wrong.append({
            "record_id": rid, "title": title, "subject": subject,
            "last": last, "flow_wrong": flow_wrong, "last_wrong": last_wrong,
            "err_types": err_types, "m": m, "times": times, "streak": streak,
            "status": status, "severity": severity,
            "answer": cell_text(f.get("标准答案背面")),
        })
    wrong.sort(key=lambda x: (-x["severity"], x["m"]))
    return wrong

def build_note(wrong):
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append("# ❌ 错题本（自动同步）\n")
    lines.append(f"> 最近更新：{today}　|　错题 {len(wrong)} 张　|　数据源：飞书学习卡表+复习流水")
    lines.append("> 攻克顺序：从上到下（错误越多、掌握度越低越优先）\n")
    lines.append("---\n")

    # 总览统计
    by_subject = Counter(w["subject"] or "未分类" for w in wrong)
    by_errtype = Counter()
    for w in wrong:
        if w["err_types"]:
            for k,v in w["err_types"].items(): by_errtype[k]+=v
        else: by_errtype["未标注"]+=1
    lines.append("## 📊 错题分布\n")
    lines.append("| 维度 | 分布 |")
    lines.append("|---|---|")
    lines.append("| 按科目 | " + "；".join(f"{k} {v}张" for k,v in by_subject.most_common()) + " |")
    lines.append("| 按错因 | " + "；".join(f"{k} {v}张" for k,v in by_errtype.most_common()) + " |")
    lines.append("")

    # 错题清单表
    lines.append("## 🔴 错题清单（按严重度排序）\n")
    lines.append("| # | 题目 | 科目 | 上次 | 累计错 | 掌握度 | 错因 | 最近答错 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for i,w in enumerate(wrong,1):
        et = "、".join(f"{k}×{v}" for k,v in w["err_types"].items()) or "未标注"
        lines.append(f"| {i} | {w['title']} | {w['subject']} | {w['last'] or '—'} | {w['flow_wrong']} | M={w['m']:.0f} | {et} | {w['last_wrong'] or '—'} |")
    lines.append("")

    # 逐题攻克卡
    lines.append("---\n## 📖 逐题攻克（遮住答案自测）\n")
    for i,w in enumerate(wrong,1):
        lines.append(f"### {i}. {w['title']}\n")
        lines.append(f"- **科目**：{w['subject']}　**掌握度**：M={w['m']:.0f}　**累计答错**：{w['flow_wrong']}次　**最近答错**：{w['last_wrong'] or '—'}")
        et = "、".join(f"{k}×{v}" for k,v in w["err_types"].items())
        lines.append(f"- **错因**：{et or '未标注（下次答错请用「不会 记不清/理解错」带上错因）'}")
        if w["answer"]:
            lines.append(f"- **标准答案**：\n  > {w['answer'][:300]}")
        lines.append(f"- **攻克动作**：连续答对2次即移出错题本；仍不会则在群里发「费曼 {w['title'][:12]}」做输出验证\n")

    # 攻克方法
    lines.append("---\n## 🧠 四类错因的针对性攻克法\n")
    lines.append("| 错因 | 本质 | 攻克法 |")
    lines.append("|---|---|---|")
    lines.append("| 记不清 | 记忆痕迹弱 | 缩短间隔到1天，用艾宾浩斯高频重复+主动回忆 |")
    lines.append("| 理解错 | 概念没打通 | 费曼输出：用自己的话讲一遍，找底层规律，配1个实例 |")
    lines.append("| 题目歧义 | 表述/边界不清 | 补充题目前提条件，关联到具体SOP/场景 |")
    lines.append("| 已过期 | 知识迭代 | 更新标准答案，标注新版本，归档旧表述 |")
    lines.append("")
    lines.append("---\n## 🗂 本地视图（Dataview，依赖卡片frontmatter）\n")
    lines.append("```dataview")
    lines.append('TABLE 科目 AS "科目", 掌握度M AS "掌握度", 错因 AS "错因", 复习次数 AS "复习次数"')
    lines.append('FROM "学习卡片"')
    lines.append('WHERE 错因 AND 错因 != ""')
    lines.append("SORT 掌握度M ASC")
    lines.append("```\n")
    return "\n".join(lines)

def summary_for_chat(wrong):
    if not wrong:
        return "✅ 错题本为空：当前没有答错未掌握的卡片，继续保持！"
    lines = [f"❌ 错题本（{len(wrong)}张待攻克）"]
    for i,w in enumerate(wrong[:8],1):
        et = "、".join(w["err_types"].keys()) or "未标注"
        lines.append(f"{i}. [{w['subject']}] {w['title'][:24]}（{w['last'] or '错'}×{w['flow_wrong']}，{et}）")
    if len(wrong)>8: lines.append(f"…其余{len(wrong)-8}张见Obsidian错题本")
    lines.append("攻克：连对2次移出；「费曼 题目」可AI讲解打分")
    return "\n".join(lines)

def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat", action="store_true", help="推送摘要到飞书群")
    ap.add_argument("--note", action="store_true", help="生成Obsidian错题本（默认也生成）")
    args = ap.parse_args()

    wrong = collect_wrong()
    note = build_note(wrong)
    p = write_note("错题本.md", note)
    print(f"✅ 错题本已生成: {p}")
    print(f"   错题 {len(wrong)} 张")
    for w in wrong:
        print(f"   - [{w['subject']}] {w['title'][:30]} last={w['last']} 累计错{w['flow_wrong']}")
    if args.chat:
        ok = send_chat(summary_for_chat(wrong))
        print("✅ 已推送群" if ok else "❌ 群推送失败")

if __name__ == "__main__":
    main()
