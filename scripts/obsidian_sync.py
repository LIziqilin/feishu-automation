#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""obsidian_sync.py — V45 Obsidian 双向同步深化
====================================================================
1) 每日笔记自动生成：洞察表当日三察/洞察 + 任务表当日摘要 -> Obsidian 每日笔记
   （复用 Obsidian Local REST API 27124，frontmatter + 双向链接 + 标签）
2) MASTERED 卡片回流：学习卡表 状态=MASTERED -> Obsidian 知识库归档
   （幂等：本地 .obsidian_card_archived.json 记录已回流 record_id）

用法：
  python obsidian_sync.py --daily            # 生成今日每日笔记
  python obsidian_sync.py --cards            # MASTERED 卡片回流（--apply 才实际写入）
  python obsidian_sync.py --cards --apply    # 实际回流
  python obsidian_sync.py --all              # 每日笔记 + 卡片回流（dry-run）
"""
import os, sys, re, json, time, ssl, argparse
import urllib.request, urllib.parse, urllib.error
from datetime import datetime, date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v15_features as v15

# ============ Obsidian Local REST API（27124，支持 MCP）============
OBS_BASE = "https://127.0.0.1:27124"
OBS_KEY = "579c9276444b294ea705e20c327b8f9ff9d80db756fdfd63939e474d9b3cc489"
DAILY_DIR = "每日笔记"
KB_DIR = "知识库"
_ARCHIVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".obsidian_card_archived.json")
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

T_CARD = v15.T_CARD
T_INSIGHT = v15.T_INSIGHT
T_TASK = v15.T_TASK
T_EVENTLOG = v15.T_EVENTLOG


def _enc_path(path):
    return "/".join(urllib.parse.quote(p) for p in path.split("/"))


def obs_api(method, path, body=None, ct="text/markdown"):
    """调用 Obsidian Local REST API；成功返回 (True, text)，失败 (False, err)"""
    data = body.encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        OBS_BASE + _enc_path(path), data=data, method=method,
        headers={"Authorization": "Bearer " + OBS_KEY, "Content-Type": ct})
    try:
        r = urllib.request.urlopen(req, context=_ctx, timeout=12)
        return True, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"
    except Exception as e:
        return False, str(e)


def _norm_title(s):
    s = re.sub(r'[\\/:*?"<>|]', "_", str(s)).strip()
    return s[:60] or "未命名"


def _select_text(v):
    if isinstance(v, list):
        return v[0].get("text", "") if v else ""
    if isinstance(v, dict):
        return v.get("text", "")
    return str(v) if v else ""


def _multi_text(v):
    if isinstance(v, list):
        return [x.get("text", "") if isinstance(x, dict) else str(x) for x in v]
    return [str(v)] if v else []


def _load_archived():
    try:
        with open(_ARCHIVE_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def _save_archived(s):
    with open(_ARCHIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(s), f, ensure_ascii=False, indent=1)


def _log_event(msg, detail, log_type="SYSTEM", severity="INFO"):
    try:
        v15.create_record(T_EVENTLOG, {
            "message": msg, "detail": detail, "source": "system",
            "log_type": log_type, "severity": severity,
            "timestamp": v15.date_ms(),
        })
    except Exception as e:
        print(f"  [事件日志] 写入失败: {e}")


# ============ 1) 每日笔记自动生成 ============
def daily_note(apply=True, target_date=None):
    d = target_date or date.today()
    ds = d.strftime("%Y-%m-%d")
    ds_slash = d.strftime("%Y/%m/%d")
    print(f"=== 每日笔记 {ds} ===")

    # 1a) 当日洞察（洞察日期 = 今天；取 洞察标题/洞察内容/AI摘要/类型/标签/来源）
    insights = []
    for it in v15.list_records(T_INSIGHT, max_pages=30):
        f = it.get("fields", {})
        idate = f.get("洞察日期") or f.get("创建日期")
        idate_s = v15.ts_to_date(idate) if idate else ""
        if idate_s and idate_s != ds:
            continue
        # 洞察日期为空的历史记录：仅保留"三察/知识沉淀/随手记"型（近期产生的），限 10 条
        itype = _select_text(f.get("洞察类型"))
        src = v15.cell_text(f.get("来源") or "")
        if not idate_s:
            if itype not in ("知识沉淀", "随手记") and "规律洞察日报" not in src:
                continue
            if len(insights) >= 10:
                continue
        title = v15.cell_text(f.get("洞察标题") or "")
        content = v15.cell_text(f.get("洞察内容") or "") or v15.cell_text(f.get("AI摘要") or "") or v15.cell_text(f.get("内容") or "")
        if not title and not content:
            continue
        insights.append({
            "title": title or content[:40],
            "content": content,
            "type": _select_text(f.get("洞察类型")),
            "tags": _multi_text(f.get("标签")),
            "subject": _select_text(f.get("科目")) or _select_text(f.get("关联科目")),
            "source": v15.cell_text(f.get("来源") or ""),
        })
    print(f"  当日洞察记录: {len(insights)}")

    # 1b) 当日任务摘要（今日创建 or 今日完成；任务总表）
    today_ms = v15.date_ms()  # 当天 00:00 的毫秒
    tomorrow_ms = today_ms + 86400000
    tasks = []
    for it in v15.list_records(T_TASK, max_pages=40):
        f = it.get("fields", {})
        title = v15.cell_text(f.get("任务名称") or f.get("标题") or f.get("名称") or "")
        status = _select_text(f.get("状态"))
        created = f.get("创建时间") or f.get("创建日期")
        finished = f.get("完成时间")
        hit = False
        for field, name in ((created, "创建"), (finished, "完成")):
            try:
                if isinstance(field, (int, float)) and field > 0 and today_ms <= field < tomorrow_ms:
                    tasks.append({"title": title, "mark": name, "status": status})
                    hit = True
                    break
            except Exception:
                pass
        if not hit and title and status in ("已完成", "完成", "done"):
            tasks.append({"title": title, "mark": "完成", "status": status})
    tasks = tasks[:40]
    print(f"  当日任务条目: {len(tasks)}")

    # 1c) 组装笔记
    lines = []
    lines.append("---")
    lines.append(f"created: {ds}")
    lines.append("tags: [每日笔记, AI系统]")
    lines.append("---")
    lines.append(f"# 📅 {ds} 每日笔记")
    lines.append("")
    lines.append("> 由 AI 学习系统自动生成 · 三察洞察 + 任务摘要")
    lines.append("")
    if insights:
        lines.append("## 🧠 今日洞察（三察/随手记）")
        for ins in insights[:20]:
            lines.append(f"- **{ins['title']}**" + (f"（{ins['type']}" if ins["type"] else "") + (f"/{ins['subject']}" if ins["subject"] else "") + ("）" if ins["type"] or ins["subject"] else ""))
            if ins["content"] and ins["content"] != ins["title"]:
                lines.append(f"  - {ins['content'][:120]}")
        lines.append("")
    else:
        lines.append("## 🧠 今日洞察\n\n（今日暂无沉淀洞察）\n")
    if tasks:
        lines.append("## ✅ 任务摘要")
        for tk in tasks[:25]:
            lines.append(f"- [{tk['mark']}] {tk['title']}" + (f"（{tk['status']}）" if tk["status"] else ""))
        lines.append("")
    else:
        lines.append("## ✅ 任务摘要\n\n（今日暂无任务变动）\n")
    lines.append("---")
    lines.append(f"相关：[[知识库]] · [[个人驾驶舱]] · 来源飞书多维表格 [[{ds}|系统表]]")
    body = "\n".join(lines)

    path = f"/vault/{DAILY_DIR}/{ds}.md"
    if not apply:
        print(f"  [dry-run] 将写入 {path}（{len(body)} 字符）")
        return True, body
    ok, resp = obs_api("PUT", path, body)
    if ok:
        print(f"  ✅ 已写入 {path}")
        _log_event("Obsidian每日笔记", f"{ds} 洞察{len(insights)}条/任务{len(tasks)}条")
        return True, f"每日笔记 {ds} 已写入 Obsidian（洞察{len(insights)}条/任务{len(tasks)}条）"
    print(f"  ❌ 写入失败: {resp}")
    return False, resp


# ============ 2) MASTERED 卡片回流 ============
def card_archive(apply=True):
    print("=== MASTERED 卡片回流 Obsidian 知识库 ===")
    archived = _load_archived()
    cards = []
    for it in v15.list_records(T_CARD, max_pages=60):
        f = it.get("fields", {})
        status = _select_text(f.get("卡片状态"))
        if status not in ("MASTERED",):
            continue
        rid = it.get("record_id")
        if rid in archived:
            continue
        q = v15.cell_text(f.get("卡片问题正面") or "")
        a = v15.cell_text(f.get("标准答案背面") or "")
        subject = _select_text(f.get("科目")) or "其他"
        tags = _multi_text(f.get("标签")) or ["知识库"]
        source = v15.cell_text(f.get("来源") or "")
        if not q:
            continue
        cards.append({"rid": rid, "q": q, "a": a, "subject": subject, "tags": tags, "source": source})
    print(f"  待回流 MASTERED 卡片: {len(cards)}")

    ok_n = 0
    for c in cards:
        lines = []
        lines.append("---")
        lines.append(f"subject: {c['subject']}")
        lines.append("tags: [" + ", ".join(c["tags"][:5]) + "]")
        lines.append(f"source: {c['source'] or '学习卡片'}")
        lines.append(f"archived: {date.today().isoformat()}")
        lines.append("---")
        lines.append(f"# {c['q']}")
        lines.append("")
        lines.append(c["a"] if c["a"] else "（无答案）")
        lines.append("")
        lines.append("---")
        lines.append("> 来自学习卡片 MASTERED 归档 · [[学习卡片]]")
        body = "\n".join(lines)
        path = f"/vault/{KB_DIR}/{_norm_title(c['subject'])}/{_norm_title(c['q'])}.md"
        if not apply:
            print(f"  [dry-run] {path}")
            continue
        ok, resp = obs_api("PUT", path, body)
        if ok:
            ok_n += 1
            archived.add(c["rid"])
            print(f"  ✅ {path}")
        else:
            print(f"  ❌ {path} -> {resp[:120]}")
    if apply:
        _save_archived(archived)
        if ok_n:
            _log_event("Obsidian卡片回流", f"MASTERED 卡片回流 {ok_n} 张")
        print(f"  完成: 回流 {ok_n} 张（累计已回流 {len(archived)}）")
        return ok_n
    return len(cards)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily", action="store_true")
    ap.add_argument("--cards", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true", help="实际写入（默认 dry-run）")
    args = ap.parse_args()

    if args.all or (args.daily and args.cards):
        daily_note(apply=args.apply)
        card_archive(apply=args.apply)
    elif args.daily:
        daily_note(apply=args.apply)
    elif args.cards:
        card_archive(apply=args.apply)
    else:
        daily_note(apply=False)
        card_archive(apply=False)


if __name__ == "__main__":
    main()
