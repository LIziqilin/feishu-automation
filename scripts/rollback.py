#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
版本回滚工具（R-12）— 只读优先、绝不删除
=======================================
能力：
  --list            列出可回滚版本（git 提交 + 标签）
  --plan <rev>      生成回滚计划（dry-run，不执行）
  --apply <rev>     仅对**非生产代码文件**执行 `git checkout <rev> -- <file>`（不删任何文件，R3）
  --snapshot        打回滚锚点标签（rollback-anchor-<ts>）
安全约束：
  - 默认 dry-run；--apply 需显式传入且仅允许在白名单路径（scripts/acceptance/docs）恢复。
  - 永不执行 git reset --hard / git clean / 删除文件。
"""
import sys, io, os, json, subprocess, argparse
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVID = ROOT / "acceptance" / "evidence" / "rollback"
WHITELIST = ("scripts/", "acceptance/", "docs/")

def _find_git():
    """解析真实 git 可执行文件（避开无法直接 CreateProcess 的 .cmd 包装）"""
    cand = []
    env = os.environ.get("QCLAW_GIT_BINARY")
    if env:
        cand.append(env)
    cand += [
        r"C:\Program Files\QClaw\v0.2.36.629\resources\git\cmd\git.exe",
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
    ]
    for c in cand:
        if c and Path(c).exists():
            return c
    return "git"

GIT = _find_git()

def git(args, timeout=30):
    try:
        r = subprocess.run([GIT] + args, cwd=str(ROOT), capture_output=True,
                           text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except Exception as e:
        return 1, "", str(e)

def list_versions(limit=15):
    code, out, _ = git(["log", "--oneline", "-n", str(limit)])
    tags_code, tags, _ = git(["tag", "--list", "rollback-anchor-*"])
    return out.splitlines() if out else [], (tags.splitlines() if tags else [])

def plan(rev):
    code, out, err = git(["diff", "--name-status", f"{rev}", "HEAD"])
    if code != 0:
        return None, err
    changes = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            changes.append({"status": parts[0], "path": parts[-1]})
    restorable = [c for c in changes if c["path"].startswith(WHITELIST)]
    blocked = [c for c in changes if not c["path"].startswith(WHITELIST)]
    return {"rev": rev, "total_changed": len(changes),
            "restorable": len(restorable), "blocked": len(blocked),
            "restorable_detail": restorable[:40], "blocked_detail": blocked[:20],
            "note": "回滚仅覆盖白名单路径；删除类(D)变更需人工确认，本工具不执行"}, None

def apply(rev, dry=True):
    p, err = plan(rev)
    if p is None:
        return {"ok": False, "error": err}
    actions = []
    for c in p["restorable_detail"]:
        if c["status"] == "D":
            actions.append({**c, "action": "SKIP_DELETE_NEEDS_MANUAL(R3)"})
            continue
        if dry:
            actions.append({**c, "action": "WILL_CHECKOUT"})
        else:
            c2, o, e = git(["checkout", rev, "--", c["path"]])
            actions.append({**c, "action": "CHECKOUT_OK" if c2 == 0 else f"FAIL:{e[:60]}"})
    return {"ok": True, "rev": rev, "dry_run": dry, "applied": len(actions),
            "actions": actions[:40]}

def snapshot():
    tag = "rollback-anchor-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    code, out, err = git(["tag", tag])
    return {"ok": code == 0, "tag": tag, "error": err}

def _write_evid(r):
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / f"rollback_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json").write_text(
        json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

def self_test():
    """回滚能力自检：打锚点 + 生成计划（dry-run，不修改工作区）"""
    snap = snapshot()
    commits, tags = list_versions(limit=5)
    target = commits[1].split()[0] if len(commits) > 1 else (commits[0].split()[0] if commits else None)
    pl = None
    if target:
        pl, _ = plan(target)
    ok = bool(snap.get("ok")) and bool(commits) and (pl is not None)
    return {"ok": ok, "mode": "self_test", "anchor": snap.get("tag"),
            "commits_visible": len(commits), "plan_rev": target,
            "plan_blocked": (pl or {}).get("blocked", 0),
            "plan_restorable": (pl or {}).get("restorable", 0),
            "note": "dry-run：仅锚点+计划，不执行 git checkout，不删文件（R3）"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--plan")
    ap.add_argument("--apply")
    ap.add_argument("--snapshot", action="store_true")
    ap.add_argument("--self-test", action="store_true", help="回滚能力自检（dry-run，产出证据）")
    ap.add_argument("--yes", action="store_true", help="确认执行 --apply")
    a = ap.parse_args()

    if a.self_test:
        r = self_test()
        _write_evid(r)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["ok"] else 2
    if a.snapshot:
        r = snapshot()
        r["mode"] = "snapshot"
        _write_evid(r)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["ok"] else 2
    if a.list:
        commits, tags = list_versions()
        _write_evid({"ok": bool(commits), "mode": "list", "commits": len(commits),
                     "tags": tags})
        print("可回滚提交（近15）:")
        for c in commits:
            print("  " + c)
        print("锚点标签:", tags or "(无)")
        return 0
    if a.plan:
        p, err = plan(a.plan)
        if p is None:
            print("ERR:", err); return 2
        print(json.dumps(p, ensure_ascii=False, indent=2))
        return 0
    if a.apply:
        dry = not a.yes
        r = apply(a.apply, dry=dry)
        r["mode"] = "apply"
        _write_evid(r)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        if dry:
            print("\n[DRY-RUN] 加 --yes 才真正恢复（且仅白名单路径）")
        return 0 if r.get("ok") else 2
    ap.print_help()
    return 0

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
