#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""feishu_mcp_cli.py — 飞书 MCP 工具封装（V45-11 新增）
基于 feishu-mcp 0.3.2 的独立 CLI（feishu-tool），无需启动 MCP 服务器即可调用飞书工具。
用途：本系统可直接用飞书文档通道（创建/读取/编辑/搜索文档、文件夹管理），
      与现有 lark-cli（多维表格/消息）体系形成双通道。
用法：
  python feishu_mcp_cli.py search "关键词"          # 搜索飞书文档
  python feishu_mcp_cli.py root                     # 根文件夹信息
  python feishu_mcp_cli.py files <folder_token>     # 文件夹下文件
  python feishu_mcp_cli.py tools                    # 列出全部可用工具
  python feishu_mcp_cli.py call <tool_name> '<json>' # 任意工具调用
"""
import json
import os
import subprocess
import sys

NODE = r"C:\Users\Administrator\AppData\Local\hermes\node\node.exe"
TOOL = r"C:\Users\Administrator\AppData\Local\hermes\node\node_modules\feishu-mcp\dist\cli\index.js"
# 凭证从环境变量读取（不硬编码到仓库）：
#   FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_AUTH_TYPE(默认 tenant)
APP_ID = os.environ.get("FEISHU_APP_ID", "cli_aa0d9ed52338dbd1")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")


def _env():
    env = dict(os.environ)
    if not APP_SECRET:
        raise SystemExit("❌ 请先设置环境变量 FEISHU_APP_SECRET（凭证据此读取，不落仓库）")
    env.update({"FEISHU_APP_ID": APP_ID, "FEISHU_APP_SECRET": APP_SECRET,
                "FEISHU_AUTH_TYPE": "tenant", "FEISHU_ENABLED_MODULES": "all"})
    return env


def call(tool_name, args=None):
    args = args or {}
    p = subprocess.run([NODE, TOOL, tool_name, json.dumps(args, ensure_ascii=False)],
                       capture_output=True, text=True, encoding="utf-8", env=_env(), timeout=120)
    out = p.stdout.strip()
    if not out:
        out = p.stderr.strip()
    try:
        return json.loads(out)
    except Exception:
        return {"_raw": out}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "tools":
        p = subprocess.run([NODE, TOOL, "help"], capture_output=True,
                           text=True, encoding="utf-8", env=_env(), timeout=60)
        print(p.stdout.strip()[:2000])
    elif cmd == "root":
        print(json.dumps(call("get_feishu_root_folder_info"), ensure_ascii=False, indent=1))
    elif cmd == "search":
        kw = sys.argv[2] if len(sys.argv) > 2 else ""
        r = call("search_feishu_documents", {"searchKey": kw})
        docs = r.get("documents", [])
        print(f"命中 {len(docs)} 篇：")
        for d in docs[:20]:
            print("  -", d.get("title", "?"), "|", d.get("token", ""))
    elif cmd == "files":
        token = sys.argv[2] if len(sys.argv) > 2 else ""
        r = call("get_feishu_folder_files", {"folderToken": token})
        files = r.get("files", []) or r.get("data", {}).get("files", [])
        print(f"文件 {len(files)} 个：")
        for f in files[:20]:
            print("  -", f.get("name", "?"), "|", f.get("token", ""))
    elif cmd == "call":
        name = sys.argv[2]
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        print(json.dumps(call(name, args), ensure_ascii=False, indent=1)[:2000])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
