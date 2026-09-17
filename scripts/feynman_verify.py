#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
费曼输出验证（V15 Phase3 深度学习）
================================
流程：
  1. 选题：用户发「费曼」→ 优先取错题本最薄弱卡；「费曼 关键词」→ 匹配指定卡
  2. 讲解：用户发「讲解：我自己的话...」→ AI 对照标准答案打分
  3. 写回：分数写「费曼打分_AI」，≥60「费曼自检=通过」，<60「未通过」
独立可测：python feynman_verify.py --test
"""
import sys, io, json, re, argparse
sys.path.insert(0, '.')
from v15_features import *

PASS_LINE = 60
# 待讲解卡片的暂存（群内上下文：记录最近一次发起费曼的卡片）
FEYNMAN_PENDING = SCRIPTS_DIR / ".feynman_pending.json"

SYSTEM_PROMPT = """你是费曼学习法教练。学员会用自己的话讲解一个知识点，你要对照【标准答案】判断他是否真正理解，而不是看措辞是否一致。
从三个维度打分（0-100）：
- accuracy 准确性：核心事实/公式是否正确，有无硬伤
- completeness 完整性：是否覆盖标准答案的关键要点
- logic 逻辑性：是否讲清因果/结构，能否让外行听懂
只输出一个JSON对象，不要输出任何多余文字，格式：
{"score":整数,"accuracy":整数,"completeness":整数,"logic":整数,"key_points_hit":"命中的关键点","gaps":"遗漏或错误","feedback":"一句针对性改进建议"}"""

def find_card(keyword=None):
    """选题：有关键词按标题匹配；否则优先错题本最薄弱卡；再否则取LEARNING第一张"""
    cards = list_records(T_CARD)
    pool = []
    for c in cards:
        f = c["fields"]
        pool.append({"record_id": c["record_id"],
                     "title": cell_text(f.get("卡片问题正面")),
                     "answer": cell_text(f.get("标准答案背面")) or cell_text(f.get("标准答案_AI")),
                     "subject": cell_select(f.get("科目")),
                     "status": cell_select(f.get("卡片状态")),
                     "m": cell_num(f.get("掌握度M")),
                     "last": cell_select(f.get("last_result"))})
    if keyword:
        kw = keyword.strip()
        hit = [c for c in pool if kw in c["title"]]
        if hit:
            hit.sort(key=lambda c: c["m"]); return hit[0]
        return None
    # 优先错题（last=不会/模糊），按掌握度升序
    wrong = [c for c in pool if c["last"] in ("不会","模糊")]
    if wrong:
        wrong.sort(key=lambda c: c["m"]); return wrong[0]
    learning = [c for c in pool if c["status"]=="LEARNING"]
    if learning:
        learning.sort(key=lambda c: c["m"]); return learning[0]
    return pool[0] if pool else None

def start(keyword=None):
    card = find_card(keyword)
    if not card:
        return None, "❌ 没找到匹配的卡片"
    FEYNMAN_PENDING.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    msg = (f"🎤 费曼输出验证\n\n"
           f"题目：{card['title']}\n"
           f"科目：{card['subject']}\n\n"
           f"请用你自己的话把它讲清楚（假装讲给一个完全不懂的人），\n"
           f"然后以「讲解：」开头发到群里，我来打分。\n"
           f"例：讲解：我理解这个概念是这样的……")
    return card, msg

def grade(user_explain, card=None):
    """AI对照打分并写回飞书"""
    if card is None and FEYNMAN_PENDING.exists():
        card = json.loads(FEYNMAN_PENDING.read_text(encoding="utf-8"))
    if not card:
        return None, "❌ 请先发「费曼」抽取要讲解的题目"
    if not card.get("answer"):
        return card, "❌ 该卡片没有标准答案，无法对照打分"

    prompt = f"""【题目】{card['title']}
【标准答案】{card['answer'][:1200]}
【学员讲解】{user_explain[:1500]}

请按系统消息要求输出JSON。"""
    raw = llm_chat(prompt, system=SYSTEM_PROMPT, max_tokens=700, temperature=0.2)
    if not raw:
        return card, "⚠️ AI打分服务暂不可用，你的讲解已收到，请稍后再试"
    # 提取JSON（容错模型可能包裹```json）
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return card, f"⚠️ AI返回解析失败，原始内容：{raw[:200]}"
    try:
        r = json.loads(m.group(0))
        score = int(float(r.get("score", 0)))
    except Exception as e:
        return card, f"⚠️ 打分结果解析失败：{e}"

    passed = score >= PASS_LINE
    # 写回学习卡表
    grade_txt = (f"{now_str()} 得分{score}（准{r.get('accuracy')}/全{r.get('completeness')}/逻{r.get('logic')}）"
                 f"｜遗漏：{r.get('gaps','')[:120]}")
    update_record(T_CARD, card["record_id"], {
        "费曼打分_AI": grade_txt,
        "费曼自检": "通过" if passed else "未通过",
    })
    emoji = "✅" if passed else "🔁"
    verdict = "通过，说明你真的懂了" if passed else "未达标，建议对照缺口再讲一遍"
    msg = (f"{emoji} 费曼打分：{score}/100（{verdict}）\n\n"
           f"题目：{card['title']}\n"
           f"准确性 {r.get('accuracy')}　完整性 {r.get('completeness')}　逻辑性 {r.get('logic')}\n"
           f"✔ 命中：{r.get('key_points_hit','—')}\n"
           f"✖ 缺口：{r.get('gaps','—')}\n"
           f"💡 {r.get('feedback','—')}\n\n"
           f"结果已写回学习卡表（费曼自检：{'通过' if passed else '未通过'}）")
    # 通过后清除pending
    if passed and FEYNMAN_PENDING.exists():
        FEYNMAN_PENDING.unlink()
    return card, msg

def _test():
    """离线端到端测试：用CAPEX卡 + 一段讲解跑通AI打分写回（用测试卡避免污染则只打印不写）"""
    card, m1 = start("CAPEX")
    print("=== 选题 ==="); print(m1); print()
    fake = "CAPEX就是买长期资产的钱，比如买设备，一次性花但用好多年要折旧；OPEX是日常运营开销比如电费工资，当期就计入成本。"
    print("=== 模拟讲解 ===\n", fake, "\n")
    card2, m2 = grade(fake, card)
    print("=== 打分结果 ==="); print(m2)

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--start", default=None, help="按关键词选题")
    ap.add_argument("--explain", default=None, help="直接提供讲解文本打分")
    args = ap.parse_args()
    if args.test:
        _test()
    elif args.explain:
        _, m = grade(args.explain); print(m)
    else:
        _, m = start(args.start); print(m)
