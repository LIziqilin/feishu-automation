#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
幂等键模块（M1）— 关闭一票否决 #4「高风险操作不可回滚」
=====================================================
为写操作提供：幂等键生成 + 去重 + 可逆日志(undo log)。
- 所有写操作以 idem_key 去重，重复请求返回首次结果，不重复写入。
- 记录 undo 操作，支持一键回滚。
- append-only：撤销记为反向操作，不删原记录（R2）。
"""
import json, time, hashlib, os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IDEM_DIR = ROOT / "runtime" / "idempotency"
UNDO_LOG = ROOT / "runtime" / "undo_log.jsonl"

def make_key(action, target, payload):
    """确定性幂等键：同操作+同目标+同内容 → 同键"""
    raw = f"{action}|{target}|{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

def _store_path(key):
    IDEM_DIR.mkdir(parents=True, exist_ok=True)
    return IDEM_DIR / f"{key}.json"

def check(key):
    """返回 (is_duplicate, prev_result)"""
    p = _store_path(key)
    if p.exists():
        try:
            return True, json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return False, None
    return False, None

def record(key, action, target, result, undo=None, ttl_days=30):
    """记录已执行写操作 + 可选 undo 描述"""
    p = _store_path(key)
    rec = {
        "key": key, "action": action, "target": target,
        "result": result, "undo": undo,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "expire_at": time.time() + ttl_days * 86400,
    }
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    if undo:
        UNDO_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(UNDO_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec

def guarded_write(key, action, target, do_fn, undo_spec=None):
    """
    幂等执行包装：do_fn() 只在首次执行；重复调用返回缓存结果。
    do_fn 返回 result(dict)。undo_spec 为可回滚描述(dict)。
    """
    dup, prev = check(key)
    if dup:
        return {"status": "duplicate", "reused": True, "result": prev.get("result")}
    result = do_fn()
    record(key, action, target, result, undo=undo_spec)
    return {"status": "executed", "reused": False, "result": result}

def _append_override(target_rec, apply_out):
    """R2：修正/回滚以 append 方式记 ADMIN_OVERRIDE，不删原流水"""
    UNDO_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "kind": "ADMIN_OVERRIDE",
        "ts": datetime.now().isoformat(timespec="seconds"),
        "ref_key": target_rec.get("key"),
        "ref_action": target_rec.get("action"),
        "apply": apply_out,
        "note": "回滚为反向操作记录；原流水保留（R2 append-only）",
    }
    with open(UNDO_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def rollback(key_key=None, mode="last", apply=False, allow_prod=False):
    """
    回滚：按 undo log 反向执行。
    - 默认 apply=False：仅返回 undo 描述（只读预演）。
    - apply=True：真实执行反向操作，需通过安全闸门：
        R1/R3：默认仅允许 TEST_ 前缀目标（生产需 allow_prod=True 且记录 ADMIN_OVERRIDE）
        R3：禁止删除记录（op=delete_record 一律拒绝）
        R2：回滚记为 ADMIN_OVERRIDE 追加写，不删原流水
    """
    if not UNDO_LOG.exists():
        return {"status": "empty", "message": "无 undo 记录"}
    recs = [json.loads(l) for l in UNDO_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    recs = [r for r in recs if r.get("kind") != "ADMIN_OVERRIDE"]
    if not recs:
        return {"status": "empty"}
    target = recs[-1] if mode == "last" else next((r for r in recs if r["key"] == key_key), None)
    if not target:
        return {"status": "not_found"}
    spec = target.get("undo")
    out = {"status": "ready", "undo_of": target["action"], "undo_spec": spec,
           "hint": "确认后执行反向操作（R2: 记 ADMIN_OVERRIDE，不删原流水）"}

    if not apply:
        return out

    if not spec:
        out["status"] = "no_undo_spec"
        return out

    op = spec.get("op")
    if op == "delete_record":
        out["status"] = "blocked"
        out["reason"] = "R3 禁止删除记录；请改用软归档(状态→已取消)"
        return out

    is_test = str(target.get("target", "")).startswith("TEST_")
    if not is_test and not allow_prod:
        out["status"] = "blocked_non_test"
        out["reason"] = "非 TEST_ 目标默认拒绝；如确需生产回滚请显式 allow_prod=True"
        return out

    if op == "update":
        tid = spec.get("table_id"); rid = spec.get("record_id")
        try:
            import v15_features as vf
            vf.update_record(tid, rid, spec.get("fields", {}))
            out["status"] = "applied"
            out["applied"] = {"op": op, "table_id": tid, "record_id": rid, "fields": spec.get("fields")}
        except Exception as e:
            out["status"] = "apply_failed"
            out["error"] = str(e)[:200]
            return out
    else:
        out["status"] = "unsupported_op"
        out["reason"] = f"未支持的反向操作: {op}"
        return out

    out["override"] = _append_override(target, out)["ts"]
    return out

if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    k = make_key("create_task", "tblz3H4lV7PCrBrX", {"title": "测试任务"})
    print("幂等键:", k)
    r1 = guarded_write(k, "create_task", "tblz3H4lV7PCrBrX", lambda: {"record_id": "rec_TEST", "ok": True},
                       undo_spec={"op": "delete_record", "record_id": "rec_TEST"})
    r2 = guarded_write(k, "create_task", "tblz3H4lV7PCrBrX", lambda: {"record_id": "rec_DUP", "ok": True})
    print("首次:", r1["status"], "| 重复:", r2["status"])
    print("回滚查询:", rollback()["status"])
