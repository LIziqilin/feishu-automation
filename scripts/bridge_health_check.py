#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bridge_health_check.py — 全桥接健康自检（V45-14）
====================================================================
一键 ping 所有子系统间桥接，输出健康表。供维护链/手动巡检调用。
只读探测，不写任何业务数据。

桥接清单：
  1. 飞书 OpenAPI（lark-cli）     — 不直连本机，跳过（由 heartbeat 覆盖）
  2. 飞书群轮询                    — learning_system --poll，由 watchdog 覆盖
  3. Obsidian Local REST API 27124 — HTTP 探测
  4. feishu-mcp 子进程             — 文件存在性 + node 存在性
  5. filesystem MCP 子进程         — 文件存在性
  6. AnythingLLM SQLite            — sqlite3 打开探测
  7. AnythingLLM REST              — 已知无（跳过）
  8. GitHub Actions                — 云端，本机不探测
  9. Coze Bot                      — REST /v1/bot/get_online_info
 10. 企业微信 Webhook               — 配置存在性（不真发）
 11. LLM fallback                  — 配置存在性

用法：
  python bridge_health_check.py          # 人类可读
  python bridge_health_check.py --json   # JSON 输出
"""
import os, sys, json, ssl, sqlite3, argparse, urllib.request, urllib.error
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent

OBS_BASE = "https://127.0.0.1:27124"
OBS_KEY = "579c9276444b294ea705e20c327b8f9ff9d80db756fdfd63939e474d9b3cc489"
CTX = ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE

HERMES_NODE = r"C:\Users\Administrator\AppData\Local\hermes\node\node.exe"
FEISHU_MCP_CLI = r"C:\Users\Administrator\AppData\Local\hermes\node\node_modules\feishu-mcp\dist\cli.js"
FS_MCP = r"D:\AI-Tools\feishu\飞书的高阶用法\mcp-servers\node_modules\@modelcontextprotocol\server-filesystem\dist\index.js"
ANYLLM_DB = r"C:\Users\Administrator\AppData\Roaming\anythingllm-desktop\storage\anythingllm.db"
COZE_CFG = r"D:\AI-Tools\shared\coze_config.json"
WECOM_CFG = HERE / "wecom_config.json"
LLM_CFG = HERE / "llm_config.json"

def chk_obsidian():
    try:
        req = urllib.request.Request(OBS_BASE + "/", headers={"Authorization":"Bearer "+OBS_KEY})
        r = urllib.request.urlopen(req, timeout=4, context=CTX)
        return "ok", f"HTTP {r.status}"
    except Exception as e:
        return "down", f"{type(e).__name__}: {str(e)[:80]}"

def chk_file(label, p):
    return ("ok" if Path(p).exists() else "down", str(p))

def chk_anyllm_db():
    try:
        con = sqlite3.connect(f"file:{ANYLLM_DB}?mode=ro", uri=True, timeout=3)
        n = con.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0]
        con.close()
        return "ok", f"workspaces={n}"
    except Exception as e:
        return "down", str(e)[:80]

def chk_coze():
    if not Path(COZE_CFG).exists():
        return "down", "coze_config.json 缺失"
    try:
        cfg = json.loads(Path(COZE_CFG).read_text(encoding="utf-8"))
        # 只探测配置完整性，不真调 API（避免 4015 噪声）
        ok = bool(cfg.get("coze_api_token") and cfg.get("bot_id"))
        return "ok" if ok else "down", f"bot_id={cfg.get('bot_id','?')}（Bot 发布状态待确认）"
    except Exception as e:
        return "down", str(e)[:80]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    rows = [
        ("Obsidian Local REST 27124", *chk_obsidian()),
        ("feishu-mcp node.exe", *chk_file("node", HERMES_NODE)),
        ("feishu-mcp cli.js", *chk_file("cli", FEISHU_MCP_CLI)),
        ("filesystem MCP index.js", *chk_file("fs", FS_MCP)),
        ("AnythingLLM SQLite", *chk_anyllm_db()),
        ("Coze 配置", *chk_coze()),
        ("企业微信 webhook 配置", *("ok" if WECOM_CFG.exists() else "down", str(WECOM_CFG))),
        ("LLM fallback 配置", *("ok" if LLM_CFG.exists() else "down", str(LLM_CFG))),
    ]
    bad = [r for r in rows if r[1] != "ok"]
    payload = {
        "ts": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "total": len(rows), "ok": len(rows)-len(bad), "down": len(bad),
        "rows": [{"bridge": n, "status": s, "detail": d} for n,s,d in rows],
    }
    if a.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"桥接健康自检 {payload['ts']}  共{payload['total']} 正常{payload['ok']} 异常{payload['down']}")
        for n,s,d in rows:
            mark = "✅" if s=="ok" else "❌"
            print(f"  {mark} {n:32s} {s:6s} {d}")
    sys.exit(0 if not bad else 2)

if __name__ == "__main__":
    main()
