#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p0a_gh_logcheck.py — 拉取指定 run 的日志压缩包并解析推送结果
用法: python p0a_gh_logcheck.py <GH_TOKEN> <run_id>
"""
import sys, io, json, zipfile, urllib.request, urllib.error

tok = sys.argv[1]
run_id = sys.argv[2]
REPO = "LIziqilin/feishu-automation"

url = f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}/logs"
h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
     "X-GitHub-Api-Version": "2022-11-28"}
req = urllib.request.Request(url, headers=h, method="GET")
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    print("BYTES", len(data))
    z = zipfile.ZipFile(io.BytesIO(data))
    print("FILES", z.namelist())
    for n in z.namelist():
        if "morning_cloud" in n or "log" in n:
            txt = z.read(n).decode("utf-8", errors="replace")
            print(f"===== {n} ({len(txt)} chars) =====")
            print(txt[-1800:])
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode(errors="replace")[:300])
except Exception as e:
    print("ERR", str(e)[:200])
