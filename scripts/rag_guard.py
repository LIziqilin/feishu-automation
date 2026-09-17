#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RAG 护栏（M2）— 关闭一票否决 #5「RAG无来源可呈现高风险事实」
==========================================================
职责：
1. 权限过滤：按用户角色过滤知识条目（最小权限）。
2. 引文校验：回答中的事实必须能追溯到来源；无来源 → 强制拒答/标注不确定。
3. 高危标记：涉及金额/规范/承诺类，无引用一律拒答。
4. 索引版本：记录索引快照版本，保证可复现。
"""
import json, hashlib, re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX_META = ROOT / "runtime" / "rag" / "index_version.json"

HIGH_RISK_TERMS = ["金额", "付款", "合同", "规范", "强条", "承重", "消防", "资质",
                   "报价", "索赔", "承诺", "合规", "验收标准", "法定"]

REFUSAL = "【无法核实】该信息未在知识库中找到可靠来源，我不能提供确定性结论。请补充资料或转人工确认。"

def index_version():
    """索引版本（可复现）：由知识库文件清单哈希决定"""
    cands = [ROOT / "docs", ROOT.parent / "docs"]
    kb = next((p for p in cands if p.exists()), cands[0])
    files = sorted([str(p.relative_to(kb)) for p in kb.rglob("*.md")]) if kb.exists() else []
    h = hashlib.sha256("|".join(files).encode()).hexdigest()[:12]
    meta = {"version": h, "file_count": len(files), "ts": datetime.now().isoformat(timespec="seconds")}
    INDEX_META.parent.mkdir(parents=True, exist_ok=True)
    INDEX_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta

def _has(need, user_perm):
    """最小权限判定（修正越权）：
       - 无需权限(none/空) → 可读
       - admin 通吃
       - 否则要求命名空间与动作**完全相等**
    历史缺陷：曾用 user_perm.startswith(need.split(':')[0]+':') 导致
    read:admin 与 read:kb 同前缀即互认（越权）。
    """
    if not need or need == "none":
        return True
    if user_perm == "admin":
        return True
    return user_perm == need

def filter_by_permission(chunks, user_perm="read:kb"):
    """chunks: [{content, source, required_perm}]  → 仅保留用户有权访问的"""
    return [c for c in chunks if _has(c.get("required_perm"), user_perm)]

def verify_citations(answer, chunks):
    """
    校验回答是否有引用支撑。返回 {ok, cited, missing, high_risk, action}
    - 若回答含高危词但无引用 → action=refuse
    - 若有引用 → action=accept
    - 若无引用且非高危 → action=mark_uncertain
    """
    cited = []
    missing = []
    for c in chunks:
        src = c.get("source", "")
        if src and src in answer:
            cited.append(src)
    high_risk = any(t in answer for t in HIGH_RISK_TERMS)
    if cited:
        action = "accept"
    elif high_risk:
        action = "refuse"
    else:
        action = "mark_uncertain"
    return {"ok": bool(cited), "cited": cited, "missing": missing,
            "high_risk": high_risk, "action": action}

def guard_answer(answer, chunks, user_perm="read:kb"):
    """对外主入口：先权限过滤，再引文校验，必要时替换为拒答"""
    allowed = filter_by_permission(chunks, user_perm)
    v = verify_citations(answer, allowed)
    if v["action"] == "refuse":
        return {"answer": REFUSAL, "verdict": v, "blocked": True,
                "reason": "high_risk_without_citation"}
    if v["action"] == "mark_uncertain" and not v["ok"]:
        return {"answer": answer + "\n\n（注：以上内容未经知识库来源核实，仅供参考。）",
                "verdict": v, "blocked": False, "reason": "uncited_noncritical"}
    return {"answer": answer, "verdict": v, "blocked": False, "reason": "ok"}

if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print("索引版本:", index_version())
    chunks = [
        {"content": "电梯维保SLA响应时限2小时", "source": "维保SLA.md", "required_perm": "read:kb"},
        {"content": "内部报价底价", "source": "报价底线.md", "required_perm": "admin"},
    ]
    print("普通用户可见:", [c["source"] for c in filter_by_permission(chunks, "read:kb")])
    r = guard_answer("电梯维保SLA响应时限为2小时，依据维保SLA.md。", chunks, "read:kb")
    print("带引用:", r["blocked"], r["verdict"]["action"])
    r2 = guard_answer("这个项目报价金额是100万。", chunks, "read:kb")
    print("高危无引用:", r2["blocked"], r2["reason"])
