# -*- coding: utf-8 -*-
"""
GT-01 / GT-02 写路径端到端验收 V3（含幂等、真实回滚、负路径）
合规：R1/R3 → 全部 TEST_ 前缀；回滚用软归档；绝不删除
输出：acceptance/evidence/golden_write/<ts>.json
"""
import io, sys, json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, r"D:\AI-Tools\feishu\V13方案增强\scripts")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import v15_features as vf
import idempotency as idm

TASK_TABLE = "tblz3H4lV7PCrBrX"
ROOT = Path(r"D:\AI-Tools\feishu\V13方案增强")
EVID = ROOT / "acceptance" / "evidence" / "golden_write"
EVID.mkdir(parents=True, exist_ok=True)
ts = datetime.now().strftime("%Y%m%d-%H%M%S")
mark = datetime.now().strftime("%H%M%S")
results, created = [], []


def rec(gt, path, name, ok, detail, extra=None):
    results.append({"gt": gt, "path": path, "check": name, "pass": bool(ok),
                    "detail": str(detail)[:200], **(extra or {})})
    print(f"  [{'PASS' if ok else 'FAIL'}] {gt}/{path} {name}: {str(detail)[:130]}")


def rid_of(resp):
    try:
        return resp["data"]["record"]["record_id"]
    except Exception:
        return None


try:
    # ================= GT-01 创建（黄金路径） =================
    name = f"TEST_写路径验收_{mark}"
    key = idm.make_key("GT-01", "create_task", name)
    c0 = idm.check(key)
    rec("GT-01", "golden", "幂等:首次非重复", not (isinstance(c0, tuple) and c0[0]), f"check={c0}")

    resp = vf.create_record(TASK_TABLE, {"任务名称": name, "状态": "进行中", "类别": "学习",
                                         "优先级": "低", "科目": "认知", "是否卡他人": "否",
                                         "创建日期": vf.date_ms()})
    rid = rid_of(resp)
    created.append(rid)
    rec("GT-01", "golden", "创建成功且业务码=0", resp.get("code") == 0 and bool(rid), f"rid={rid}")

    found = [r for r in vf.list_records(TASK_TABLE) if r.get("fields", {}).get("任务名称") == name]
    rec("GT-01", "golden", "断言:记录数=1", len(found) == 1, f"matches={len(found)}")
    st = vf.cell_select(found[0]["fields"].get("状态")) if found else None
    rec("GT-01", "golden", "断言:状态=进行中", st == "进行中", f"status={st}")

    idm.record(key, "create_task", name, {"record_id": rid},
               undo={"op": "update", "table_id": TASK_TABLE, "record_id": rid,
                     "fields": {"状态": "已取消"}})
    c1 = idm.check(key)
    rec("GT-01", "golden", "幂等:重复键被识别", isinstance(c1, tuple) and c1[0] is True,
        f"dup_key={c1[1].get('key') if isinstance(c1, tuple) and isinstance(c1[1], dict) else None}")

    # ---- 负路径：非法字段（fail-loud 修复后应抛 BitableError） ----
    try:
        vf.create_record(TASK_TABLE, {"不存在的字段XYZ": "x", "任务名称": name + "_bad"})
        rec("GT-01", "negative", "非法字段必须报错", False, "未抛错→fail-loud缺失")
    except vf.BitableError as e:
        rec("GT-01", "negative", "非法字段必须报错", True, f"BitableError code={e.code} {e.msg}")
    except Exception as e:
        rec("GT-01", "negative", "非法字段必须报错", True, f"{type(e).__name__}: {str(e)[:100]}")

    # ---- 负路径：空名称（服务端未校验→如实记录） ----
    try:
        r_empty = vf.create_record(TASK_TABLE, {"任务名称": "", "状态": "进行中"})
        created.append(rid_of(r_empty))
        rec("GT-01", "negative", "空名称校验", False,
            "服务端接受空名称(code=0)→本地缺少输入校验，缺陷")
    except Exception as e:
        rec("GT-01", "negative", "空名称校验", True, f"已拒绝: {str(e)[:100]}")

    # ---- 负路径：越权 token ----
    import urllib.request as _u
    try:
        rr = _u.Request(f"https://open.feishu.cn/open-apis/bitable/v1/apps/{vf.BASE_TOKEN}/tables/{TASK_TABLE}/records",
                        headers={"Authorization": "Bearer invalid_token_negative_test"})
        _u.urlopen(rr, timeout=10)
        rec("GT-01", "negative", "越权token必须被拒", False, "非法token通过")
    except Exception as e:
        rec("GT-01", "negative", "越权token必须被拒", True, f"已拒绝: {str(e)[:90]}")

    # ================= GT-02 完成 + 真实回滚 =================
    if rid:
        up = vf.update_record(TASK_TABLE, rid, {"状态": "已完成", "实际完成日期": vf.date_ms()})
        rec("GT-02", "golden", "更新业务码=0", up.get("code") == 0, f"code={up.get('code')}")
        a = [r for r in vf.list_records(TASK_TABLE) if r.get("record_id") == rid]
        rec("GT-02", "golden", "断言:状态=已完成",
            vf.cell_select(a[0]["fields"].get("状态")) == "已完成" if a else False,
            f"status={vf.cell_select(a[0]['fields'].get('状态')) if a else None}")
        rec("GT-02", "golden", "断言:完成日期非空",
            bool(a[0]["fields"].get("实际完成日期")) if a else False, "")

        # 只读预演
        pre = idm.rollback(key)
        rec("GT-02", "golden", "回滚预演(只读)", pre.get("status") == "ready", f"{pre.get('status')}")

        # 真实回滚（apply）
        rb = idm.rollback(key, apply=True)
        rec("GT-02", "golden", "回滚真实执行", rb.get("status") == "applied", f"status={rb.get('status')} {rb.get('reason','')}")
        a2 = [r for r in vf.list_records(TASK_TABLE) if r.get("record_id") == rid]
        s3 = vf.cell_select(a2[0]["fields"].get("状态")) if a2 else None
        rec("GT-02", "golden", "断言:回滚后=已取消", s3 == "已取消", f"status={s3}")
        rec("GT-02", "golden", "R2:ADMIN_OVERRIDE已追加", bool(rb.get("override")), f"ts={rb.get('override')}")

        # ---- 负路径：R3 禁止删除型回滚 ----
        k2 = idm.make_key("GT-02", "delete_task", name + "_del")
        idm.record(k2, "delete_task", name + "_del", {"record_id": rid},
                   undo={"op": "delete_record", "table_id": TASK_TABLE, "record_id": rid})
        blk = idm.rollback(k2, apply=True)
        rec("GT-02", "negative", "R3:删除型回滚被拦截", blk.get("status") == "blocked",
            f"status={blk.get('status')} {blk.get('reason','')}")

        # ---- 负路径：非TEST_目标默认拒绝 ----
        k3 = idm.make_key("GT-02", "prod_task", "真实生产任务样例")
        idm.record(k3, "prod_task", "真实生产任务样例", {"record_id": rid},
                   undo={"op": "update", "table_id": TASK_TABLE, "record_id": rid, "fields": {"状态": "已取消"}})
        blk2 = idm.rollback(k3, apply=True)
        rec("GT-02", "negative", "非TEST_目标默认拒绝", blk2.get("status") == "blocked_non_test",
            f"status={blk2.get('status')}")

        # ---- 负路径：不存在记录 ----
        try:
            vf.update_record(TASK_TABLE, "recNOTEXIST0000", {"状态": "已完成"})
            rec("GT-02", "negative", "不存在record必须报错", False, "未抛错")
        except Exception as e:
            rec("GT-02", "negative", "不存在record必须报错", True, f"{type(e).__name__} {str(e)[:90]}")

finally:
    for cid in created:
        if cid:
            try:
                vf.update_record(TASK_TABLE, cid, {"状态": "已取消",
                                                   "复盘备注": "TEST_前缀写路径验收残留→软归档"})
            except Exception as e:
                print("  清理告警:", str(e)[:70])
    passed = sum(1 for r in results if r["pass"])
    rep = {"ts": ts, "total": len(results), "passed": passed,
           "pass_rate": round(passed / len(results), 4) if results else 0.0,
           "created_record_ids": created, "results": results}
    p = EVID / f"golden_write_{ts}.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGT-01/GT-02 写路径: {passed}/{len(results)}")
    print("证据:", p)
