# -*- coding: utf-8 -*-
"""对 V13.1 交付文档执行我在 1.5 节提出的 doc_consistency_check：
   ① 矩阵内部算术三口径自洽
   ② 各章标题分数（"X → Y" 演进式的 Y 值）与 15.1 矩阵行均同源
   ③ 15.2 三阶段对照表的 V13 / V13.1 列与两份矩阵一致
   ④ 全文出现的关键数字交叉核对
"""
import re, io, sys

DOC = r"D:\Documents\qwen-agent\5rbuuy57m9\default\V13.1增量优化-十一专家七维度深化第二轮.md"
text = io.open(DOC, encoding="utf-8").read()

DIMS = ["可行性", "稳定性", "可落地性", "效率提升", "知识转化", "便捷性", "维护简易性"]

# 15.1 矩阵（与文档同源录入）
V131 = {
    "AI 工程专家":       [4.5, 5.0, 5.0, 4.5, 4.0, 4.0, 4.5],
    "AI 专家":           [4.5, 5.0, 4.5, 5.0, 4.5, 4.0, 4.5],
    "飞书专家":          [4.5, 5.0, 4.5, 4.5, 4.0, 4.0, 4.5],
    "Coze 专家":         [4.5, 4.5, 5.0, 4.0, 4.5, 4.5, 5.0],
    "工作效率提升专家":  [4.5, 4.5, 4.5, 5.0, 4.5, 4.5, 4.5],
    "工程专家":          [4.5, 4.5, 4.5, 4.5, 4.0, 4.0, 4.5],
    "自动化工程专家":    [4.5, 5.0, 4.5, 5.0, 4.5, 4.0, 4.5],
    "软件及程序专家":    [4.5, 5.0, 5.0, 4.5, 4.0, 4.0, 4.5],
    "教育专家":          [5.0, 5.0, 4.5, 4.5, 5.0, 5.0, 5.0],
    "超级学习专家":      [4.5, 4.5, 4.5, 4.5, 5.0, 4.5, 4.5],
    "超级效率提升专家":  [4.5, 5.0, 4.5, 5.0, 4.5, 4.5, 5.0],
}
V13 = {
    "AI 工程专家":       [4.5, 4.5, 5.0, 4.5, 3.5, 4.0, 4.0],
    "AI 专家":           [4.5, 4.5, 4.5, 4.5, 4.0, 4.0, 4.0],
    "飞书专家":          [4.5, 4.5, 4.5, 4.0, 3.5, 4.0, 4.0],
    "Coze 专家":         [4.5, 4.0, 4.5, 4.0, 4.0, 4.5, 4.5],
    "工作效率提升专家":  [4.5, 4.0, 4.5, 5.0, 4.0, 4.5, 4.0],
    "工程专家":          [4.0, 4.5, 4.0, 4.5, 3.5, 4.0, 3.5],
    "自动化工程专家":    [4.5, 4.5, 4.0, 5.0, 4.0, 4.0, 4.0],
    "软件及程序专家":    [4.5, 4.5, 4.5, 4.5, 3.5, 4.0, 4.0],
    "教育专家":          [5.0, 4.5, 4.5, 4.5, 4.5, 5.0, 4.5],
    "超级学习专家":      [4.5, 4.0, 4.0, 4.5, 4.5, 4.5, 4.0],
    "超级效率提升专家":  [4.5, 4.5, 4.5, 5.0, 4.0, 4.5, 4.5],
}

fails = []

def chk(cond, msg):
    print(("  [PASS] " if cond else "  [FAIL] ") + msg)
    if not cond:
        fails.append(msg)

print("=" * 70)
print("① 15.1 矩阵内部算术三口径自洽")
print("=" * 70)
cells = sum(sum(v) for v in V131.values())
n = len(V131) * len(DIMS)
grand = cells / n
rowavg = sum(sum(v) / len(v) for v in V131.values()) / len(V131)
colavg_list = [sum(V131[e][i] for e in V131) / len(V131) for i in range(len(DIMS))]
colavg = sum(colavg_list) / len(colavg_list)
print(f"  单元格数={n} 求和={cells}")
chk(n == 77, f"单元格数应为 77，实际 {n}")
chk(abs(cells - 351.5) < 1e-9, f"求和应为 351.5，实际 {cells}")
chk(abs(grand - rowavg) < 1e-9 and abs(grand - colavg) < 1e-9,
    f"三口径自洽：总均={grand:.4f} 行均={rowavg:.4f} 列均={colavg:.4f}")
chk(f"{grand:.2f}" == "4.56", f"总均四舍五入应为 4.56，实际 {grand:.2f}")

print()
print("=" * 70)
print("② 各章标题分数（演进式 Y 值）与矩阵行均同源")
print("=" * 70)
# 抓取形如 "## 第三章 AI 工程专家视角（4.29 → **4.50**）"
pat = re.compile(r"^## 第[一二三四五六七八九十]+章\s+(.+?)视角（([\d.]+)\s*→\s*\*?\*?([\d.]+)", re.M)
found = pat.findall(text)
chk(len(found) == 11, f"应抓到 11 处章节标题演进分数，实际 {len(found)}")
for name, before, after in found:
    key = name.strip()
    if key not in V131:
        chk(False, f"章节专家名 '{key}' 未在矩阵中找到")
        continue
    mx = sum(V131[key]) / 7
    b13 = sum(V13[key]) / 7
    ok_after = abs(float(after) - mx) < 0.005
    ok_before = abs(float(before) - b13) < 0.005
    chk(ok_after and ok_before,
        f"{key:<12} 标题 {before}→{after} | 矩阵 V13={b13:.2f} V13.1={mx:.2f}")

print()
print("=" * 70)
print("③ 15.2 三阶段对照表：V13 列 / V13.1 列 / Δ 与两份矩阵一致")
print("=" * 70)
c13 = [sum(V13[e][i] for e in V13) / len(V13) for i in range(7)]
c131 = colavg_list
# 从文档 15.2 表抓行
sec = text.split("### 15.2")[1].split("### 15.3")[0]
rows = re.findall(
    r"^\|\s*\*{0,2}([^|*]+?)\*{0,2}\s*\|"      # 维度名（可被 ** 包裹）
    r"\s*\*{0,2}([\d.]+)\*{0,2}\s*\|"           # V13 列
    r"\s*\*{0,2}([\d.]+)\*{0,2}\s*\|"           # V13.1 列
    r"\s*\*{0,2}([+\-]?[\d.]+)\*{0,2}\s*\|",    # Δ 列
    sec, re.M)
chk(len(rows) >= 8, f"15.2 表应至少抓到 8 行（7维度+总均），实际 {len(rows)}")
for name, a, b, d in rows:
    nm = name.strip()
    if nm in DIMS:
        i = DIMS.index(nm)
        chk(abs(float(a) - c13[i]) < 0.005, f"{nm:<8} V13列 文档={a} 矩阵={c13[i]:.2f}")
        chk(abs(float(b) - c131[i]) < 0.005, f"{nm:<8} V13.1列 文档={b} 矩阵={c131[i]:.2f}")
        chk(abs(float(d) - (c131[i] - c13[i])) < 0.005,
            f"{nm:<8} Δ列 文档={d} 实算={c131[i]-c13[i]:+.2f}")
    elif "总均" in nm:
        g13 = sum(sum(v) for v in V13.values()) / 77
        chk(abs(float(a) - g13) < 0.005, f"总均 V13列 文档={a} 实算={g13:.2f}")
        chk(abs(float(b) - grand) < 0.005, f"总均 V13.1列 文档={b} 实算={grand:.2f}")
        chk(abs(float(d) - (grand - g13)) < 0.005,
            f"总均 Δ列 文档={d} 实算={grand-g13:+.2f}")

print()
print("=" * 70)
print("④ 全文关键数字交叉核对")
print("=" * 70)
def has(s):
    return s in text

chk(has("331.0") and has("4.2987"), "V13 核验数字 331.0 / 4.2987 在文中出现")
chk(has("351.5") and has("4.5649"), "V13.1 核验数字 351.5 / 4.5649 在文中出现")
chk(has("356.5") and has("4.6299"), "V13.1b 核验数字 356.5 / 4.6299 在文中出现")
for s in ["166.7", "216.7", "377", "6.3", "3.9h", "2.9h"]:
    chk(has(s), f"工期关键数字 '{s}' 在文中出现")
chk(has("8/11"), "文档矛盾条目数 8/11 在文中出现")
chk(has("N11") and has("N18"), "新发现编号 N11–N18 齐备")
for p in ["P0-6", "P0-7", "P0-8", "P0-9", "P0-10", "P0-11"]:
    chk(has(p), f"新增 P0 项 {p} 在文中出现")
for p in ["P1-9", "P1-15", "P1-21"]:
    chk(has(p), f"新增 P1 项 {p} 在文中出现")
for p in ["P2-7", "P2-13"]:
    chk(has(p), f"新增 P2 项 {p} 在文中出现")
for t in ["⑭", "⑮", "⑯"]:
    chk(has(t), f"新增契约测试 {t} 在文中出现")
for u in ["U1", "U7"]:
    chk(has(u), f"不确定项 {u} 在文中出现")

print()
print("=" * 70)
print("⑤ 敏感性与就绪度演进链路一致性")
print("=" * 70)
chk(has("4.22") and has("4.30") and has("4.56") and has("4.63") and has("4.47"),
    "就绪度演进 4.22 / 4.30 / 4.56 / 4.63 / 4.47 均在文中")
# 敏感性：错因否决 知识转化 4.41->4.20，总均应约 4.53
d = (4.41 - 4.20) * 11 / 77
chk(abs((grand - d) - 4.53) < 0.01,
    f"待拍板④否决后总均：实算 {grand-d:.2f}，文档写 4.53")
# 敏感性：全部不改动 = 4.30 基线
chk(abs(sum(sum(v) for v in V13.values()) / 77 - 4.30) < 0.005, "基线 4.30 复核通过")
# 提升幅度
chk(abs((grand - 4.2987) - 0.27) < 0.01,
    f"本轮提升 Δ：实算 {grand-4.2987:+.2f}，文档写 +0.27")

print()
print("=" * 70)
print(f"核验结论：{'全部通过 ✅' if not fails else f'{len(fails)} 项失败 ❌'}")
print("=" * 70)
if fails:
    for f in fails:
        print("  - " + f)
    sys.exit(1)
