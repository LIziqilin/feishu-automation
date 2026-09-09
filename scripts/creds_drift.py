# -*- coding: utf-8 -*-
"""creds_drift.py — V13 凭据 SSOT 收口与漂移检测（波次1·数据安全组）
设计（软件专家定稿）：单写入点(权威 JSON) + 只读副本 + 运行时哈希漂移检测
  - 权威源: D:\AI-Tools\feishu\飞书的高阶用法\优化实施\scripts\feishu_creds.json
  - 副本:   D:\AI-Tools\shared\state\creds_副本.json（只读，脚本不得写入）
  - 漂移检测: 对权威源做 SHA-256 指纹并持久化 state\creds.fingerprint，
             每次运行时比对；发现指纹变化 → A 类告警（本地 alerts.log + 弹窗）
  - 全仓业务脚本扫描：列出仍手写 APP_SECRET/token 的脚本（渐进迁移台账）
用法: python creds_drift.py [--scan] [--init-fingerprint] [--copy]
"""
import os, sys, io, json, hashlib, re, glob
_LOCAL_SHARED = r'D:\AI-Tools\shared'
if os.path.isdir(_LOCAL_SHARED):
    sys.path.insert(0, _LOCAL_SHARED)
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass
from local_alert import log_alert

AUTH = r'D:\AI-Tools\feishu\飞书的高阶用法\优化实施\scripts\feishu_creds.json'
STATE_DIR = r'D:\AI-Tools\shared\state'
FP = os.path.join(STATE_DIR, 'creds.fingerprint')
COPY = os.path.join(STATE_DIR, 'creds_副本.json')
SCAN_ROOTS = [r'D:\AI-Tools\feishu', r'D:\AI-Tools\gh_upload', r'D:\AI-Tools\shared']
EXCLUDE_SUB = ('.venv', 'site-packages', '__pycache__', 'oapi-sdk', 'shadow', 'V12方案')
SECRET_RX = re.compile(r'(APP_SECRET|app_secret|tenant_access_token)\s*[:=]\s*["\']')

def _excluded(path):
    low = path.replace('\\', '/')
    return any(s in low for s in EXCLUDE_SUB)

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

def drift_check():
    if not os.path.exists(AUTH):
        log_alert('A', 'creds_drift', '凭据权威源缺失: %s' % AUTH)
        return 'AUTH_MISSING'
    fp = sha256_file(AUTH)
    if not os.path.exists(FP):
        with open(FP, 'w') as f:
            f.write(fp)
        return 'INIT'
    with open(FP) as f:
        old = f.read().strip()
    if old != fp:
        log_alert('A', 'creds_drift', '凭据权威源指纹漂移! 请核对是否被意外修改')
        with open(FP, 'w') as f:
            f.write(fp)
        return 'DRIFT'
    return 'OK'

def copy_ro():
    """生成只读副本（权限设置为只读位）。"""
    os.makedirs(STATE_DIR, exist_ok=True)
    if os.path.exists(AUTH):
        data = open(AUTH, encoding='utf-8').read()
        with open(COPY, 'w', encoding='utf-8') as f:
            f.write(data)
        try:
            os.chmod(COPY, 0o444)
        except Exception:
            pass
        return COPY

def scan_scripts():
    hits = []
    for root in SCAN_ROOTS:
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if not _excluded(os.path.join(dp, d))]
            for fn in fns:
                if not fn.endswith('.py'):
                    continue
                p = os.path.join(dp, fn)
                try:
                    txt = open(p, encoding='utf-8', errors='ignore').read()
                except Exception:
                    continue
                if SECRET_RX.search(txt):
                    hits.append(p)
    return hits

def main():
    args = sys.argv[1:]
    if '--init-fingerprint' in args:
        r = drift_check()
        print('指纹初始化: %s' % r)
    if '--copy' in args:
        p = copy_ro()
        print('只读副本: %s' % p)
    if '--scan' in args:
        hits = scan_scripts()
        print('仍手写凭据的业务脚本 %d 个（渐进迁移台账）:' % len(hits))
        for h in hits:
            print('  ', h)
    if not args:
        r = drift_check()
        print('漂移检测: %s' % r)

if __name__ == '__main__':
    main()
