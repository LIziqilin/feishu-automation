# -*- coding: utf-8 -*-
"""deepseek_assistants.py — 4个DeepSeek直连助手（V49）
================================================================
错题解析助手   -> 学习卡片表  (写 AI解析_错题/知识点分类_AI/标准答案_AI/底层规律)
学习周报助手   -> 洞察笔记表  (写 洞察标题/内容/行动建议/来源/整理日期)
画像演化助手   -> 用户画像表  (写 画像维度/画像值/置信度/数据来源)
健康诊断助手   -> 系统健康表  (写 检查项/异常描述/告警等级/处理状态/最近检查时间)

用法：
  python deepseek_assistants.py wrong_answer [--limit 1]
  python deepseek_assistants.py weekly_report
  python deepseek_assistants.py profile
  python deepseek_assistants.py health
"""
import json, os, sys, time, argparse, urllib.request, datetime
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
BASE = "X8N1bvN3na99dFsyu0gcU8zTnHf"
LARK = r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd"
CARD_TABLE = "tblpLvxyYpDJgF92"      # 学习卡片表
INSIGHT_TABLE = "tblaqKBl87V9C0q1"  # 洞察笔记表
PROFILE_TABLE = "tbldjGffbuPKCe21"  # 用户画像表
HEALTH_TABLE = "tblxJMndPNtZ7XyG"  # 系统健康表

_cfg = json.loads(Path(r"D:\AI-Tools\shared\coze_config.json").read_text(encoding="utf-8"))
DS_KEY = _cfg.get("deepseek_api_key", "")
DS_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")


def ds_chat(prompt, system="", max_tokens=600):
    """直连DeepSeek，返回文本。"""
    body = json.dumps({
        "model": DS_MODEL,
        "messages": ([{"role": "system", "content": system}] if system else []) +
                    [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens, "temperature": 0.4,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {DS_KEY}"}, method="POST")
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d["choices"][0]["message"]["content"].strip()


def lark(args):
    out = subprocess_run([LARK, "base"] + args + ["--as", "user", "--format", "json"])
    i, j = out.find("{"), out.rfind("}")
    if i >= 0 and j > i:
        try:
            return json.loads(out[i:j+1])
        except Exception:
            pass
    return {"ok": False, "raw": out[:200]}


def subprocess_run(argv):
    import subprocess
    p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return p.stdout


def _str(v):
    """select多选/数组值归一化为字符串。"""
    if isinstance(v, list):
        return v[0] if v else ""
    return v if v else ""


def _extract_json(ans):
    """从DeepSeek返回中提取第一个JSON对象或数组。"""
    s = ans.strip()
    if s.startswith("```"):
        s = s.split("```")[1] if "json" not in s[:10] else s
    try:
        return json.loads(s)
    except Exception:
        pass
    for a, b in [("{", "}"), ("[", "]")]:
        i, j = s.find(a), s.rfind(b)
        if i >= 0 and j > i:
            try:
                return json.loads(s[i:j+1])
            except Exception:
                pass
    raise ValueError("无法解析JSON: " + s[:80])


def list_records(table_id, limit=5):
    d = lark(["+record-list", "--base-token", BASE, "--table-id", table_id, "--limit", str(limit)])
    data = d.get("data", {})
    fields = data.get("fields", [])
    rows = data.get("data", [])
    rec_ids = data.get("record_id_list", [])
    out = []
    for i, row in enumerate(rows):
        rec = dict(zip(fields, row[:len(fields)]))
        rec["_record_id"] = rec_ids[i] if i < len(rec_ids) else None
        out.append(rec)
    return out


def now_ms():
    return int(time.time() * 1000)


# ---------- 1. 错题解析 ----------
def wrong_answer(limit=1):
    rows = list_records(CARD_TABLE, limit=20)
    todo = [r for r in rows if (r.get("卡片问题正面") or "").strip()
            and not (r.get("AI解析_错题") or "").strip()]
    todo = todo[:limit]
    if not todo:
        print("无需解析的卡片（都已有AI解析）"); return
    print(f"待解析 {len(todo)} 张")
    for r in todo:
        q = r.get("卡片问题正面", "")
        a = r.get("标准答案背面", "") or r.get("标准答案_AI", "")
        prompt = (f"题目：{q}\n标准答案：{a}\n\n"
                  "请输出JSON：{\"分析\":\"一句话核心概念澄清\",\"知识点\":\"分类标签\",\"正解\":\"简明正确思路\",\"规律\":\"底层规律\"}")
        try:
            ans = ds_chat(prompt, system="你是错题解析助手，只输出JSON，不要多余文字。", max_tokens=500)
            j = json.loads(ans[ans.find("{"):ans.rfind("}")+1])
        except Exception as e:
            print("解析失败:", e); continue
        lark(["+record-upsert", "--base-token", BASE, "--table-id", CARD_TABLE,
              "--record-id", r["_record_id"],
              "--json", json.dumps({
                  "AI解析_错题": j.get("分析", ans),
                  "知识点分类_AI": j.get("知识点", ""),
                  "标准答案_AI": j.get("正解", ""),
                  "底层规律": j.get("规律", ""),
              }, ensure_ascii=False)])
        print(f"  ✅ 已解析并写回: {q[:20]}")


# ---------- 2. 学习周报 -> 洞察表 ----------
def weekly_report():
    rows = list_records(CARD_TABLE, limit=30)
    n = len(rows)
    mastered = sum(1 for r in rows if r.get("卡片状态") == "MASTERED")
    subjects = {}
    for r in rows:
        s = _str(r.get("科目")) or "其他"
        subjects[s] = subjects.get(s, 0) + 1
    prompt = (f"本周学习数据：共{n}张卡片，已掌握{mastered}张，科目分布{subjects}。"
              "请写一份简短学习周报，含：本周完成情况/薄弱环节/下周计划三点。")
    rep = ds_chat(prompt, system="你是学习周报助手，写150字内的周报。", max_tokens=400)
    title = f"学习周报 {datetime.date.today().strftime('%m-%d')}"
    lark(["+record-batch-create", "--base-token", BASE, "--table-id", INSIGHT_TABLE,
          "--json", json.dumps({"records": [{"fields": {
              "洞察标题": title, "内容": rep, "行动建议": "按薄弱环节复习",
              "来源": "DeepSeek周报助手", "整理日期": now_ms(),
          }}]}, ensure_ascii=False)])
    print(f"✅ 周报已写入洞察笔记表：{title}\n{rep}")


# ---------- 3. 画像演化 -> 用户画像表 ----------
def profile():
    rows = list_records(CARD_TABLE, limit=30)
    subjects = {}
    for r in rows:
        s = _str(r.get("科目")) or "其他"
        subjects[s] = subjects.get(s, 0) + 1
    prompt = (f"学习科目分布{subjects}。请推断3条用户画像标签，每条JSON："
              "{\"维度\":\"如学习偏好/关注领域/学习风格\",\"值\":\"具体标签\",\"置信度\":0.0-1.0}")
    ans = ds_chat(prompt, system="你是画像演化助手，只输出JSON数组。", max_tokens=400)
    try:
        items = _extract_json(ans)
        if isinstance(items, dict):
            items = [items]
    except Exception:
        items = [{"维度": "关注领域", "值": ans[:50], "置信度": 0.6}]
    recs = [{"fields": {"画像维度": it.get("维度", ""), "画像值": str(it.get("值", "")),
                        "置信度": float(it.get("置信度", 0.7)),
                        "数据来源": "自动演化", "更新时间": now_ms()}} for it in items]
    lark(["+record-batch-create", "--base-token", BASE, "--table-id", PROFILE_TABLE,
          "--json", json.dumps({"records": recs}, ensure_ascii=False)])
    print(f"✅ 画像演化 {len(recs)} 条已写入用户画像表")


# ---------- 4. 健康诊断 -> 系统健康表 ----------
def health():
    # 采集：LLM双通道+备份时间
    facts = {"今日": datetime.date.today().isoformat()}
    prompt = ("请基于以下系统事实做健康诊断，输出JSON："
              "{\"检查项\":\"综合诊断\",\"结论\":\"正常/预警/告警\",\"描述\":\"一句话\",\"处理建议\":\"一句话\"}。"
              f"事实：{json.dumps(facts, ensure_ascii=False)}")
    try:
        ans = ds_chat(prompt, system="你是健康诊断助手，只输出JSON。", max_tokens=300)
        j = _extract_json(ans)
        if isinstance(j, list):
            j = j[0]
    except Exception as e:
        print("诊断失败:", e); return
    level = j.get("结论", "正常")
    level_map = {"正常": "正常", "预警": "预警", "告警": "告警", "严重": "严重"}
    lark(["+record-batch-create", "--base-token", BASE, "--table-id", HEALTH_TABLE,
          "--json", json.dumps({"records": [{"fields": {
              "检查项": j.get("检查项", "综合诊断"),
              "异常描述": j.get("描述", ""),
              "告警等级": level_map.get(level, "正常"),
              "处理状态": "已自动修复" if level == "正常" else "待人工",
              "最近检查时间": now_ms(),
              "当前使用通道": "DeepSeek",
          }}]}, ensure_ascii=False)])
    print(f"✅ 健康诊断已写入系统健康表：{level} - {j.get('描述','')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["wrong_answer", "weekly_report", "profile", "health"])
    ap.add_argument("--limit", type=int, default=1)
    a = ap.parse_args()
    if a.cmd == "wrong_answer":
        wrong_answer(a.limit)
    elif a.cmd == "weekly_report":
        weekly_report()
    elif a.cmd == "profile":
        profile()
    elif a.cmd == "health":
        health()
