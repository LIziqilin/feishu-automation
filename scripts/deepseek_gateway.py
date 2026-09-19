#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""deepseek_gateway.py — V47 DeepSeek API 封装（替代 Coze 做批量表格任务）
====================================================================
模型：deepseek-v4-flash（全部任务统一）
Base：https://api.deepseek.com
Key：从环境变量 DEEPSEEK_API_KEY 读

用法：
  from deepseek_gateway import run
  ok, resp = run("你是错题解析助手。原题：...")
"""
import os, sys, json, time

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-v4-flash"
MAX_OUTPUT = 600  # 控制成本，防止超长输出


def run(prompt: str, system: str = ""):
    """调 DeepSeek，返回 (ok, text_or_errmsg)"""
    if not API_KEY:
        return False, "DEEPSEEK_API_KEY 未配置"
    try:
        from openai import OpenAI
    except ImportError:
        return False, "openai 包未安装: pip install openai"

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt[:4000]})

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=msgs,
            max_tokens=MAX_OUTPUT,
            temperature=0.3,
        )
        text = resp.choices[0].message.content.strip()
        usage = resp.usage
        cost_note = f"[in={usage.prompt_tokens} out={usage.completion_tokens}]"
        return True, f"{text} {cost_note}"
    except Exception as e:
        return False, f"DeepSeek调用失败: {e}"


def check():
    """连通性检查"""
    ok, resp = run("用一句话介绍你自己")
    print(f"DeepSeek check: ok={ok}, resp={resp[:100]}")
    return ok


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        check()
    else:
        q = sys.argv[1] if len(sys.argv) > 1 else "用一句话解释什么是费曼学习法"
        ok, resp = run(q)
        print(f"ok={ok}")
        print(resp)
