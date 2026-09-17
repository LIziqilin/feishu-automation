#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
profile_evolve.py - 用户画像自动演化（"系统越用越懂我"核心增量 V43）
============================================================
从系统行为数据自动更新用户画像表（T_PROFILE=tbldjGffbuPKCe21），
让推荐引擎的兴趣/薄弱/优势维度随使用持续演化，替代"手动录入一次即不变"。

输入证据：
  1. 复习流水表：30 天科目分布、正确率 → 优势/薄弱领域
  2. 卡片表：错题最多的科目（last_result=不会/模糊 计数）
  3. 洞察表：最新洞察内容 → LLM 抽取兴趣关键词 → 兴趣维度
  4. 任务表：完成质量评分≥4 的科目 → 优势领域

输出：
  - 画像表 upsert/update：
      · 优势领域（置信度=正确率×0.7+高分任务比例×0.3）
      · 薄弱领域（置信度=错误率）
      · 自动兴趣（来自洞察 LLM 抽取，置信度=洞察数量权重）
      · 学习画像_自动（摘要文本）
  - 事件日志（source=profile, log_type=AUDIT）
  - 总控群推送摘要（--push）

用法：
  python profile_evolve.py            # 计算并更新画像表
  python profile_evolve.py --dry      # 只打印不写入
  python profile_evolve.py --json     # JSON 输出
"""
import os
import sys
import json
import subprocess
import urllib.request
from datetime import datetime, timedelta
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from v19_integration import (
    BASE_TOKEN, FLOW_TABLE, CARD_TABLE, INSIGHT_TABLE, TASK_TABLE,
    EVENT_LOG_TABLE, TARGET_CHAT_ID,
)

PROFILE_TABLE = "tbldjGffbuPKCe21"
GLM_URL = "http://127.0.0.1:3003/v4/chat/completions"


def run_cmd(cmd, timeout=90):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, shell=False)
        out = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        err = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return r.returncode == 0, out, err
    except Exception as e:
        return False, "", str(e)


def send_message(text):
    cmd = ["lark-cli", "im", "+messages-send", "--chat-id", TARGET_CHAT_ID, "--as", "user", "--text", text]
    return run_cmd(cmd)


def get_all_records(table_id):
    result = []
    offset = 0
    while True:
        cmd = ["lark-cli", "base", "+record-list", "--base-token", BASE_TOKEN,
               "--table-id", table_id, "--as", "user",
               "--limit", "200", "--offset", str(offset), "--format", "json"]
        ok, stdout, _ = run_cmd(cmd)
        if not ok:
            break
        try:
            data = json.loads(stdout).get("data", {})
        except Exception:
            break
        records = data.get("data", [])
        record_ids = data.get("record_id_list", [])
        fields = data.get("fields", [])
        for i, rec in enumerate(records):
            if isinstance(rec, list):
                d = {"_id": record_ids[i] if i < len(record_ids) else ""}
                for j, f in enumerate(fields):
                    if j < len(rec):
                        d[f] = rec[j]
                result.append(d)
        offset += len(records)
        if not data.get("has_more", False) or not records:
            break
    return result


def to_naive(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        ts = v / 1000.0 if v > 1e11 else v
        return datetime.fromtimestamp(ts)
    if isinstance(v, str):
        try:
            d = datetime.fromisoformat(v)
            return d.replace(tzinfo=None) if d.tzinfo else d
        except Exception:
            return None
    return None


def cell_text(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return ",".join(str(x) for x in v)
    return str(v)


def cell_select(v):
    t = cell_text(v)
    return t.strip("[]'\"")


# ---------- LLM 兴趣抽取 ----------
def glm_chat(prompt, max_tokens=400):
    body = {
        "model": "glm-4-flash",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    req = urllib.request.Request(
        GLM_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def extract_interests(insight_texts, fallback):
    """从洞察内容抽取兴趣关键词（逗号分隔）"""
    if not insight_texts:
        return fallback
    prompt = (
        "以下是我近期记录的思考洞察（每条一行）。请提取 3-6 个我最关注的主题领域"
        "（如：酒店工程、项目管理、财商、学习方法、沟通、人性等），"
        "用中文逗号分隔输出，只输出关键词不要解释。\n洞察：\n{}\n".format(
            "\n".join(t[:80] for t in insight_texts[:20])))
    try:
        out = glm_chat(prompt)
        return [x.strip() for x in out.replace("。", ",").replace("，", ",").split(",") if x.strip()][:6]
    except Exception:
        return fallback


# ---------- 证据计算 ----------
def collect_evidence(days=30):
    cutoff = datetime.now() - timedelta(days=days)

    # 1. 流水：科目分布 + 正确率（通过卡片ID关联科目）
    cards = get_all_records(CARD_TABLE)
    card_subject = {}
    for c in cards:
        card_subject[c.get("_id", "")] = cell_select(c.get("科目")) or "未分类"
    card_title_subject = {}
    for c in cards:
        card_title_subject[cell_text(c.get("卡片问题正面"))] = card_subject.get(c.get("_id", ""), "未分类")

    flows = get_all_records(FLOW_TABLE)
    subject_total = Counter()
    subject_correct = Counter()
    for f in flows:
        ts = to_naive(f.get("客户端时间戳") or f.get("创建日期"))
        if ts and ts < cutoff:
            continue
        subj = card_subject.get(cell_text(f.get("卡片ID")), "未分类")
        subject_total[subj] += 1
        if "会" in cell_text(f.get("结果")):
            subject_correct[subj] += 1

    # 2. 卡片表薄弱：last_result=不会/模糊 计数
    card_weak = Counter()
    for c in cards:
        lr = cell_select(c.get("last_result"))
        if lr in ("不会", "模糊"):
            card_weak[card_subject.get(c.get("_id", ""), "未分类")] += 1

    # 3. 洞察：最新 20 条
    insights = get_all_records(INSIGHT_TABLE)
    insight_texts = [cell_text(x.get("内容") or x.get("洞察内容") or "") for x in insights[:20]]
    insight_texts = [t for t in insight_texts if t]

    # 4. 任务：完成质量评分
    tasks = get_all_records(TASK_TABLE)
    high_score_subjects = Counter()
    for t in tasks:
        score = cell_text(t.get("完成质量评分"))
        if score and score not in ("", "[]"):
            try:
                if float(score) >= 4:
                    s = cell_select(t.get("科目"))
                    if s and s != "其他":
                        high_score_subjects[s] += 1
            except Exception:
                pass

    # 优势：正确率 ≥0.6 或高分任务 ≥2
    strength = {}
    for subj, total in subject_total.items():
        if total >= 3:
            acc = subject_correct.get(subj, 0) / total
            if acc >= 0.6:
                strength[subj] = round(acc * 0.7 + min(high_score_subjects.get(subj, 0), 5) / 5 * 0.3, 2)
    for subj, cnt in high_score_subjects.items():
        if cnt >= 2 and subj not in strength:
            strength[subj] = round(min(cnt, 5) / 5 * 0.8 + 0.2, 2)

    # 薄弱：错误率高或错题多
    weakness = {}
    for subj, total in subject_total.items():
        if total >= 3:
            err = 1 - subject_correct.get(subj, 0) / total
            if err >= 0.4:
                weakness[subj] = round(err, 2)
    for subj, cnt in card_weak.items():
        if cnt >= 2:
            weakness[subj] = max(weakness.get(subj, 0), round(min(cnt, 6) / 6, 2))

    # 兴趣
    fallback_interests = [s for s, _ in sorted(strength.items(), key=lambda x: -x[1])[:3]] or ["酒店工程", "认知", "财商"]
    interests = extract_interests(insight_texts, fallback_interests)

    return {
        "strength": dict(sorted(strength.items(), key=lambda x: -x[1])),
        "weakness": dict(sorted(weakness.items(), key=lambda x: -x[1])),
        "interests": interests,
        "flows_total": sum(subject_total.values()),
        "insights_used": len(insight_texts),
        "high_score_tasks": dict(high_score_subjects.most_common(3)),
    }


# ---------- 画像表写入 ----------
def update_profile(ev, dry=False):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    strength_txt = "、".join("{}（{}）".format(k, v) for k, v in ev["strength"].items()) or "待积累"
    weak_txt = "、".join("{}（{}）".format(k, v) for k, v in ev["weakness"].items()) or "暂无"
    interest_txt = "、".join(ev["interests"]) or "待积累"
    summary = "自动演化（{}）：优势={}；薄弱={}；兴趣={}".format(now, strength_txt, weak_txt, interest_txt)

    # 读取画像表现有记录（维度→record_id）
    existing = {}
    for r in get_all_records(PROFILE_TABLE):
        existing[cell_text(r.get("画像维度"))] = r.get("_id", "")

    writes = [
        ("优势领域", strength_txt, min(0.95, 0.5 + 0.1 * len(ev["strength"])), "自动演化"),
        ("薄弱领域", weak_txt, min(0.95, 0.5 + 0.1 * len(ev["weakness"])), "自动演化"),
        ("自动兴趣", interest_txt, min(0.95, 0.5 + 0.05 * len(ev["interests"])), "自动演化"),
        ("学习画像_自动", summary, 0.9, "自动演化"),
    ]
    done = []
    for dim, val, conf, src in writes:
        fields = {"画像维度": dim, "画像值": val[:500], "置信度": conf, "数据来源": src,
                  "更新时间": int(datetime.now().timestamp() * 1000)}
        rid = existing.get(dim, "")
        if dry:
            done.append(("DRY", dim, val[:40]))
            continue
        if rid:
            ok, _, _ = run_cmd(["lark-cli", "base", "+record-upsert", "--base-token", BASE_TOKEN,
                                "--table-id", PROFILE_TABLE, "--record-id", rid,
                                "--json", "@" + _tmp_json(fields), "--as", "user"])
            done.append(("UPDATE" if ok else "FAIL", dim, val[:40]))
        else:
            payload = {"create_records": [fields]}
            ok, _, _ = run_cmd(["lark-cli", "base", "+record-batch-create", "--base-token", BASE_TOKEN,
                                "--table-id", PROFILE_TABLE, "--json", "@" + _tmp_json(payload), "--as", "user"])
            done.append(("CREATE" if ok else "FAIL", dim, val[:40]))
    return done


def _tmp_json(obj):
    import uuid
    p = os.path.join(SCRIPT_DIR, "_tmp_profile_{}.json".format(uuid.uuid4().hex[:6]))
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    return p


def write_event_log(message):
    ts_ms = int(datetime.now().timestamp() * 1000)
    payload = {"create_records": [{
        "event_id": "prof_{}".format(datetime.now().strftime("%Y%m%d%H%M%S%f")),
        "timestamp": ts_ms,
        "message": message[:1900],
        "severity": "INFO",
        "source": "system",
        "log_type": "AUDIT",
    }]}
    jf = _tmp_json(payload)
    cmd = ["lark-cli", "base", "+record-batch-create", "--base-token", BASE_TOKEN,
           "--table-id", EVENT_LOG_TABLE, "--json", "@" + jf, "--as", "user", "--format", "json"]
    ok, _, err = run_cmd(cmd)
    if os.path.exists(jf):
        os.remove(jf)
    return ok, err


def main():
    args = sys.argv[1:]
    dry = "--dry" in args
    as_json = "--json" in args
    push = "--push" in args

    ev = collect_evidence()
    if as_json:
        print(json.dumps(ev, ensure_ascii=False, indent=1, default=str))
        return

    print("=== 画像自动演化 ===")
    print("优势领域：{}".format("、".join("{}（{}）".format(k, v) for k, v in ev["strength"].items()) or "待积累"))
    print("薄弱领域：{}".format("、".join("{}（{}）".format(k, v) for k, v in ev["weakness"].items()) or "暂无"))
    print("自动兴趣：{}".format("、".join(ev["interests"])))
    print("证据：流水{}条 / 洞察{}条 / 高分任务{}类".format(
        ev["flows_total"], ev["insights_used"], len(ev["high_score_tasks"])))

    if dry:
        print("\n[DRY] 未写入画像表")
    else:
        done = update_profile(ev)
        print("\n[画像表写入]")
        for op, dim, val in done:
            print("  {} {} → {}".format(op, dim, val))
        ok, err = write_event_log("画像自动演化｜优势{} 薄弱{} 兴趣{}".format(
            len(ev["strength"]), len(ev["weakness"]), len(ev["interests"])))
        print("[事件日志] " + ("OK" if ok else "失败：" + err[:80]))

        if push:
            msg = ("🧠 画像已自动演化\n优势：{}\n薄弱：{}\n兴趣：{}\n"
                   "（证据：流水{}条/洞察{}条，发「今日推荐」体验更懂你的队列）").format(
                "、".join(ev["strength"]) or "待积累", "、".join(ev["weakness"]) or "暂无",
                "、".join(ev["interests"]), ev["flows_total"], ev["insights_used"])
            send_ok, _, _ = send_message(msg)
            print("[推送] " + ("OK" if send_ok else "失败"))


if __name__ == "__main__":
    main()
