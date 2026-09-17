#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fetch_external_data.py - 外部数据抓取（行情/RSS/天气）L3进阶
============================================================
满足任务【P3】GitHub Actions/云函数抓外部数据（L3进阶：行情/RSS/天气）。

抓取：
  1. 行情：腾讯行情 API（沪深300/深证成指/创业板指/恒生指数）— 免费、无 key、GBK 编码
  2. 天气：wttr.in（西安，免费、无 key，JSON）
  3. RSS：36氪 / 少数派 — 免费、无 key，取前 3 条

输出：
  - 汇总文本（--push 推送到总控群）
  - 写系统事件日志（EVENT_LOG_TABLE，source=external，log_type=INSTRUCTION）

双模式：
  - 本地：lark-cli --as user（OAuth 用户身份）
  - GitHub Actions：env 注入 FEISHU_APP_ID/FEISHU_APP_SECRET/BASE_TOKEN/CHAT_ID → --as bot
  云端零 Python 第三方依赖（仅 urllib 标准库）。

用法：
  python fetch_external_data.py               # 抓取并打印
  python fetch_external_data.py --push        # 抓取并推送总控群
  python fetch_external_data.py --json        # JSON 输出
  python fetch_external_data.py --no-rss      # 跳过 RSS（网络受限时）
"""
import os
import sys
import json
import urllib.request
from datetime import datetime

# ---------- 常量 ----------
CHAT_ID = os.environ.get("CHAT_ID", "oc_1fe154e172ab04622b7ffa810ac172bc")
BASE_TOKEN = os.environ.get("BASE_TOKEN") or os.environ.get("FEISHU_BASE_TOKEN", "")
EVENT_LOG_TABLE = "tblPreh1ipB9LQpf"
LARK_APP_ID = os.environ.get("LARK_APP_ID") or os.environ.get("FEISHU_APP_ID", "")
LARK_APP_SECRET = os.environ.get("LARK_APP_SECRET") or os.environ.get("FEISHU_APP_SECRET", "")
CITY = os.environ.get("CITY", "Xian")

# 本地兜底：无 env 时从 config_local 取 BASE_TOKEN（云端仅 env，兼容双模式）
if not BASE_TOKEN:
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from config_local import BASE_TOKEN as _BT
        BASE_TOKEN = _BT
    except Exception:
        pass

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

INDICES = {
    "沪深300": "sh000300",
    "深证成指": "sz399001",
    "创业板指": "sz399006",
    "恒生指数": "hkHSI",
}


def http_get(url, timeout=12, decode=None):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    if decode:
        return raw.decode(decode, errors="replace")
    return raw.decode("utf-8", errors="replace")


# ---------- 行情 ----------
def fetch_market():
    """腾讯行情：~分隔字段 [1]=名称 [2]=代码 [3]=现价 [4]=昨收 [5]=今开 等"""
    codes = ",".join(INDICES.values())
    txt = http_get("https://qt.gtimg.cn/q=" + codes, decode="gbk")
    rows = []
    for line in txt.strip().split(";"):
        line = line.strip()
        if not line or "=" not in line:
            continue
        parts = line.split("=", 1)[1].strip('"').split("~")
        if len(parts) < 6:
            continue
        name, price, yclose = parts[1], float(parts[3]), float(parts[4])
        chg = (price - yclose) / yclose * 100 if yclose else 0.0
        arrow = "▲" if chg >= 0 else "▼"
        rows.append("{} {} {:.2f} ({}{:+.2f}%)".format(name, price, chg, arrow, chg))
    return rows


# ---------- 天气 ----------
def fetch_weather():
    j = json.loads(http_get("https://wttr.in/{}?format=j1".format(CITY)))
    cur = j["current_condition"][0]
    desc = cur["weatherDesc"][0]["value"]
    return "{} {}°C {} 湿度{}% 风{}{}km/h".format(
        CITY, cur["temp_C"], desc, cur["humidity"],
        cur["winddir16Point"], cur["windspeedKmph"])


# ---------- RSS ----------
def fetch_rss(url, limit=3):
    import re
    xml = http_get(url)
    items = re.findall(r"<item>.*?<title>(.*?)</title>.*?<pubDate>(.*?)</pubDate>", xml, re.S)
    out = []
    for title, pub in items[:limit]:
        clean = re.sub(r"<!\[CDATA\[|\]\]>", "", title).strip()
        out.append("· {}（{}）".format(clean[:40], pub[:16]))
    return out


def fetch_all(include_rss=True):
    result = {"time": datetime.now().strftime("%Y-%m-%d %H:%M"), "market": [], "weather": "", "rss": []}
    try:
        result["market"] = fetch_market()
    except Exception as e:
        result["market"] = ["行情抓取失败：{}".format(str(e)[:60])]
    try:
        result["weather"] = fetch_weather()
    except Exception as e:
        result["weather"] = "天气抓取失败：{}".format(str(e)[:60])
    if include_rss:
        for name, url in (("36氪", "https://36kr.com/feed"), ("少数派", "https://sspai.com/feed")):
            try:
                items = fetch_rss(url, limit=3)
                if items:
                    result["rss"].append("【{}】".format(name))
                    result["rss"].extend(items)
            except Exception as e:
                result["rss"].append("【{}】抓取失败：{}".format(name, str(e)[:50]))
    return result


def build_report(r):
    L = [
        "🌐 外部数据早报/晚报（{}）".format(r["time"]),
        "📈 行情",
    ]
    L.extend("  " + m for m in r["market"])
    L.append("🌤 天气（{}）".format(CITY))
    L.append("  " + r["weather"])
    if r["rss"]:
        L.append("📰 资讯")
        L.extend("  " + x for x in r["rss"])
    return "\n".join(L)


# ---------- lark 调用 ----------
def run_cmd(cmd, timeout=90):
    try:
        r = __import__("subprocess").run(cmd, capture_output=True, timeout=timeout, shell=False)
        out = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        err = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return r.returncode == 0, out, err
    except Exception as e:
        return False, "", str(e)


def send_message(text):
    if LARK_APP_ID and LARK_APP_SECRET:
        cmd = ["lark-cli", "im", "+messages-send", "--chat-id", CHAT_ID, "--as", "bot", "--text", text]
    else:
        cmd = ["lark-cli", "im", "+messages-send", "--chat-id", CHAT_ID, "--as", "user", "--text", text]
    return run_cmd(cmd)


def write_event_log(message):
    if not BASE_TOKEN:
        return False, "", "no BASE_TOKEN"
    import subprocess
    ts_ms = int(datetime.now().timestamp() * 1000)
    payload = {"create_records": [{
        "event_id": "ext_{}".format(datetime.now().strftime("%Y%m%d%H%M%S%f")),
        "timestamp": ts_ms,
        "message": message[:1900],
        "severity": "INFO",
        "source": "system",
        "log_type": "INSTRUCTION",
    }]}
    jf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp_ext_log.json")
    with open(jf, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    cmd = ["lark-cli", "base", "+record-batch-create", "--base-token", BASE_TOKEN,
           "--table-id", EVENT_LOG_TABLE, "--json", "@" + jf, "--as", "user", "--format", "json"]
    ok, out, err = run_cmd(cmd)
    if os.path.exists(jf):
        os.remove(jf)
    return ok, out, err


def main():
    args = sys.argv[1:]
    push = "--push" in args
    as_json = "--json" in args
    include_rss = "--no-rss" not in args

    r = fetch_all(include_rss=include_rss)
    if as_json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return

    report = build_report(r)
    print(report)
    if push:
        ok, _, err = send_message(report)
        print("\n[推送] " + ("OK" if ok else "失败：" + err[:120]))
        log_ok, _, log_err = write_event_log("外部数据抓取｜行情{}项 天气OK RSS{}条".format(
            len(r["market"]), len(r["rss"])))
        print("[事件日志] " + ("OK" if log_ok else "失败：" + log_err[:80]))


if __name__ == "__main__":
    main()
