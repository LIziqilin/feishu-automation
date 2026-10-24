#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p0a_github_secrets.py — P0-A 云端永续：将 A 应用（总控群 bot）凭据写入 GitHub Actions Secrets
用法: python p0a_github_secrets.py <GH_TOKEN> [--dry-run]
凭据来源: agent1_business/.env 的 FEISHU_APP_ID / FEISHU_APP_SECRET + 固定 BASE_TOKEN
"""
import os, sys, json, base64, urllib.request, urllib.error
from nacl import encoding, public

REPO = "LIziqilin/feishu-automation"
BASE_TOKEN = "X8N1bvN3na99dFsyu0gcU8zTnHf"
ENV_PATH = r"C:\Users\Administrator\AppData\Local\hermes\profiles\agent1_business\.env"
DRY = "--dry-run" in sys.argv

tok = sys.argv[1] if len(sys.argv) > 1 else ""
if not tok:
    print("NO_TOKEN"); sys.exit(2)

def read_env(path, key):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    return ""

def api(method, path, body=None, timeout=30):
    url = "https://api.github.com" + path
    h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:300]}

def seal(public_key_b64, value):
    pk = public.PublicKey(public_key_b64, encoding.Base64Encoder())
    sealed = public.SealedBox(pk).encrypt(value.encode("utf-8"))
    return base64.b64encode(sealed).decode()

def main():
    app_id = read_env(ENV_PATH, "FEISHU_APP_ID")
    app_secret = read_env(ENV_PATH, "FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        print(f"ENV_MISSING app_id={bool(app_id)} secret={bool(app_secret)}"); sys.exit(2)
    print(f"LOCAL_APP_ID={app_id[:14]}... secret_len={len(app_secret)}")

    st, pk = api("GET", f"/repos/{REPO}/actions/secrets/public-key")
    if st != 200:
        print(f"PUBKEY_FAIL st={st} {pk}"); sys.exit(2)
    key_id = pk["key_id"]
    print(f"PUBKEY_OK key_id={key_id}")

    secrets = {
        "FEISHU_APP_ID": app_id,
        "FEISHU_APP_SECRET": app_secret,
        "FEISHU_BASE_TOKEN": BASE_TOKEN,
    }
    for name, val in secrets.items():
        if DRY:
            print(f"[dry] PUT {name} len={len(val)}")
            continue
        enc = seal(pk["key"], val)
        st, r = api("PUT", f"/repos/{REPO}/actions/secrets/{name}",
                    {"encrypted_value": enc, "key_id": key_id})
        print(f"PUT {name} -> st={st}" + (f" {r}" if st != 201 and st != 204 else ""))
        if st not in (201, 204):
            sys.exit(2)

    st, s = api("GET", f"/repos/{REPO}/actions/secrets")
    if st == 200:
        for x in s.get("secrets", []):
            if x["name"] in secrets:
                print(f"VERIFY {x['name']} updated={x['updated_at']}")
    print("DONE")

if __name__ == "__main__":
    main()
