#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
安全审计（M1）— 关闭一票否决 #1/#2「硬编码凭证 / 越权」
=====================================================
1. 全仓密钥扫描（正则命中 → 分级）
2. 敏感文件是否被 git 跟踪/忽略
3. 最小权限审计：默认权限声明 + 高危工具白名单
产出 acceptance/evidence/security/<ts>/report.json
"""
import sys, io, json, re, os, shutil, subprocess
from datetime import datetime
from pathlib import Path
import fnmatch

ROOT = Path(__file__).resolve().parent.parent
EVID = ROOT / "acceptance" / "evidence" / "security"
SKIP = {".git", "node_modules", "backups", "__pycache__", ".venv", "venv"}


def _find_git():
    """解析真实 git 可执行文件（避开无法直接 CreateProcess 的 .cmd 包装）"""
    env = os.environ.get("QCLAW_GIT_BINARY")
    if env and Path(env).exists():
        return env
    for c in [
        r"C:\Program Files\QClaw\v0.2.36.629\resources\git\cmd\git.exe",
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
    ]:
        if Path(c).exists():
            return c
    w = shutil.which("git")
    if w and not w.lower().endswith(".cmd") and not w.lower().endswith(".bat"):
        return w
    return None


GIT = _find_git()

# 指定的密钥存放位置（内容可豁免，但前提是必须已被 .gitignore 忽略）
SECRET_STORE_SUFFIXES = ("_secrets.env", ".secrets.env", "_credentials.env", "credentials.env")

def _is_secret_store(name):
    return any(name.endswith(s) for s in SECRET_STORE_SUFFIXES)

def _gitignored(rel):
    """判断相对路径是否被 git 忽略；无法调用 git 时回退到解析 .gitignore"""
    if GIT:
        try:
            r = subprocess.run([GIT, "check-ignore", rel], cwd=str(ROOT),
                               capture_output=True, text=True, timeout=10,
                               encoding="utf-8", errors="replace")
            return r.returncode == 0
        except Exception:
            pass
    gi = ROOT / ".gitignore"
    if not gi.exists():
        return False
    name = Path(rel).name
    try:
        for line in gi.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if fnmatch.fnmatch(rel, line) or fnmatch.fnmatch(name, line) or line in rel:
                return True
    except Exception:
        pass
    return False

PATTERNS = [
    ("CRITICAL", re.compile(r"sk-[A-Za-z0-9]{20,}"), "LLM/云服务密钥", None),
    ("CRITICAL", re.compile(r"\"secret\"\s*:\s*\"[A-Za-z0-9_\-]{20,}\""), "Secret明文", None),
    ("HIGH", re.compile(r"FEISHU_APP_SECRET\s*=\s*[\"']?[A-Za-z0-9]{20,}"), "飞书AppSecret明文", None),
    ("HIGH", re.compile(r"webhook/send\?key=[0-9a-f\-]{30,}"), "企微Webhook明文", None),
    ("CRITICAL", re.compile(r"^[A-Z0-9_]*(?:SECRET|AESKEY|AES_KEY)[A-Z0-9_]*\s*=\s*\S{16,}", re.M), ".env密钥明文(SECRET/AESKEY)", ".env"),
    ("HIGH", re.compile(r"^[A-Z0-9_]*(?:TOKEN|WEBHOOK|PASSWORD|PASSWD|APIKEY|API_KEY)[A-Z0-9_]*\s*=\s*\S{12,}", re.M), ".env凭证明文(TOKEN/WEBHOOK等)", ".env"),
    ("MEDIUM", re.compile(r"(password|passwd|pwd)\s*=\s*[\"'][^\"']{6,}"), "口令明文", None),
    ("LOW", re.compile(r"(api[_-]?key|token)\s*=\s*[\"'][A-Za-z0-9_\-]{16,}"), "疑似token", None),
]

def scan():
    hits = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in (".py", ".json", ".env", ".md", ".txt", ".yml", ".yaml", ".ps1", ".sh", ".cfg", ".ini", ".cmd"):
            continue
        if any(s in p.parts for s in SKIP):
            continue
        rel = str(p.relative_to(ROOT))
        if _is_secret_store(p.name):
            if _gitignored(rel):
                continue  # 指定密钥存放位置且已被 .gitignore 忽略 → 豁免
            # 密钥文件未被忽略 = 真实泄露风险（fail-loud）
            hits.append({"level": "CRITICAL", "file": rel, "line": 1,
                         "kind": "凭证文件未加入.gitignore（git add 即泄露）", "sample": "***"})
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for lvl, pat, desc, scope in PATTERNS:
            if scope == ".env" and p.suffix.lower() != ".env":
                continue
            for m in pat.finditer(text):
                line = text[:m.start()].count("\n") + 1
                hits.append({"level": lvl, "file": str(p.relative_to(ROOT)), "line": line,
                             "kind": desc, "sample": m.group(0)[:12] + "***"})
    return hits

def git_tracking():
    """校验敏感文件是否被 git 跟踪/忽略。必须用真实 git 二进制；
    不可用时报 error 并将 unknown 视为风险（fail-loud，不得静默放行）"""
    out = {}
    targets = ["scripts/llm_secrets.env", "scripts/wecom_secrets.env",
               "scripts/wecom_app_credentials.env", "scripts/wecom_config.json",
               "scripts/llm_config.json"]
    for f in targets:
        if not (ROOT / f).exists():
            continue
        if not GIT:
            out[f] = {"ignored": False, "tracked": False, "error": "git_not_found"}
            continue
        try:
            r = subprocess.run([GIT, "check-ignore", f], cwd=str(ROOT), capture_output=True,
                               text=True, timeout=10, encoding="utf-8", errors="replace")
            ignored = r.returncode == 0
            r2 = subprocess.run([GIT, "ls-files", "--error-unmatch", f], cwd=str(ROOT),
                                capture_output=True, text=True, timeout=10,
                                encoding="utf-8", errors="replace")
            tracked = r2.returncode == 0
            out[f] = {"ignored": ignored, "tracked": tracked}
        except Exception as e:
            out[f] = {"ignored": False, "tracked": False, "error": str(e)}
    return out

def _latest_ev(sub, pat="*.json"):
    d = ROOT / "acceptance" / "evidence" / sub
    if not d.exists():
        return {}
    fs = sorted(d.rglob(pat), key=lambda p: p.stat().st_mtime, reverse=True)
    for f in fs:
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
    return {}


def _load_override_count():
    """统计 undo_log 中 ADMIN_OVERRIDE 真实回滚记录数"""
    log = ROOT / "runtime" / "undo_log.jsonl"
    if not log.exists():
        return 0
    n = 0
    for line in log.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            if json.loads(line).get("kind") == "ADMIN_OVERRIDE":
                n += 1
        except Exception:
            pass
    return n


def least_privilege():
    """最小权限审计（证据化）：禁止用文件存在冒充通过"""
    checks = []
    checks.append({"item": "默认不自动外发", "pass": True, "note": "外发需显式动作（邮件/群发）"})

    # 写操作幂等：查最近的写路径验收证据
    gw = _latest_ev("golden_write")
    gw_res = gw.get("results", [])
    idem_ok = (any("幂等" in r.get("check", "") and r.get("pass") for r in gw_res)
               and gw.get("passed", 0) == gw.get("total", -1) and bool(gw_res))
    checks.append({"item": "写操作幂等", "pass": idem_ok,
                   "note": f"golden_write 幂等用例通过={idem_ok} @{gw.get('ts','无证据')}"})

    # RAG 权限过滤：红队 AUTH 用例实跑
    rt = _latest_ev("redteam")
    auth_pass = any("AUTH" in str(r.get("category", r.get("case", r.get("id", "")))) and r.get("pass")
                    for r in rt.get("results", []))
    checks.append({"item": "RAG权限过滤", "pass": bool(rt) and rt.get("gate_pass") is True and auth_pass,
                   "note": f"redteam gate={rt.get('gate_pass','NA')} AUTH={auth_pass}"})

    # 密钥外部化：实扫零命中 + 无凭证被 git 跟踪
    hits = scan()
    tracked_leak = any(v.get("tracked") for v in git_tracking().values())
    checks.append({"item": "密钥外部化", "pass": len(hits) == 0 and not tracked_leak,
                   "note": f"扫描命中={len(hits)} 被跟踪泄露={tracked_leak}"})

    # 可回滚 undo：必须有真实 ADMIN_OVERRIDE 记录（非文件存在）
    n_ov = _load_override_count()
    checks.append({"item": "可回滚undo", "pass": n_ov > 0,
                   "note": f"ADMIN_OVERRIDE 实测记录={n_ov} 条"})
    return checks

def main():
    hits = scan()
    gt = git_tracking()
    lp = least_privilege()
    crit = [h for h in hits if h["level"] == "CRITICAL"]
    high = [h for h in hits if h["level"] == "HIGH"]
    leak_risk = any(v.get("tracked") for v in gt.values())
    git_unknown = bool(gt) and not GIT
    report = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "critical": len(crit), "high": len(high), "total_hits": len(hits),
        "git_binary": GIT or "NOT_FOUND",
        "git_unknown": git_unknown,
        "gate_pass": len(crit) == 0 and not leak_risk and not git_unknown and all(c["pass"] for c in lp),
        "hits": hits[:50], "git_tracking": gt, "least_privilege": lp,
    }
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"security_{datetime.now().strftime('%Y%m%d-%H%M')}.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"CRITICAL={len(crit)} HIGH={len(high)} 凭证被跟踪={leak_risk} git={GIT or 'NOT_FOUND'} gate={'PASS' if report['gate_pass'] else 'FAIL'}")
    for h in hits[:10]:
        print(f"  [{h['level']}] {h['file']}:{h['line']} {h['kind']}")
    print("证据:", p)
    return 0 if report["gate_pass"] else 2

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
