#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""memory_hierarchy.py — V45 记忆分层（借鉴 Hermes 画像分层架构）
====================================================================
把系统记忆分成三层，生成 Obsidian「_meta/系统记忆分层」笔记 + 控制台摘要：

  短期记忆（Working）  近 7 天事件日志 + 近期行为
  长期记忆（Long-term） 画像表最新画像维度（画像值 + 置信度）
  程序性记忆（Procedural） 已掌握卡片(MASTERED) + 已沉淀洞察 + 各科目掌握度

用法：python memory_hierarchy.py [--push]   # --push 将摘要推送到总控群
"""
import os, sys, json, argparse
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v15_features as v15
from obsidian_sync import obs_api

DAYS_WORKING = 7


def _cell(f, key):
    v = f.get(key)
    if isinstance(v, list):
        return v[0].get("text") if v and isinstance(v[0], dict) else (v[0] if v else "")
    return v or ""


def working_memory():
    """短期记忆：近7天事件日志"""
    since = int((datetime.now() - timedelta(days=DAYS_WORKING)).timestamp() * 1000)
    items = []
    for it in v15.list_records(v15.T_EVENTLOG, max_pages=30):
        f = it.get("fields", {})
        ts = f.get("timestamp") or 0
        if isinstance(ts, list):
            ts = ts[0] if ts else 0
        if ts and ts >= since:
            items.append({"ts": ts, "msg": _cell(f, "message"), "type": _cell(f, "log_type"),
                          "sev": _cell(f, "severity"), "src": _cell(f, "source")})
    items.sort(key=lambda x: x["ts"])
    return items


def longterm_memory():
    """长期记忆：画像表全部画像维度"""
    rows = {}
    for it in v15.list_records(v15.T_PROFILE, max_pages=30):
        f = it.get("fields", {})
        dim = _cell(f, "画像维度")
        val = _cell(f, "画像值")
        conf = f.get("置信度")
        if isinstance(conf, list):
            conf = conf[0] if conf else None
        try:
            conf = float(conf)
        except (TypeError, ValueError):
            conf = 0.0
        src = _cell(f, "数据来源")
        if dim and val:
            rows.setdefault(dim, []).append({"v": val, "c": conf, "s": src})
    return rows


def procedural_memory():
    """程序性记忆：卡片掌握 + 洞察沉淀 + 科目分布"""
    stats = {"cards": {}, "insights": 0, "mastered_cards": 0, "subjects": {}}
    for it in v15.list_records(v15.T_CARD, max_pages=60):
        f = it.get("fields", {})
        st = _cell(f, "卡片状态")
        stats["cards"][st] = stats["cards"].get(st, 0) + 1
        if st == "MASTERED":
            stats["mastered_cards"] += 1
    for it in v15.list_records(v15.T_INSIGHT, max_pages=30):
        f = it.get("fields", {})
        if _cell(f, "是否已沉淀") in ("是", "已沉淀", True) or _cell(f, "沉淀状态") in ("已沉淀",):
            stats["insights"] += 1
        subj = _cell(f, "科目")
        if subj:
            stats["subjects"][subj] = stats["subjects"].get(subj, 0) + 1
    return stats


def build_note():
    wm = working_memory()
    lm = longterm_memory()
    pm = procedural_memory()
    today = datetime.now().strftime("%Y-%m-%d")
    lines = ["---", "tags: [系统记忆, 记忆分层]", f"date: {today}", "---", "",
             f"# 系统记忆分层（{today}）", "",
             "## 🧠 短期记忆（近7天行为）", ""]
    if wm:
        for it in wm[-20:]:
            ts = datetime.fromtimestamp(it["ts"] / 1000).strftime("%m-%d %H:%M")
            lines.append(f"- [{it.get('sev') or 'INFO'}] {ts} {it['msg']}")
    else:
        lines.append("（近7天无事件日志）")
    lines += ["", "## 🗂️ 长期记忆（画像分层）", ""]
    if lm:
        for dim, arr in sorted(lm.items()):
            tops = sorted(arr, key=lambda x: -(x["c"] or 0))[:2]
            desc = "；".join(f"{t['v']}(置信度{t['c']})" for t in tops)
            lines.append(f"- **{dim}**：{desc}")
    else:
        lines.append("（画像表暂无数据）")
    lines += ["", "## 💾 程序性记忆（能力沉淀）", ""]
    lines.append(f"- 卡片状态分布：{json.dumps(pm['cards'], ensure_ascii=False)}")
    lines.append(f"- 已掌握卡片(MASTERED)：{pm['mastered_cards']} 张")
    lines.append(f"- 已沉淀洞察：{pm['insights']} 条")
    if pm["subjects"]:
        lines.append(f"- 科目分布：{json.dumps(pm['subjects'], ensure_ascii=False)}")
    return "\n".join(lines), {"wm": wm, "lm": lm, "pm": pm}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true", help="摘要推送到总控群")
    args = ap.parse_args()

    note, data = build_note()
    path = "/vault/_meta/系统记忆分层_" + datetime.now().strftime("%Y-%m-%d") + ".md"
    ok, body = obs_api("PUT", path, note)
    print("Obsidian 记忆分层笔记:", "✅ 写入 " + path if ok else "❌ " + str(body)[:200])

    pm = data["pm"]
    summary = (f"🧠 系统记忆分层 | {datetime.now().strftime('%Y-%m-%d')}\n"
               f"短期记忆：近7天 {len(data['wm'])} 条事件\n"
               f"长期记忆：{len(data['lm'])} 个画像维度\n"
               f"程序性：MASTERED {pm['mastered_cards']} 卡 / 已沉淀洞察 {pm['insights']} 条 / "
               f"卡片分布 {json.dumps(pm['cards'], ensure_ascii=False)}")
    print(summary)
    if args.push:
        v15.send_chat(v15.CHAT_ID, summary)
        print("✅ 摘要已推送总控群")


if __name__ == "__main__":
    main()
