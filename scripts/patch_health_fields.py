# -*- coding: utf-8 -*-
"""V41 健康表字段补写：为历史记录补齐"组件健康度/系统健康评分"字段
用法: python patch_health_fields.py [--dry-run] [--limit N]
"""
import argparse, json, os, sys, time, urllib.request, urllib.error

BASE = 'X8N1bvN3na99dFsyu0gcU8zTnHf'
HEALTH_TABLE = 'tblxJMndPNtZ7XyG'
ENV_CANDIDATES = [
    r"C:\Users\Administrator\AppData\Local\hermes\profiles\agent6_scheduler\scripts\feishu_insight_link.env",
    r"D:\AI-Tools\feishu\飞书的高阶用法\feishu_insight_link.env",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "feishu_insight_link.env"),
]

def load_secret(key):
    v = os.environ.get(key)
    if v: return v
    for p in ENV_CANDIDATES:
        try:
            for line in open(p, encoding="utf-8-sig"):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, val = line.partition("=")
                    if k.strip() == key: return val.strip()
        except Exception: continue
    return ""

def get_token(app_id, app_secret):
    req = urllib.request.Request("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)

def api(token, method, url, payload=None, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode() if payload else None,
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"}, method=method)
            with urllib.request.urlopen(req, timeout=60) as r: resp = json.load(r)
            if resp.get("code") == 0: return resp.get("data", {}), None
            if resp.get("code") == 1254291 and i < retries-1: time.sleep(1.0*(i+1)); continue
            return None, f"code_{resp.get('code')}:{resp.get('msg')}"
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8","ignore")[:200]
            return None, f"http_{e.code}:{body}"
        except Exception as e:
            if i < retries-1: time.sleep(1.0*(i+1)); continue
            return None, str(e)[:120]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 条空值记录（0=全部）")
    args = ap.parse_args()

    app_id = load_secret("FEISHU_APP_ID"); app_secret = load_secret("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        print("ERR: no app credentials"); sys.exit(1)
    tr = get_token(app_id, app_secret)
    if tr.get("code") != 0:
        print("ERR: token", tr.get("msg")); sys.exit(1)
    token = tr["tenant_access_token"]

    # 1) 拉全量（带 record_id）
    url = "https://open.feishu.cn/open-apis/bitable/v1/apps/%s/tables/%s/records?page_size=500" % (BASE, HEALTH_TABLE)
    records, page_token = [], None
    while True:
        u = url + (("&page_token=" + page_token) if page_token else "")
        data, err = api(token, "GET", u)
        if err: print("ERR list:", err); sys.exit(1)
        items = data.get("items", [])
        records.extend(items)
        if not data.get("has_more"): break
        page_token = data.get("page_token")
    print("总记录:", len(records))

    # 2) 找空值记录
    need = []
    for it in records:
        f = it.get("fields", {})
        k = f.get("组件健康度"); w = f.get("系统健康评分")
        if k is None or w is None:
            need.append(it)
    print("缺组件健康度或系统健康评分:", len(need))

    # 3) 生成补值
    patches = []
    for it in need:
        f = it.get("fields", {})
        status = f.get("处理状态")
        status = status[0] if isinstance(status, list) and status else (status or "")
        ok = (str(status) == "正常")
        cur_k = f.get("组件健康度")
        cur_w = f.get("系统健康评分")
        try: cur_k = float(cur_k) if cur_k is not None else None
        except (TypeError, ValueError): cur_k = None
        try: cur_w = float(cur_w) if cur_w is not None else None
        except (TypeError, ValueError): cur_w = None
        nk = cur_k if cur_k is not None else (100.0 if ok else 40.0)
        nw = cur_w if cur_w is not None else (5.0 if ok else 1.5)
        patches.append({"record_id": it["record_id"], "fields": {"组件健康度": nk, "系统健康评分": nw}})
    print("待更新:", len(patches))

    if args.limit > 0: patches = patches[:args.limit]
    if args.dry_run:
        print("DRY_RUN: 将更新", len(patches), "条")
        from collections import Counter
        print("分值分布:", dict(Counter((p["fields"]["组件健康度"], p["fields"]["系统健康评分"]) for p in patches)))
        sys.exit(0)

    # 4) 分批更新（≤200/批）
    ok_n = 0
    for i in range(0, len(patches), 200):
        batch = patches[i:i+200]
        data, err = api(token, "POST",
            "https://open.feishu.cn/open-apis/bitable/v1/apps/%s/tables/%s/records/batch_update" % (BASE, HEALTH_TABLE),
            {"records": batch})
        if err:
            print(f"批 {i//200} 失败:", err); continue
        ok_n += len(data.get("records", batch))
        print(f"批 {i//200}: +{len(batch)} ok")
        time.sleep(0.3)
    print(f"完成: {ok_n}/{len(patches)} 条已补写")

if __name__ == "__main__":
    main()
