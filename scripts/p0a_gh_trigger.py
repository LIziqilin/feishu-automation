#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p0a_gh_trigger.py — 触发指定云端 workflow 并轮询日志验证
用法: python p0a_gh_trigger.py <GH_TOKEN> [wf_id] [run_seconds]
默认 wf_id=360964015（V16 早报推送·云端永续）；360964013=每日维护备份
"""
import sys, time, json, urllib.request, urllib.error

REPO = "LIziqilin/feishu-automation"
tok = sys.argv[1]
WF_ID = sys.argv[2] if len(sys.argv) > 2 else "360964015"
MAX_WAIT = int(sys.argv[3]) if len(sys.argv) > 3 else 300

def api(method, path, body=None, timeout=30):
    url = "https://api.github.com" + path
    h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:400]}

# 1) 触发
st, r = api("POST", f"/repos/{REPO}/actions/workflows/{WF_ID}/dispatches", {"ref": "main"})
print(f"DISPATCH st={st}")
if st != 204:
    print("DISPATCH_FAIL", r); sys.exit(2)

# 2) 轮询 runs
start = time.time()
run_id = None
while time.time() - start < 30:
    time.sleep(3)
    st, r = api("GET", f"/repos/{REPO}/actions/workflows/{WF_ID}/runs?per_page=1")
    if st == 200 and r.get("total_count"):
        rid = r["workflow_runs"][0]["id"]
        status = r["workflow_runs"][0]["status"]
        concl = r["workflow_runs"][0].get("conclusion")
        created = r["workflow_runs"][0]["created_at"]
        print(f"RUN id={rid} status={status} concl={concl} created={created}")
        if status in ("completed", "success", "failure") or concl:
            run_id = rid; break
        run_id = rid
print(f"run_id={run_id}")

# 3) 轮询直到 completed
while run_id and time.time() - start < MAX_WAIT:
    time.sleep(10)
    st, r = api("GET", f"/repos/{REPO}/actions/runs/{run_id}")
    if st == 200:
        status = r["status"]; concl = r.get("conclusion")
        print(f"POLL status={status} concl={concl}")
        if status == "completed":
            print(f"CONCLUSION={concl}")
            break

# 4) 拉 jobs 日志
if run_id:
    st, r = api("GET", f"/repos/{REPO}/actions/runs/{run_id}/jobs")
    if st == 200:
        for j in r.get("jobs", []):
            print(f"JOB {j['name']} concl={j.get('conclusion')}")
            for s in j.get("steps", []):
                print(f"  STEP {s['name']} concl={s.get('conclusion')}")
    # 下载日志文本
    st, r = api("GET", f"/repos/{REPO}/actions/runs/{run_id}/logs")
    if st == 200:
        raw = r.get("raw", "")
        print("LOG_LEN", len(raw))
        for kw in ["☀️", "云端早报", "早报", "code=0", "code=", "Error", "Traceback", "推送", "失败"]:
            if kw in raw:
                i = raw.find(kw)
                print(f"LOG[{kw}] ...{raw[max(0,i-120):i+220]}...".replace("\n", " "))
                break
    else:
        print(f"LOG_FAIL st={st} {str(r)[:200]}")
