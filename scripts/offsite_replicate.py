#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
异地/隔离副本复制（M2）
================================
目标：在独立物理卷上建立备份副本（异地），降低单盘故障/误删风险。
设计（诚实）：
- 源：backups/*.json（分层备份产物）
- 目标：环境变量 V16_OFFSITE_DIR，默认 D:\\AI-Backups\\V16_Offsite（D盘物理卷，与C盘隔离）
- 策略：copy-on-new（仅复制目标缺失/更新的文件），保留最近 N 份（默认 96，避免无限增长）
- 校验：复制后逐文件比对字节数，失败即 FAIL（绝不静默）
- 不删除源文件（R3）；仅轮换目标副本层
输出证据：acceptance/evidence/offsite/offsite_<ts>.json
"""
import os, sys, io, json, shutil, hashlib, argparse, subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "backups"
EVID = ROOT / "acceptance" / "evidence" / "offsite"
DEFAULT_DST = r"D:\AI-Backups\V16_Offsite"
KEEP = 96  # 目标层最多保留份数


def sha(p, buf=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()



def push_to_lark(local_dir, evidence):
    """R-14/异地备份升级：把本地 backups 镜像到飞书云盘文件夹。
    token 来源：环境变量 LARK_DRIVE_FOLDER_TOKEN > scripts/lark_drive_secrets.env；
    未配置则跳过，保持本地 D 盘备份，零破坏。
    注意：lark-cli 的 --local-dir 有白名单，必须 cwd=backups 且传 "."。"""
    folder = os.environ.get("LARK_DRIVE_FOLDER_TOKEN", "").strip()
    if not folder:
        sec = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lark_drive_secrets.env")
        if os.path.exists(sec):
            try:
                with open(sec, encoding="utf-8-sig") as f:
                    for line in f:
                        if line.strip().startswith("LARK_DRIVE_FOLDER_TOKEN="):
                            folder = line.strip().split("=", 1)[1].strip()
            except Exception:
                pass
    if not folder:
        evidence["lark_drive"] = "skipped(no LARK_DRIVE_FOLDER_TOKEN)"
        return
    cli = os.environ.get("LARK_CLI",
        r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd")
    cmd = [cli, "drive", "+push",
           "--local-dir", ".",
           "--folder-token", folder,
           "--if-exists", "smart",
           "--as", "bot", "--format", "json"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=300,
                           cwd=str(local_dir),
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        if r.returncode == 0:
            evidence["lark_drive"] = "PUSHED"
        else:
            err = (r.stderr or b"").decode("utf-8", "replace")[:200]
            evidence["lark_drive"] = f"FAIL: {err}"
    except Exception as e:
        evidence["lark_drive"] = f"EXC: {e}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dst", default=os.environ.get("V16_OFFSITE_DIR", DEFAULT_DST))
    ap.add_argument("--keep", type=int, default=KEEP)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    dst = Path(args.dst)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    EVID.mkdir(parents=True, exist_ok=True)
    result = {"ts": ts, "src": str(SRC), "dst": str(dst), "copied": [], "verified": [],
              "skipped": [], "failed": [], "dry_run": args.dry_run}

    if not SRC.exists():
        result["status"] = "no_source"
        push_to_lark(SRC, result)
        _save(result)
        return 2

    src_files = sorted(SRC.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not src_files:
        result["status"] = "no_files"
        _save(result)
        return 2

    if not args.dry_run:
        dst.mkdir(parents=True, exist_ok=True)

    for f in src_files:
        target = dst / f.name
        if target.exists() and target.stat().st_size == f.stat().st_size:
            result["skipped"].append(f.name)
            continue
        if args.dry_run:
            result["copied"].append(f.name)
            continue
        try:
            shutil.copy2(f, target)
            if target.stat().st_size == f.stat().st_size and sha(target) == sha(f):
                result["verified"].append(f.name)
                result["copied"].append(f.name)
            else:
                result["failed"].append({"file": f.name, "reason": "size/hash mismatch"})
        except Exception as e:
            result["failed"].append({"file": f.name, "reason": str(e)[:150]})

    # 目标层轮换（只轮换副本，不删源 R3）
    if not args.dry_run:
        copies = sorted(dst.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in copies[args.keep:]:
            try:
                old.unlink()
                result.setdefault("rotated_out", []).append(old.name)
            except Exception:
                pass

    ok = not result["failed"] and (len(result["copied"]) >= 1 or len(result["skipped"]) >= 1)
    result["status"] = "PASS" if ok else "FAIL"
    result["counts"] = {"src": len(src_files), "copied": len(result["copied"]),
                        "verified": len(result["verified"]), "skipped": len(result["skipped"]),
                        "failed": len(result["failed"])}
    push_to_lark(SRC, result)
    _save(result)
    print(f"异地副本 {result['status']} | 源{len(src_files)} 新复制{len(result['copied'])} "
          f"校验{len(result['verified'])} 跳过{len(result['skipped'])} 失败{len(result['failed'])}")
    print("目标:", dst)
    print("证据:", EVID / f"offsite_{ts}.json")
    return 0 if ok else 3


def _save(r):
    p = EVID / f"offsite_{r['ts']}.json"
    p.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
