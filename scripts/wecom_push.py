#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
企业微信推送（V15 Phase4 微信集成，官方群机器人 Webhook，零成本/无封号风险）
=========================================================================
为什么不用个人微信：WeChatFerry/itchat 等 Hook 个人微信有封号风险，不用于生产。
企业微信群机器人是官方能力，稳定免费；企业微信可在手机上与个人微信同时接收提醒。

配置（一次）：
  1. 企业微信建一个群（可只拉自己），群右上角「...」→ 群机器人 → 添加 → 复制 Webhook
  2. 运行 python wecom_push.py --init，把 Webhook 填进生成的 wecom_config.json
  3. python wecom_push.py --test 验证

能力：
  send_text / send_markdown：推企业微信
  dual_push：飞书总控群 + 企业微信群 双通道同时推（三报/告警用）
"""
import sys, io, json, os, urllib.request, argparse
sys.path.insert(0, '.')
from v15_features import send_chat, now_str

CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wecom_config.json")

def _load_cfg():
    """P0-4/M1：密钥不入仓。优先环境变量 WECOM_WEBHOOK_URL / wecom_secrets.env，
    wecom_config.json 仅保留非敏感元数据（enabled/说明）。"""
    cfg = {"enabled": False, "webhook_url": ""}
    if os.path.exists(CFG):
        try:
            with open(CFG, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    # 环境变量 > secrets 文件 > config(若仍含url)
    env_url = os.environ.get("WECOM_WEBHOOK_URL")
    if env_url:
        cfg["webhook_url"] = env_url.strip()
        cfg["enabled"] = True
    else:
        sec = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wecom_secrets.env")
        if os.path.exists(sec):
            try:
                with open(sec, encoding="utf-8-sig") as f:
                    for line in f:
                        if line.strip().startswith("WECOM_WEBHOOK_URL="):
                            cfg["webhook_url"] = line.strip().split("=", 1)[1].strip()
                            cfg["enabled"] = True
            except Exception:
                pass
    return cfg

def _save_cfg(cfg):
    with open(CFG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def _post(payload):
    cfg = _load_cfg()
    url = cfg.get("webhook_url", "")
    if not cfg.get("enabled") or not url:
        return False, "未配置/未启用企业微信Webhook"
    try:
        req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.load(r)
        if resp.get("errcode") == 0:
            return True, "ok"
        return False, f"errcode={resp.get('errcode')} {resp.get('errmsg')}"
    except Exception as e:
        return False, f"请求异常:{e}"

def send_text(text):
    return _post({"msgtype": "text", "text": {"content": text}})

def send_markdown(md, title=None):
    content = (f"## {title}\n\n" if title else "") + md
    return _post({"msgtype": "markdown", "markdown": {"content": content}})

def dual_push(text, md=None, also_feishu=True):
    """双通道：飞书总控群 + 企业微信群。返回各自结果"""
    res = {}
    if also_feishu:
        try:
            res["feishu"] = send_chat(text)
        except Exception as e:
            res["feishu"] = f"error:{e}"
    ok, msg = send_markdown(md or text)
    res["wecom"] = msg if ok else f"skip({msg})"
    return res

def init_config():
    cfg = _load_cfg()
    _save_cfg(cfg)
    print(f"已生成配置文件：{CFG}")
    print("请用记事本打开，把 webhook_url 填成你的企业微信群机器人地址，并把 enabled 改为 true")

def selfcheck():
    cfg = _load_cfg()
    print("=== 企业微信推送自检 ===")
    if not cfg.get("webhook_url"):
        print("⚠️ 尚未配置 webhook_url")
        print("获取步骤：企业微信群 → 右上角... → 群机器人 → 添加机器人 → 复制Webhook地址")
        print(f"然后填入：{CFG}")
        return
    ok, msg = send_text(f"✅ 企业微信通道测试 {now_str()}")
    print("推送结果：", "成功" if ok else msg)

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    if args.init: init_config()
    else: selfcheck()
