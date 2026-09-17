#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""import_knowledge.py — V45 MarkItDown 文档导入
====================================================================
把外部文档（PDF/DOCX/MD/TXT/PPT/XLSX）用 MarkItDown 转为 Markdown，
清洗后沉淀为洞察（类型=知识沉淀，来源=MarkItDown导入），并可写入 Obsidian。

用法：
  python import_knowledge.py <文件路径> [--obsidian] [--dry-run]
"""
import os, sys, re, argparse
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v15_features as v15
from obsidian_sync import obs_api

MAX_LEN = 20000


def convert(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".md", ".txt"):
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            return f.read()
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
        res = md.convert(path)
        text = res.text_content or ""
    except Exception as e:
        return f"（MarkItDown 转换失败：{e}）"
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    text = re.sub(r"\s+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[Page\s*\d+\]", "", text)
    return text.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--obsidian", action="store_true", help="同时写入 Obsidian 技术笔记")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = args.path
    if not os.path.exists(path):
        print("❌ 文件不存在:", path)
        return 1
    name = os.path.basename(path)
    text = convert(path)
    print(f"📄 转换完成：{name} → {len(text)} 字符")

    if args.dry_run:
        print("（dry-run，不写入）\n" + text[:300])
        return 0

    # 写入洞察表（知识沉淀）
    rid = v15.create_record(v15.T_INSIGHT, {
        "洞察标题": f"文档导入：{name}",
        "洞察内容": text[:MAX_LEN],
        "洞察日期": int(datetime.now().timestamp() * 1000),
        "洞察类型": "知识沉淀",
        "来源": "MarkItDown导入",
        "标签": ["文档导入"],
        "类型": "洞察",
    })
    print("✅ 已沉淀到洞察表:", rid.get("data", {}).get("record", {}).get("record_id"))

    if args.obsidian:
        title = f"文档导入_{datetime.now().strftime('%Y%m%d')}_{os.path.splitext(name)[0][:40]}"
        note = f"---\ntags: [文档导入]\ndate: {datetime.now().strftime('%Y-%m-%d')}\n---\n\n# {name}\n\n{text[:MAX_LEN]}"
        ok, body = obs_api("PUT", f"/vault/03-技术笔记库/{title}.md", note)
        print("✅ Obsidian 技术笔记:", "写入成功" if ok else f"失败 {str(body)[:150]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
