#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
feynman_workflow.py - 费曼学习法工作流（AI大系统 feynman_assist 深度融合版 V13）
============================================================
按需运行（学到新知识点时）：生成费曼四步（大白话复述/一句话定义+类比/卡壳自查/口述提纲），
写入 Obsidian 费曼目录 + 系统事件日志，并推送到总控群。

用法：
  python feynman_workflow.py "CAPEX" "酒店工程" "资本性支出"
  python feynman_workflow.py "什么是倒置购房贷" "财商"
  python feynman_workflow.py --list        # 列出已完成费曼笔记

LLM：走本机 GLM 代理 127.0.0.1:3003（复用 Obsidian/AnythingLLM 依赖的代理，无额外密钥）
数据：事件日志表 EVENT_LOG_TABLE（log_type=INSTRUCTION, source=feynman）
"""
import sys
import os
import json
import subprocess
import urllib.request
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from v19_integration import BASE_TOKEN, EVENT_LOG_TABLE, TARGET_CHAT_ID

GLM_URL = "http://127.0.0.1:3003/v4/chat/completions"
FEYNMAN_DIR = "D:/AI/finished Brain/04-思维方法库/费曼输出"
LOG_FILE = os.path.join(SCRIPT_DIR, "feynman_workflow.log")


def log(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("[{}] {}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def run_cmd(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, shell=False)
        out = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        err = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return r.returncode == 0, out, err
    except Exception as e:
        return False, "", str(e)


def send_message(text):
    cmd = ["lark-cli", "im", "+messages-send",
           "--chat-id", TARGET_CHAT_ID, "--as", "user", "--text", text]
    return run_cmd(cmd)


def write_event_log(message, severity="INFO", source="system", log_type="INSTRUCTION"):
    ts_ms = int(datetime.now().timestamp() * 1000)
    payload = {"create_records": [{
        "event_id": "feyn_{}".format(datetime.now().strftime("%Y%m%d%H%M%S%f")),
        "timestamp": ts_ms,
        "message": message[:1900],
        "severity": severity,
        "source": source,
        "log_type": log_type,
    }]}
    json_file = os.path.join(SCRIPT_DIR, "_tmp_feyn_log.json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    cmd = ["lark-cli", "base", "+record-batch-create",
           "--base-token", BASE_TOKEN, "--table-id", EVENT_LOG_TABLE,
           "--json", "@{}".format(json_file),
           "--as", "user", "--format", "json"]
    ok, out, err = run_cmd(cmd)
    if os.path.exists(json_file):
        os.remove(json_file)
    return ok, out, err


def glm_chat(prompt, max_tokens=1200):
    """调用本机 GLM 代理生成费曼输出"""
    body = {
        "model": "glm-4-flash",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.6,
    }
    req = urllib.request.Request(
        GLM_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def list_feynman():
    d = FEYNMAN_DIR.replace("/", "\\")
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".md"):
                print("·", fn)
    else:
        print("费曼目录不存在：", d)


def main():
    args = sys.argv[1:]
    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        return
    if "--list" in args:
        list_feynman()
        return

    topic = args[0]
    subject = args[1] if len(args) > 1 else "认知升级"
    source = args[2] if len(args) > 2 else topic

    print("=== 费曼学习辅助：{}（{}）===".format(topic, subject))
    prompt = (
        "你是费曼学习法教练。对知识点「{}」执行费曼四步，原文/背景：{}。\n"
        "输出 4 个部分：\n"
        "1.【第一步·大白话复述】用纯口语、无专业术语地解释它，≤200字（假设对方是初中生）\n"
        "2.【第二步·一句话定义+类比】1句核心定义（≤30字）+ 1个生活化类比\n"
        "3.【第三步·卡壳自查】指出复述中最可能讲不清/遗漏的 2-3 个点，给出针对性补学建议\n"
        "4.【第四步·口述提纲】1分钟脱稿口述的分点提纲（4-6个要点）\n"
        "语言简洁直接，不要寒暄。".format(topic, source)
    )
    print("=== 生成费曼输出（GLM 代理）... ===")
    try:
        result = glm_chat(prompt)
    except Exception as e:
        print("[!] LLM 生成失败：", str(e)[:100])
        log("费曼生成失败：{} ({})".format(topic, str(e)[:80]))
        return
    print("=" * 50)
    print(result)
    print("=" * 50)

    # 写入 Obsidian 费曼目录
    fpath = ""
    try:
        target = FEYNMAN_DIR.replace("/", "\\")
        os.makedirs(target, exist_ok=True)
        fname = "费曼-{}.md".format(topic.replace(" ", "_").replace("/", "-"))
        fpath = os.path.join(target, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("# 费曼：{}\n\n> 科目：{} ｜ 生成时间：{}\n\n{}".format(
                topic, subject, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), result))
        print("[OK] 已写入 Obsidian：", fpath)
    except Exception as e:
        print("[!] 写 Obsidian 失败：", str(e)[:80])

    # 写系统事件日志
    ok, _, err = write_event_log("费曼输出｜{}（{}）已归档".format(topic, subject))
    print("[OK] 已写事件日志" if ok else "[!] 事件日志写入失败：{}".format(err[:80]))

    # 推送总控群
    send_ok, _, _ = send_message(
        "📖 费曼学习输出｜【{}】\n科目：{}\n{}\n📎 归档：{}".format(topic, subject, result[:400], fpath or "Obsidian目录"))
    print("[OK] 已推送总控群" if send_ok else "[!] 群推送失败")

    log("费曼：{}（{}）｜归档={}｜日志={}｜推送={}".format(topic, subject, fpath, ok, send_ok))


if __name__ == "__main__":
    main()
