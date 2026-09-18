#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""anyllm_bridge.py — AnythingLLM 桥接（V45-9 新增）
只读 anythingllm.db（SQLite），提供：
  1) 工作区/Agent/文档/向量/聊天统计（--stats）
  2) 检索已索引文档清单（--docs [关键词]）
  3) 验证 SQL 连接配置状态（--sql）
零写入、零依赖（仅标准库 sqlite3），供本系统"问系统"等模块引用参考。
"""
import argparse
import json
import os
import sqlite3
import sys

DB_PATH = r"C:\Users\Administrator\AppData\Roaming\anythingllm-desktop\storage\anythingllm.db"


def _conn():
    if not os.path.exists(DB_PATH):
        print(f"❌ AnythingLLM 数据库不存在: {DB_PATH}")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)


def cmd_stats():
    con = _conn()
    cur = con.cursor()
    out = {"anythingllm": {}, "workspaces": [], "agents": []}
    for t, label in [
        ("workspaces", "工作区"), ("workspace_documents", "已索引文档"),
        ("document_vectors", "向量分片"), ("workspace_chats", "聊天记录"),
        ("event_logs", "事件日志"), ("workspace_agent_invocations", "Agent调用")]:
        try:
            cur.execute(f"SELECT COUNT(*) FROM '{t}'")
            out["anythingllm"][label] = cur.fetchone()[0]
        except Exception:
            out["anythingllm"][label] = 0
    cur.execute("SELECT id, name, chatMode, agentModel, agentProvider FROM workspaces")
    for r in cur.fetchall():
        ws = {"id": r[0], "name": r[1], "mode": r[2], "agent_model": r[3], "agent_provider": r[4]}
        if r[3]:
            out["agents"].append(ws)
        out["workspaces"].append(ws)
    # skill 配置
    cur.execute("SELECT label, value FROM system_settings WHERE label IN ('default_agent_skills','disabled_agent_skills','agent_sql_connections','agent_search_provider')")
    skills = {}
    for r in cur.fetchall():
        try:
            skills[r[0]] = json.loads(r[1])
        except Exception:
            skills[r[0]] = r[1]
    out["agent_skills"] = skills
    con.close()
    print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_docs(keyword=None):
    con = _conn()
    cur = con.cursor()
    sql = """SELECT d.id, d.docpath, d.workspaceId, d.filename
             FROM workspace_documents d LEFT JOIN workspaces w ON d.workspaceId = w.id"""
    if keyword:
        cur.execute(sql + " WHERE d.docpath LIKE ? OR d.filename LIKE ? LIMIT 30",
                    (f"%{keyword}%", f"%{keyword}%"))
    else:
        cur.execute(sql + " ORDER BY d.workspaceId LIMIT 30")
    rows = cur.fetchall()
    print(f"文档匹配 {len(rows)} 条（关键词: {keyword or '全部,前30'}）")
    for r in rows:
        print(f"  [WS{r[2]}] {r[1]}")
    con.close()


def cmd_sql():
    con = _conn()
    cur = con.cursor()
    cur.execute("SELECT label, value FROM system_settings WHERE label='agent_sql_connections'")
    r = cur.fetchone()
    print("SQL 连接配置:", r[1] if r else "N/A（设置项不存在）")
    cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
    print("AnythingLLM 数据库表数:", cur.fetchone()[0], "（可 sqlite 直连只读）")
    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="AnythingLLM 桥接（只读）")
    ap.add_argument("action", choices=["stats", "docs", "sql"])
    ap.add_argument("keyword", nargs="?", default=None)
    a = ap.parse_args()
    if a.action == "stats":
        cmd_stats()
    elif a.action == "docs":
        cmd_docs(a.keyword)
    else:
        cmd_sql()
