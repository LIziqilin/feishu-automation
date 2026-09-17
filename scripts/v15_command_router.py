#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
V15 新功能群指令路由（被 learning_system.py 导入调用）
====================================================
把总控群里的自然语言指令路由到 9 大新功能，返回 (handled:bool, reply:str)。
支持指令：
  错题本                      → 当前错题清单
  费曼 / 费曼 关键词           → 抽题做费曼输出
  讲解：xxx / 讲解:xxx         → AI 对讲解打分
  番茄                        → 今日番茄统计
  番茄 25 任务名              → 记录一个番茄
  时间块                      → 按任务重排今日时间块
  今日推荐 / 个性化推荐        → 个性化学习推荐队列
  知识演进 / 演进图            → 重新生成知识体系演进图
本模块被 import 时不做 stdout 重定向，避免与主进程冲突。
"""
import os, sys, re, subprocess, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

def _run_sub(script, timeout=180):
    try:
        parts = script.split()
        script_path = os.path.join(HERE, parts[0])
        args = [PY, script_path] + parts[1:]
        r = subprocess.run(args, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        out = (r.stdout or "").strip()
        return r.returncode == 0, out
    except Exception as e:
        return False, str(e)

def handle_v15_command(text):
    t = (text or "").strip()
    low = t.lower()

    # ---------- 错题本 ----------
    if t in ("错题本", "错题", "wrong book") or t.startswith("错题本"):
        try:
            from wrong_book import collect_wrong, summary_for_chat
            wrong = collect_wrong()
            return True, summary_for_chat(wrong)
        except Exception as e:
            return True, f"⚠️ 错题本生成失败：{e}"

    # ---------- 费曼抽题 ----------
    m = re.match(r"^费曼\s*(.*)$", t)
    if m:
        try:
            from feynman_verify import start
            kw = m.group(1).strip() or None
            card, msg = start(kw)
            return True, msg
        except Exception as e:
            return True, f"⚠️ 费曼抽题失败：{e}"

    # ---------- 费曼讲解打分 ----------
    m = re.match(r"^讲解[：:]\s*(.+)$", t)
    if m:
        try:
            from feynman_verify import grade
            card, msg = grade(m.group(1).strip())
            return True, msg
        except Exception as e:
            return True, f"⚠️ 费曼打分失败：{e}"

    # ---------- 番茄 ----------
    m = re.match(r"^番茄\s*(\d+)?\s*(.*)$", t)
    if t == "番茄" or m:
        try:
            import pomodoro
            if m and m.group(1):
                mins = m.group(1); task = m.group(2).strip() or "未命名专注"
                pomodoro.log_pomodoro(mins, task)
                pomodoro.build_board()
            c, total, by = pomodoro.today_summary()
            lines=[f"🍅 今日番茄 {c} 个 / 专注 {total} 分钟（{total/60:.1f}h）"]
            for task,mins in by.most_common(5):
                lines.append(f"· {task}：{mins}分钟")
            if c<8: lines.append(f"距8个深度番茄目标还差 {max(0,8-c)} 个，加油")
            else: lines.append("已达成今日8番茄目标 🎉")
            return True, "\n".join(lines)
        except Exception as e:
            return True, f"⚠️ 番茄记录失败：{e}"

    # ---------- 时间块 ----------
    if t in ("时间块", "今日时间块", "重排时间块", "排时间块"):
        ok, out = _run_sub("time_block_plan.py")
        tail = "\n".join(out.splitlines()[-1:]) if out else ""
        return True, ("⏰ 今日时间块已重排，见 Obsidian「时间块规划.md」\n"+tail) if ok else f"⚠️ 时间块生成失败：{out[-200:]}"

    # ---------- 个性化推荐 ----------
    if t in ("今日推荐", "个性化推荐", "推荐", "学习推荐"):
        try:
            from personalized_recommender import recommend, build_note
            pick, meta = recommend(12)
            lines=[f"🎯 今日为你推荐 {len(pick)} 张卡"+("（疲劳保护已减量）" if meta["fatigue"] else "")]
            for i,c in enumerate(pick[:8],1):
                lines.append(f"{i}. {c['title'][:34]}（{'、'.join(c['reasons'][:2])}）")
            lines.append("完整队列见 Obsidian「个性化学习推荐.md」，发「今日卡片」开始复习")
            return True, "\n".join(lines)
        except Exception as e:
            return True, f"⚠️ 推荐生成失败：{e}"

    # ---------- 知识演进图 ----------
    if t in ("知识演进", "演进图", "知识体系演进", "知识图谱更新"):
        ok, out = _run_sub("knowledge_evolution.py")
        return True, ("🗺 知识体系演进图已更新，见 Obsidian「知识体系演进图.md」与仪表盘") if ok else f"⚠️ 演进图生成失败：{out[-200:]}"

    # ---------- 知识缺口分析 ----------
    if t in ("知识缺口", "缺口分析", "盲点", "knowledge gap"):
        ok, out = _run_sub("knowledge_gap_analysis.py")
        tail = "\n".join(out.splitlines()[-8:]) if out else ""
        return True, ("🔍 知识缺口分析完成，见 Obsidian「知识缺口分析.md」\n" + tail) if ok else f"⚠️ 缺口分析失败：{out[-200:]}"

    # ---------- 画像演化 ----------
    if t in ("画像更新", "更新画像", "越用越懂", "画像演化"):
        ok, out = _run_sub("profile_evolve.py")
        return True, ("🧠 画像已更新，见下方摘要（发「今日推荐」体验新队列）\n" + "\n".join(out.splitlines()[-8:])) if ok else f"⚠️ 画像更新失败：{out[-200:]}"

    # ---------- V44 三察洞察 ----------
    if t in ("三察", "今日三察", "今日洞察", "规律洞察"):
        ok, out = _run_sub("insight_daily.py --push")
        return True, ("🔍 今日三察已生成并推送（天气+社会/自然/人性洞察），已沉淀洞察表\n" + "\n".join(out.splitlines()[:14])) if ok else f"⚠️ 三察生成失败：{out[-200:]}"

    # ---------- V44 洞察沉淀 ----------
    if t in ("沉淀洞察", "洞察转卡片", "洞察沉淀", "知识自增长"):
        ok, out = _run_sub("insight_to_card.py")
        return True, ("🧩 洞察沉淀完成，高价值洞察已转为知识卡片进入复习循环\n" + "\n".join(out.splitlines()[-6:])) if ok else f"⚠️ 沉淀失败：{out[-200:]}"

    # ---------- V45 问系统（轻量 RAG 知识问答） ----------
    m = re.match(r"^问系统[：: ]\s*(.+)$", t) or re.match(r"^问系统\s+(.+)$", t)
    if m:
        try:
            import system_rag
            return True, system_rag.answer(m.group(1).strip()[:200])
        except Exception as e:
            return True, f"⚠️ 系统问答失败：{e}"

    # ---------- V45 智能（Coze 复杂 agentic 任务） ----------
    m = re.match(r"^智能[：: ]\s*(.+)$", t) or re.match(r"^智能\s+(.+)$", t)
    if m:
        try:
            import coze_gateway
            ok, resp = coze_gateway.run(m.group(1).strip()[:300])
            return True, resp
        except Exception as e:
            return True, f"⚠️ 智能任务失败：{e}"

    # ---------- V45 导知识（文本直达知识沉淀，文件导入走 import_knowledge.py） ----------
    m = re.match(r"^导知识[：: ]\s*(.+)$", t) or re.match(r"^导入知识[：: ]\s*(.+)$", t)
    if m:
        try:
            import import_knowledge
            content = m.group(1).strip()[:2000]
            rid = import_knowledge.sink_text("群指令导入：" + content[:24], content, tag="群指令导入")
            return True, (f"📥 已沉淀为知识（洞察表）\n🆔 {rid}\n（会进入「沉淀洞察」卡片闭环）" if rid else "⚠️ 沉淀未成功，请稍后重试")
        except Exception as e:
            return True, f"⚠️ 导知识失败：{e}"

    # ---------- V45 记忆分层 ----------
    if t in ("记忆分层", "系统记忆", "记忆"):
        ok, out = _run_sub("memory_hierarchy.py --push")
        return True, ("🧠 记忆分层已生成（Obsidian「系统记忆分层」+ 摘要推送）\n" + "\n".join(out.splitlines()[-4:])) if ok else f"⚠️ 记忆分层失败：{out[-200]}"

    return False, ""

# 自测
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    for q in ["错题本", "番茄", "今日推荐"]:
        print(f"\n### 指令：{q}")
        h, r = handle_v15_command(q)
        print(f"handled={h}\n{r[:400]}")
