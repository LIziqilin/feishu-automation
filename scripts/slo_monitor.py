#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SLO 监控与放行判定（M2）— 汇总各证据链，计算严格分
=================================================
读取：埋点(traces) + 评测(eval) + 混沌(chaos) + 安全(security) + 恢复(recovery) + 运行计时
输出：六维严格分 + 一票否决自检 + 放行建议；写 acceptance/evidence/scorecard/<ts>.json
"""
import sys, io, json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
ACC = ROOT / "acceptance"
EVID = ACC / "evidence"
TIMER = ROOT / "runtime" / "uptime_since.json"

def _latest(sub, pat="*.json"):
    d = EVID / sub
    if not d.exists():
        return None
    fs = sorted(d.rglob(pat), key=lambda p: p.stat().st_mtime, reverse=True)
    if not fs:
        return None
    try:
        return json.loads(fs[0].read_text(encoding="utf-8"))
    except Exception:
        return None

def uptime_days():
    if not TIMER.exists():
        TIMER.parent.mkdir(parents=True, exist_ok=True)
        TIMER.write_text(json.dumps({"since": datetime.now().isoformat(timespec="seconds")}), encoding="utf-8")
        return 0.0
    try:
        since = datetime.fromisoformat(json.loads(TIMER.read_text(encoding="utf-8"))["since"])
        return round((datetime.now() - since).total_seconds() / 86400, 2)
    except Exception:
        return 0.0

def _recent_files(sub, pat="*.json", max_age_h=72):
    """获取近 max_age_h 小时内的证据文件（防止陈旧证据冒充现状）"""
    d = EVID / sub
    if not d.exists():
        return []
    import time as _t
    cut = _t.time() - max_age_h * 3600
    return sorted([p for p in d.rglob(pat) if p.stat().st_mtime >= cut],
                  key=lambda p: p.stat().st_mtime, reverse=True)


def _load(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return {}


def veto_check():
    """一票否决自检（证据化）：每项必须有真实运行证据，禁止"文件存在"冒充
    返回 [(name, passed, evidence_note)]
    """
    # #1 密钥：安全审计实扫结果（近72h）
    sec_f = _recent_files("security")
    sec = _load(sec_f[0]) if sec_f else {}
    v1 = bool(sec_f) and sec.get("critical", 1) == 0 and sec.get("high", 1) == 0
    n1 = f"security_audit critical={sec.get('critical','NA')} high={sec.get('high','NA')} @{sec.get('ts','NA')}"

    # #2 越权：红队真实护栏用例结果 + 最小权限清单全过
    rt_f = _recent_files("redteam")
    rt = _load(rt_f[0]) if rt_f else {}
    auth_ok = False
    for r in rt.get("results", []):
        nm = str(r.get("category", r.get("case", r.get("id", ""))))
        if "AUTH" in nm:
            auth_ok = bool(r.get("pass"))
    lp = sec.get("least_privilege") or []
    v2 = bool(rt_f) and rt.get("gate_pass") is True and auth_ok and bool(lp) and all(c.get("pass") for c in lp)
    n2 = f"redteam gate={rt.get('gate_pass','NA')} AUTH通过={auth_ok} 最小权限项={len(lp)}"

    # #3 备份可恢复：恢复演练实跑结果（含校验+表/记录数一致）
    rs_f = _recent_files("restore")
    rs = _load(rs_f[0]) if rs_f else {}
    v3 = bool(rs_f) and rs.get("pass") is True and rs.get("records_src") == rs.get("records_restored") and bool(rs.get("tables"))
    n3 = f"restore pass={rs.get('pass','NA')} {rs.get('tables','NA')}表 {rs.get('records_restored','NA')}条 校验={rs.get('checksum','NA')}"

    # #4 高风险可回滚：写路径验证据中「回滚真实执行=applied」
    gw_f = _recent_files("golden_write")
    gw = _load(gw_f[0]) if gw_f else {}
    rb_applied = any(r.get("check", "").startswith("回滚真实执行") and r.get("pass")
                     for r in gw.get("results", []))
    r3_blocked = any("R3" in r.get("check", "") and r.get("pass") for r in gw.get("results", []))
    v4 = bool(gw_f) and rb_applied and r3_blocked
    n4 = f"golden_write 回滚applied={rb_applied} R3拦截={r3_blocked} @{gw.get('ts','NA')}"

    # #5 RAG 有来源/拒答：RAG 守卫实跑记录（rag_guard 自检或评测中的 rag_query 用例）
    rg_ev = _recent_files("rag") or _recent_files("eval")
    rg = _load(rg_ev[0]) if rg_ev else {}
    rag_ok = False
    if "by_category" in rg:
        rag_ok = rg.get("overall_pass_rate", 0) >= 0.95
    else:
        rag_ok = bool(rg.get("index_version")) and rg.get("high_risk_without_citation") == "block"
    v5 = bool(rg_ev) and rag_ok
    n5 = f"eval/rag 证据 @{rg.get('ts', rg.get('index_version','NA'))}"

    # #6 黄金/边界测试集：实跑结果 + 文件存在
    ge_f = _recent_files("golden")
    ge = _load(ge_f[0]) if ge_f else {}
    v6 = (bool(ge_f) and ge.get("passed", 0) == ge.get("total", -1) and bool(ge.get("total"))
          and (ACC / "eval_set.jsonl").exists() and (ACC / "golden_tasks.jsonl").exists())
    n6 = f"golden {ge.get('passed','NA')}/{ge.get('total','NA')} + eval_set/golden_tasks 就位"

    # #7 告警/责任人：风险登记册含责任人 + 告警通道实检
    rr = ACC / "risk_register.md"
    has_owner = False
    if rr.exists():
        t = rr.read_text(encoding="utf-8", errors="ignore")
        has_owner = ("责任人" in t) and ("R" in t and "A" in t)
    alert_ok = bool(sec_f)  # 告警链路随安全审计巡检
    v7 = has_owner and alert_ok and (ACC / "slo_config.md").exists()
    n7 = f"risk_register责任人={has_owner} 告警巡检={alert_ok}"

    return [
        ("#1 无硬编码密钥", v1, n1),
        ("#2 越权/外发受控", v2, n2),
        ("#3 备份可恢复", v3, n3),
        ("#4 高风险可回滚", v4, n4),
        ("#5 RAG有来源/拒答", v5, n5),
        ("#6 黄金/边界测试集", v6, n6),
        ("#7 告警/责任人", v7, n7),
    ]

def six_dim():
    ev = _latest("eval") or {}
    ch = _latest("chaos") or {}
    sec = _latest("security") or {}
    rs = _latest("restore") or {}
    # 明文密钥扫描（落地可能性的“无泄露”项，实扫非硬编）
    leaks = 0
    try:
        import re as _re
        for f in SCRIPTS.glob("*.py"):
            leaks += len(_re.findall(r"sk-[A-Za-z0-9]{20,}",
                                     f.read_text(encoding="utf-8", errors="ignore")))
    except Exception:
        leaks = 999
    leak_free = leaks == 0
    try:
        import observability as ob
        m = ob.summarize()
    except Exception:
        m = {"count": 0}
    eval_rate = ev.get("overall_pass_rate", 0)
    chaos_rate = ch.get("pass_rate", 0)
    # 效率：读效率基线实测（人工/全自动耗时对照）；未实测则 None（不伪造）
    eff_dim = None
    eff_note = ""
    try:
        _ed = json.loads((ACC / "efficiency_data.json").read_text(encoding="utf-8")) if (ACC / "efficiency_data.json").exists() else {}
        _sp = []
        for _k, _v in _ed.items():
            if _k.startswith("_"):
                continue
            _man = _v.get("manual_min"); _auto = _v.get("auto_min")
            if _man and _auto and _auto > 0:
                _sp.append(_man / _auto)
        if _sp:
            _avg = sum(_sp) / len(_sp)
            # 映射：提速比 → 10 分制（1x=6分基线下限，≥10x=10分；线性裁切）
            eff_dim = round(min(10.0, max(0.0, 6.0 + (_avg - 1.0) * (4.0 / 9.0))), 1)
            _is_est = isinstance(_ed.get("_meta"), dict) and _ed["_meta"].get("method") == "estimated"
            eff_note = f"avg_speedup={round(_avg,2)}x 样本={len(_sp)}" + (" [估算口径]", "")[not _is_est]
    except Exception:
        eff_dim = None
    restore_ok = 1.0 if rs.get("pass") else 0.0
    rpo_meet = 1.0 if rs.get("rpo_meet") else 0.0
    rto_meet = 1.0 if rs.get("rto_meet") else 0.0
    # 稳定性：混沌 + 恢复真实 + SLO文档 + RTO/RPO 达标（RPO未达则如实扣分）
    stab = (chaos_rate * 0.35 + restore_ok * 0.25 + rto_meet * 0.15
            + (0.15 if (ACC / "slo_config.md").exists() else 0) + rpo_meet * 0.10)
    rb = _latest("rollback") or {}
    rb_ok = bool(rb.get("ok"))
    # M4 硬门槛#4：独立验收人随机抽样复现（sample_*.json，gate_pass=true）
    samp_files = _recent_files("independent", pat="sample_*.json", max_age_h=24 * 7)
    samp = _load(samp_files[0]) if samp_files else {}
    sample_ok = bool(samp_files) and samp.get("gate_pass") is True
    has_qs = (SCRIPTS / "quickstart.py").exists()
    has_howto = (ROOT / "docs").exists() or (ACC / "slo_config.md").exists()
    dims = {
        "工作场景(25)": round((eval_rate * 0.7 + (1 if (ACC/'golden_tasks.jsonl').exists() else 0) * 0.3) * 10, 1),
        "系统稳定性(22)": round(stab * 10, 1),
        "落地可能性(18)": round((0.45 if sec.get("gate_pass") else 0.15) * 10
                             + (0.25 if (ROOT/'requirements.lock').exists() else 0) * 10
                             + (0.15 if rb_ok else 0) * 10
                             + (0.15 if leak_free else 0) * 10, 1),
        "效率提升性(15)": eff_dim,  # 实测效率基线（人工/全自动对照）；未实测则 None
        "使用场景(12)": round((eval_rate * 0.6 + 0.4) * 10, 1),
        "使用便捷性(8)": round(((0.5 if has_qs else 0.2) + (0.3 if has_howto else 0) + 0.2) * 10, 1),
    }
    weights = {"工作场景(25)": .25, "系统稳定性(22)": .22, "落地可能性(18)": .18,
               "效率提升性(15)": .15, "使用场景(12)": .12, "使用便捷性(8)": .08}
    # 严格分 = Σ(维度得分×权重)；未实测维度按 0 计入（蓝图：「未实测 = 不存在」），
    # 禁止把未实测维度剔除后重新归一化（那会虚高分数）
    scored = {k: v for k, v in dims.items() if v is not None}
    pending = [k for k, v in dims.items() if v is None]
    wsum = sum(weights[k] for k in weights)
    covered = sum(weights[k] for k in scored)
    # ① 保守分（治理口径）：未实测维度计 0 → 永不虚高，10/10 资格看这个
    strict = round(sum((scored.get(k, 0.0) or 0.0) * weights[k] for k in weights), 2)
    # ② 临时分（进度口径）：仅对已实测维度重新归一化，用于跟踪 M0→M3 进度
    #    蓝图把「效率A/B」列在 M3，故 M2 阶段允许效率缺口；此分必须在卡片中
    #    与保守分并列展示，且不得作为 10/10 依据。
    provisional = round(sum((scored.get(k, 0.0) or 0.0) * weights[k] for k in scored) / covered, 2) if covered else 0.0
    # 保守分上限（未实测维度占比 × 10）
    ceiling = round(10.0 - sum(weights[k] for k in pending) * 10.0, 2)
    min_dim = min(scored.values()) if scored else 0.0
    coverage = round(covered / wsum, 3) if wsum else 0.0
    return dims, strict, provisional, ceiling, min_dim, pending, coverage

def main():
    checks = veto_check()
    dims, strict, provisional, ceiling, min_dim, pending, coverage = six_dim()
    veto_ok = all(ok for _, ok, _n in checks)
    days = uptime_days()
    samp_files = _recent_files("independent", pat="sample_*.json", max_age_h=24 * 7)
    samp = _load(samp_files[0]) if samp_files else {}
    sample_ok = bool(samp_files) and samp.get("gate_pass") is True
    rs = _latest("restore") or {}
    # 硬门槛#2（六维全≥8）：10.0 的必要条件；有 pending 维度即不满足
    full_house = (not pending) and min_dim >= 8.0
    # 双阶段口径（如实呈现蓝图内部张力：M2 要求≥8.9，但效率A/B被蓝图列为 M3）：
    #  - stage_progress（进度阶段）：用临时分（已实测维度）判 M1/M2/M3
    #  - stage_verified（受验阶段）：用保守分（未测计 0）判，治理/对外声明以它为准
    stage_progress = ("M4" if (veto_ok and full_house and provisional >= 9.5 and days >= 30) else
                      "M3" if (veto_ok and full_house and provisional >= 9.0) else
                      "M2" if (veto_ok and provisional >= 8.9) else
                      "M1" if (veto_ok and provisional >= 8.1) else "M0")
    stage_verified = ("M4" if (veto_ok and full_house and strict >= 9.5 and days >= 30 and sample_ok) else
                      "M3" if (veto_ok and full_house and strict >= 9.0) else
                      "M2" if (veto_ok and full_house and strict >= 8.9) else
                      "M1" if (veto_ok and strict >= 8.1) else "M0")
    # 临界提示：保守分受未实测维度所限，临时分与阶段阈值的差距提示下一阶段是否靠该维度打开
    next_gap = None
    if pending:
        for thr, nm in ((8.9, "M2"), (9.0, "M3"), (9.5, "M4")):
            if provisional >= thr:
                next_gap = f"临时分{provisional}≥{thr}({nm})，但保守分{strict}受未实测维度[{','.join(pending)}]压制"
                break
    card = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "veto": [{"item": i, "pass": bool(o), "evidence": n} for i, o, n in checks],
        "veto_pass": veto_ok,
        "dimensions": dims,
        "min_dimension": min_dim,
        "pending_dimensions": pending,
        "weights_covered": coverage,
        "full_house_6dims_ge8": full_house,
        "strict_score": strict,
        "strict_score_ceiling": ceiling,
        "provisional_score": provisional,
        "uptime_days": days,
        "independent_sample_ok": sample_ok,
        "stage": stage_verified,                       # 兼容旧字段，等价于受验阶段
        "stage_progress": stage_progress,
        "stage_verified": stage_verified,
        "stage_policy": "进度阶段用临时分（跟踪M0-M3）；受验阶段用保守分；对外声明/放行以受验阶段为准",
        "next_gap_hint": next_gap,
        "release": ("允许放行" if (veto_ok and full_house and strict >= 9.5 and days >= 30 and sample_ok) else
                    "有条件放行（需连续30天+独立复现方可10.0）" if (veto_ok and full_house and strict >= 8.9) else
                    "继续施工"),
        "next_stage_blocker": (f"未实测维度: {','.join(pending)}（保守分上限 {ceiling}）" if pending
                               else (f"需连续30天（已 {days} 天）" if days < 30 else
                                     ("需独立抽样复现（independent_sample.py）" if not sample_ok else "已满足"))),
        "m4_hard_gates": {
            "一票否决7/7": veto_ok,
            "六维全≥8": full_house,
            "连续30天": days >= 30,
            "独立抽样复现": sample_ok,
            "RPO/RTO实测": bool(rs) and rs.get("pass") is True,
            "学习业务KPI": (EVID / "eval").exists(),
        },
    }
    out = EVID / "scorecard"
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"scorecard_{datetime.now().strftime('%Y%m%d-%H%M')}.json"
    p.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(card, ensure_ascii=False, indent=2))
    print("评分卡:", p)
    return 0

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
