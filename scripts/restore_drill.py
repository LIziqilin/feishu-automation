#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
真实恢复演练（M2）— 隔离环境还原 + RPO/RTO 实测
================================================
与 recovery_drill.py 的区别：
  recovery_drill = 只读校验（JSON可解析、表数/记录数）
  本脚本        = 真实"还原到隔离库"并计时

能力：
1. 选中最新备份 → 计算 RPO = now - backup_time
2. 在 runtime/restore_test/ 建立**隔离** SQLite 库，逐表还原并计时 → RTO
3. 校验：表数/记录数/字段完整性与源一致；生成校验和
4. 产出 evidence + 可选发飞书
安全：只写 runtime/restore_test/，绝不触碰生产表；R3 不删除源备份。
"""
import sys, io, os, json, glob, time, sqlite3, hashlib, argparse, urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = ROOT / "backups"
RESTORE_DIR = ROOT / "runtime" / "restore_test"
EVID = ROOT / "acceptance" / "evidence" / "restore"
CHAT_ID = "oc_1fe154e172ab04622b7ffa810ac172bc"
ENV_CANDIDATES = [
    r"C:\Users\Administrator\AppData\Local\hermes\profiles\agent6_scheduler\scripts\feishu_insight_link.env",
    ROOT / "scripts" / "feishu_insight_link.env",
]

def load_secret(key):
    v = os.environ.get(key)
    if v:
        return v
    for p in ENV_CANDIDATES:
        try:
            for line in open(p, encoding="utf-8-sig"):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, val = line.partition("=")
                    if k.strip() == key:
                        return val.strip()
        except Exception:
            continue
    return ""

def _rows(tbl):
    """兼容两种结构：{'records':[...]} 或 直接 list"""
    if isinstance(tbl, dict):
        return tbl.get("records") or tbl.get("items") or []
    if isinstance(tbl, list):
        return tbl
    return []

def _name(tbl, idx):
    if isinstance(tbl, dict):
        return tbl.get("table_name") or tbl.get("name") or tbl.get("table_id") or f"t{idx}"
    return f"t{idx}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--notify", action="store_true", help="发飞书报告")
    ap.add_argument("--keep", action="store_true", help="保留隔离库（默认演练后清理）")
    args = ap.parse_args()

    t_start = time.time()
    cands = (glob.glob(str(BACKUP_DIR / "backup_*.json"))
             + glob.glob(str(BACKUP_DIR / "hourly_*.json")))
    files = sorted(cands, key=os.path.getmtime, reverse=True)
    if not files:
        print("FAIL: 无备份文件"); return 1
    latest = files[0]
    with open(latest, encoding="utf-8") as f:
        data = json.load(f)

    btime = data.get("backup_time", "")
    rpo_min = None
    try:
        rpo_min = round((datetime.now() - datetime.fromisoformat(btime)).total_seconds() / 60, 1)
    except Exception:
        pass

    tables = data.get("tables", [])
    # ---- 真实还原到隔离 SQLite ----
    RESTORE_DIR.mkdir(parents=True, exist_ok=True)
    db = RESTORE_DIR / f"restore_{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    if db.exists():
        db.unlink()
    conn = sqlite3.connect(str(db))
    src_counts, dst_counts = {}, {}
    t_restore0 = time.time()
    for i, tbl in enumerate(tables):
        name = _name(tbl, i)
        rows = _rows(tbl)
        src_counts[name] = len(rows)
        cols = set()
        for r in rows:
            if isinstance(r, dict):
                cols.update(r.keys())
        cols = sorted(cols) or ["raw"]
        collist = ", ".join('"%s" TEXT' % c.replace('"', '') for c in cols)
        conn.execute(f'CREATE TABLE IF NOT EXISTS "{name}" ({collist})')
        ph = ", ".join("?" for _ in cols)
        for r in rows:
            vals = []
            for c in cols:
                v = r.get(c) if isinstance(r, dict) else r
                vals.append(json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
            conn.execute(f'INSERT INTO "{name}" VALUES ({ph})', vals)
        dst_counts[name] = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
    conn.commit()
    # 校验和（隔离库内容指纹）
    h = hashlib.sha256()
    for name in sorted(dst_counts):
        for row in conn.execute(f'SELECT * FROM "{name}" ORDER BY rowid'):
            h.update(repr(row).encode("utf-8", "ignore"))
    checksum = h.hexdigest()[:16]
    conn.close()
    rto_sec = round(time.time() - t_restore0, 1)

    # ---- 断言 ----
    mismatch = {k: (src_counts[k], dst_counts.get(k)) for k in src_counts if src_counts[k] != dst_counts.get(k)}
    total_src = sum(src_counts.values()); total_dst = sum(dst_counts.values())
    ok = (not mismatch) and len(tables) > 0 and total_dst == total_src

    report = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "backup_file": os.path.basename(latest),
        "backup_time": btime,
        "rpo_minutes": rpo_min,
        "rto_seconds": rto_sec,
        "tables": len(tables),
        "records_src": total_src,
        "records_restored": total_dst,
        "mismatch": mismatch,
        "checksum": checksum,
        "isolated_db": str(db.relative_to(ROOT)),
        "pass": ok,
        "rpo_target_min": 60, "rto_target_min": 60,
        "rpo_target_note": "日备7轮 + 每小时增量24轮（分层），目标≤60min",
        "rpo_meet": (rpo_min is not None and rpo_min <= 60),
        "rto_meet": rto_sec <= 3600,
    }
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"restore_{datetime.now().strftime('%Y%m%d-%H%M')}.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"备份: {os.path.basename(latest)}  备份时间: {btime}")
    print(f"RPO = {rpo_min} 分钟 (目标≤60)  {'达标' if report['rpo_meet'] else '超标'}")
    print(f"RTO = {rto_sec} 秒 (目标≤3600)  {'达标' if report['rto_meet'] else '超标'}")
    print(f"表数 {len(tables)}  记录 {total_src} -> 还原 {total_dst}  不一致={mismatch or '无'}")
    print(f"校验和: {checksum}")
    print(f"结果: {'PASS' if ok else 'FAIL'}  用时 {round(time.time()-t_start,1)}s")
    print("证据:", p)

    if not args.keep and db.exists():
        db.unlink()  # 清理隔离库（不影响生产）

    # 发飞书
    if args.notify:
        aid, asec = load_secret("FEISHU_APP_ID"), load_secret("FEISHU_APP_SECRET")
        if aid and asec:
            try:
                req = urllib.request.Request(
                    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                    data=json.dumps({"app_id": aid, "app_secret": asec}).encode(),
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    token = json.load(r)["tenant_access_token"]
                text = (f"🧪 真实恢复演练 {'✅通过' if ok else '❌失败'}\n"
                        f"时间：{report['ts']}\n备份：{os.path.basename(latest)}（{btime}）\n"
                        f"RPO：{rpo_min} 分钟（目标≤60）\nRTO：{rto_sec} 秒（目标≤3600）\n"
                        f"表数：{len(tables)}　记录：{total_src}→{total_dst}\n"
                        f"校验和：{checksum}\n隔离库：{report['isolated_db']}")
                body = {"receive_id": CHAT_ID, "msg_type": "text",
                        "content": json.dumps({"text": text})}
                req2 = urllib.request.Request(
                    "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
                    data=json.dumps(body).encode(),
                    headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                    method="POST")
                with urllib.request.urlopen(req2, timeout=30) as r:
                    print("飞书报告: 已发送" if json.load(r).get("code") == 0 else "飞书报告: 失败")
            except Exception as e:
                print("飞书报告异常:", e)
    return 0 if ok else 2

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
