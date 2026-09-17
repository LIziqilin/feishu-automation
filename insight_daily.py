#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
insight_daily.py - 每日三察洞察日报（西安天气 + 社会规律 + 自然规律 + 人性洞察）
============================================================
早报/晚报增强模块（V44）：把"行情/RSS"类资讯替换为更有认知增量的每日洞察：
  1. 🌤 西安天气（wttr.in）
  2. 🧭 社会规律洞察：从当日资讯/社会运行规律提炼 1 条
  3. 🌿 自然规律洞察：结合时令/节气/天气现象提炼 1 条
  4. 🧠 人性洞察：人性通则结合当日场景 1 条

双模式：
  - llm（本地）：GLM 代理 127.0.0.1:3003 生成（更贴合当日真实资讯/天气）
  - rules（云端 GitHub Actions）：确定性规律库（时令节气+规律池），零 LLM 依赖

洞察沉淀（"越用越聪明"闭环）：
  - 每条洞察写入多维表格洞察表（INSIGHT_TABLE），供后续 insight_to_card 沉淀为知识卡片

用法：
  python insight_daily.py                     # 生成并打印（本地自动 llm 模式）
  python insight_daily.py --mode rules        # 强制规则模式（云端）
  python insight_daily.py --push              # 推送到总控群
  python insight_daily.py --json              # JSON 输出
"""
import os
import sys
import json
import subprocess
import urllib.request
import re
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
if os.environ.get("LARK_API_MODE") == "1":
    # 云端零依赖模式：常量内联/环境变量，不 import v19_integration（其依赖 config_local 云端缺失）
    BASE_TOKEN = os.environ.get("FEISHU_BASE_TOKEN", "")
    INSIGHT_TABLE = "tblaqKBl87V9C0q1"
    TARGET_CHAT_ID = os.environ.get("CHAT_ID", "oc_1fe154e172ab04622b7ffa810ac172bc")
    EVENT_LOG_TABLE = "tblPreh1ipB9LQpf"
else:
    from v19_integration import BASE_TOKEN, INSIGHT_TABLE, TARGET_CHAT_ID, EVENT_LOG_TABLE

GLM_URL = "http://127.0.0.1:3003/v4/chat/completions"
CITY = os.environ.get("CITY", "Xian")
CITY_CN = "西安"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def run_cmd(cmd, timeout=90):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, shell=False)
        out = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        err = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return r.returncode == 0, out, err
    except Exception as e:
        return False, "", str(e)


def api_send_message(text):
    '''云端直连飞书 API 发消息（零 lark-cli/npm 依赖，凭据走环境变量）'''
    app_id = os.environ.get("LARK_APP_ID", "")
    app_secret = os.environ.get("LARK_APP_SECRET", "")
    if not (app_id and app_secret):
        return False, "缺少 LARK_APP_ID/LARK_APP_SECRET 环境变量"
    try:
        body = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode("utf-8")
        req = urllib.request.Request(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            tresp = json.loads(resp.read().decode("utf-8", errors="replace"))
        if tresp.get("code") != 0:
            return False, "token接口失败 code={} msg={}".format(tresp.get("code"), tresp.get("msg"))
        tok = tresp["tenant_access_token"]
        payload = json.dumps({
            "receive_id": TARGET_CHAT_ID,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        }).encode("utf-8")
        req2 = urllib.request.Request(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            data=payload, headers={"Content-Type": "application/json",
                                   "Authorization": "Bearer " + tok}, method="POST")
        with urllib.request.urlopen(req2, timeout=30) as resp:
            res = json.loads(resp.read().decode("utf-8", errors="replace"))
        return res.get("code") == 0, json.dumps(res, ensure_ascii=False)[:300]
    except Exception as e:
        return False, str(e)


def send_message(text):
    if os.environ.get("LARK_API_MODE") == "1":
        return api_send_message(text)
    cmd = ["lark-cli", "im", "+messages-send", "--chat-id", TARGET_CHAT_ID, "--as", "user", "--text", text]
    return run_cmd(cmd)


def http_get(url, timeout=12):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


# ---------- 数据源 ----------
def fetch_weather():
    try:
        j = json.loads(http_get("https://wttr.in/{}?format=j1".format(CITY)))
    except Exception:
        return "西安 天气数据暂不可用", 20
    cur = j["current_condition"][0]
    desc = cur["weatherDesc"][0]["value"]
    return "{} {}°C {} 湿度{}% 风{}{}km/h".format(
        CITY_CN, cur["temp_C"], desc, cur["humidity"],
        cur["winddir16Point"], cur["windspeedKmph"]), cur["temp_C"]


def fetch_news_titles(limit=5):
    out = []
    for url in ("https://sspai.com/feed", "https://36kr.com/feed"):
        try:
            xml = http_get(url)
            items = re.findall(r"<item>.*?<title>(.*?)</title>", xml, re.S)
            for t in items[:limit]:
                clean = re.sub(r"<!\[CDATA\[|\]\]>", "", t).strip()
                if clean and len(out) < limit:
                    out.append(clean[:50])
        except Exception:
            continue
    return out


# ---------- 规则模式规律库 ----------
SOLAR_TERMS = [
    (1, 5, "小寒"), (1, 20, "大寒"), (2, 4, "立春"), (2, 19, "雨水"),
    (3, 5, "惊蛰"), (3, 20, "春分"), (4, 5, "清明"), (4, 20, "谷雨"),
    (5, 5, "立夏"), (5, 21, "小满"), (6, 6, "芒种"), (6, 21, "夏至"),
    (7, 7, "小暑"), (7, 23, "大暑"), (8, 7, "立秋"), (8, 23, "处暑"),
    (9, 7, "白露"), (9, 23, "秋分"), (10, 8, "寒露"), (10, 23, "霜降"),
    (11, 7, "立冬"), (11, 22, "小雪"), (12, 7, "大雪"), (12, 22, "冬至"),
]

NATURE_RULES = [
    "昼夜温差拉大时，植物会把养分从叶片回流到根部——外界环境越收缩，生命越向内沉淀，人也一样：压力期正是积累期",
    "水往低处流不是水弱，是势能换动能——顺势而为比逆流硬扛更省力，且走得更远",
    "秋天果实成熟前，果树会先停止抽新枝——懂得'停止生长新枝'，才能把养分集中给果实",
    "候鸟迁徙从不靠蛮力，靠的是对气候信号的敏感——真正的高手提前感知趋势，而不是等到冷了再动",
    "竹子前四年几乎不长，第五年每天疯长——复利与扎根，前期沉默越久，后期爆发越猛",
    "蚁群遇到障碍会留下信息素标记死路，后来的蚂蚁自动绕开——组织最大的成本是重复踩同一个坑",
]

SOCIAL_RULES = [
    "所有制度的本质都是激励结构：谁受益、谁买单、谁背锅，三个问题看清一件事的底层逻辑",
    "信息差红利消失的速度，取决于传播工具的扩散速度——能用工具降低的摩擦，早晚会被别人降低",
    "任何系统给的正反馈都有滞后：今天种下的动作，往往两周后才看见结果，熬过滞后区就是分水岭",
    "成本低到可忽略的行动最容易坚持：把'每天学1小时'改成'每天翻1页'，坚持率完全不同",
    "选择比努力重要的前提是：你有能力看见选项——信息获取能力才是第一生产力",
    "所有'突然'的成功，都是此前长期积累的必然兑现——没有人能凭空起飞，只有准备好了的起飞",
]

HUMAN_RULES = [
    "人更容易记住'被否定'而不是'被认可'——批评要就事论事，表扬要具体到行为，否则前者伤人后者无效",
    "损失厌恶：同样100元，丢了的心痛约等于捡到的快乐的两倍——做决策时，先问'我可能失去什么'",
    "人在压力下会退回最熟练的模式，而不是最正确的模式——所以关键场景要提前演练，而不是临场发挥",
    "确认偏误：人只会寻找支持自己观点的证据——对抗它的方法是主动找'反例'，而不是找'更多例证'",
    "即时反馈让人上瘾，延迟反馈让人成长——刷手机和学习的区别就在反馈时差上",
    "人高估自己一天能做的事，低估自己一年能做的事——把目标放在一年尺度上，焦虑会少一半",
]


def current_term():
    now = datetime.now()
    best, dist = "秋分", 999
    for m, d, name in SOLAR_TERMS:
        cand = datetime(now.year, m, d)
        if cand < now:
            dd = (now - cand).days
        else:
            dd = 365 - (cand - now).days
        if abs(dd - 0) < dist and dd <= 15:
            dist = abs(dd)
            best = name
    return best


def day_seed():
    """每日轮换索引（稳定：同一天同一选择）"""
    return datetime.now().strftime("%Y%m%d")


def rules_insights(weather_str, temp):
    seed = int(day_seed())
    nature = NATURE_RULES[seed % len(NATURE_RULES)]
    social = SOCIAL_RULES[(seed // 3) % len(SOCIAL_RULES)]
    human = HUMAN_RULES[(seed // 7) % len(HUMAN_RULES)]
    term = current_term()
    return {
        "term": term,
        "nature": nature,
        "social": social,
        "human": human,
        "weather": weather_str,
    }


# ---------- LLM 模式 ----------
def glm_chat(prompt, max_tokens=900):
    body = {
        "model": "glm-4-flash",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    req = urllib.request.Request(
        GLM_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def llm_insights(weather_str, news):
    news_txt = "\n".join("· " + n for n in news) or "（今日无新闻样本）"
    prompt = (
        "你是洞察力极强的认知教练。今天是{}，西安天气：{}。\n"
        "今日资讯样本：\n{}\n\n"
        "请严格按以下三行格式输出（每行以编号开头，内容50-90字，不得出现其他行、不得重复标签）：\n"
        "1. 社会规律：从资讯或社会运行中提炼一条可迁移到个人成长的规律，必须具体，结合某个真实现象\n"
        "2. 自然规律：结合当前季节/节气/天气现象提炼一条自然启示，画面感要强\n"
        "3. 人性洞察：基于人性通则、今天最值得提醒自己的一条，直指行动\n"
        "硬性要求：不得空泛说'要学习/要坚持/要努力'，必须给出可操作的迁移结论。".format(
            datetime.now().strftime("%m月%d日"), weather_str, news_txt))
    try:
        out = glm_chat(prompt)
        social = nature = human = None
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("1.") or line.startswith("1）") or "社会规律" in line[:14]:
                social = re.sub(r"^[\d\.）\s]*[社][会][规][律][：:]\s*", "", line.split("社会规律：")[-1]) if "社会规律" in line else re.sub(r"^[\d\.）\s]*", "", line)
            elif line.startswith("2.") or line.startswith("2）") or "自然规律" in line[:14]:
                nature = line.split("自然规律：")[-1] if "自然规律" in line else re.sub(r"^[\d\.）\s]*", "", line)
            elif line.startswith("3.") or line.startswith("3）") or "人性洞察" in line[:14]:
                human = line.split("人性洞察：")[-1] if "人性洞察" in line else re.sub(r"^[\d\.）\s]*", "", line)
        # 清掉可能残留的标签前缀
        for i, x in ((0, social), (1, nature), (2, human)):
            if x:
                x = re.sub(r"^[\d\.）\s]*", "", x)
                x = re.sub(r"^【?[社自人][会然性][规洞][律察]】?[：:]?\s*", "", x)
                if i == 0:
                    social = x
                elif i == 1:
                    nature = x
                else:
                    human = x
        if not (social and nature and human):
            raise ValueError("解析不完整")
        return {
            "term": current_term(),
            "nature": nature.strip(),
            "social": social.strip(),
            "human": human.strip(),
            "weather": weather_str,
        }
    except Exception:
        return None


# ---------- 报告组装 ----------
def build_report(mode="llm"):
    weather_str, temp = fetch_weather()
    news = fetch_news_titles() if mode == "llm" else []
    data = llm_insights(weather_str, news) if mode == "llm" else rules_insights(weather_str, temp)
    if mode == "llm" and data is None:
        data = rules_insights(weather_str, temp)

    L = [
        "🔍 今日三察 | {}".format(datetime.now().strftime("%Y-%m-%d %A")),
        "🌤 西安天气：{}".format(data["weather"]),
        "（{}）".format(data["term"]),
        "",
        "🧭 社会规律",
        "  " + data["social"],
        "",
        "🌿 自然规律",
        "  " + data["nature"],
        "",
        "🧠 人性洞察",
        "  " + data["human"],
    ]
    return "\n".join(L), data


# ---------- 洞察沉淀 ----------
def sink_insights(data):
    """三条洞察写入洞察表（越用越聪明：沉淀为可学习知识）"""
    ts_ms = int(datetime.now().timestamp() * 1000)
    today = datetime.now().strftime("%Y-%m-%d")
    rows = [
        {"洞察标题": "社会规律·{}".format(today), "内容": data["social"],
         "洞察类型": "知识沉淀", "类型": "洞察", "标签": ["认知升级", "商业洞察"],
         "关联科目": ["通用知识"], "来源": "规律洞察日报", "洞察日期": ts_ms, "整理日期": ts_ms},
        {"洞察标题": "自然规律·{}".format(today), "内容": data["nature"],
         "洞察类型": "知识沉淀", "类型": "洞察", "标签": ["认知升级"],
         "关联科目": ["通用知识"], "来源": "规律洞察日报", "洞察日期": ts_ms, "整理日期": ts_ms},
        {"洞察标题": "人性洞察·{}".format(today), "内容": data["human"],
         "洞察类型": "知识沉淀", "类型": "洞察", "标签": ["认知升级", "决策反思"],
         "关联科目": ["通用知识"], "来源": "规律洞察日报", "洞察日期": ts_ms, "整理日期": ts_ms},
    ]
    payload = {"create_records": rows}
    jf = os.path.join(SCRIPT_DIR, "_tmp_insight_sink.json")
    with open(jf, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    cmd = ["lark-cli", "base", "+record-batch-create", "--base-token", BASE_TOKEN,
           "--table-id", INSIGHT_TABLE, "--json", "@" + jf, "--as", "user", "--format", "json"]
    ok, out, err = run_cmd(cmd)
    if os.path.exists(jf):
        os.remove(jf)
    return ok, err


def write_event_log(message):
    ts_ms = int(datetime.now().timestamp() * 1000)
    payload = {"create_records": [{
        "event_id": "ins_{}".format(datetime.now().strftime("%Y%m%d%H%M%S%f")),
        "timestamp": ts_ms,
        "message": message[:1900],
        "severity": "INFO",
        "source": "system",
        "log_type": "INSTRUCTION",
    }]}
    jf = os.path.join(SCRIPT_DIR, "_tmp_insight_log.json")
    with open(jf, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    cmd = ["lark-cli", "base", "+record-batch-create", "--base-token", BASE_TOKEN,
           "--table-id", EVENT_LOG_TABLE, "--json", "@" + jf, "--as", "user", "--format", "json"]
    ok, _, err = run_cmd(cmd)
    if os.path.exists(jf):
        os.remove(jf)
    return ok, err


def main():
    args = sys.argv[1:]
    mode = "rules" if "--mode" in args and args[args.index("--mode") + 1] == "rules" else "llm"
    push = "--push" in args
    as_json = "--json" in args
    no_sink = "--no-sink" in args

    report, data = build_report(mode)
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=1))
        return

    print(report)
    if push:
        ok, _, err = send_message(report)
        print("\n[推送] " + ("OK" if ok else "失败：" + err[:160]))
        if not ok:
            sys.exit(1)
        if not no_sink:
            s_ok, s_err = sink_insights(data)
            print("[洞察沉淀] " + ("OK（3条已入洞察表）" if s_ok else "失败：" + s_err[:80]))
            l_ok, _ = write_event_log("三察洞察日报｜模式={}".format(mode))
            print("[事件日志] " + ("OK" if l_ok else "失败"))


if __name__ == "__main__":
    main()
