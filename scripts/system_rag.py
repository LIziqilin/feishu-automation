#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""system_rag.py — V45 系统知识问答（轻量 RAG，零第三方依赖）
====================================================================
把最终版方案/用户手册/施工资料/DELIVERY_MANIFEST 等系统文档建立本地索引，
群指令「问系统：xxx」-> 检索最相关片段 + LLM 生成可溯源回答。

用法：
  python system_rag.py --rebuild        # 重建知识索引
  python system_rag.py "任务表字段有哪些？"
  python system_rag.py --reindex --query "如何触发三察"
"""
import os, sys, re, json, glob, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v15_features as v15

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
DOCS_DIR = os.path.join(PROJ, "docs")
INDEX_FILE = os.path.join(HERE, ".system_rag_index.json")
EXTRA = [
    os.path.join(PROJ, "DELIVERY_MANIFEST.md"),
]
CHUNK_MAX = 1200  # 字符


def _read(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return f.read()
    except Exception:
        return ""


def chunk_markdown(text, title):
    """按标题切块（h1/h2/h3），每块<=CHUNK_MAX"""
    blocks = re.split(r"(?m)^(#{1,3} .*)$", text)
    chunks = []
    cur_title = title
    cur = []
    def flush():
        nonlocal cur
        body = " ".join(x.strip() for x in cur).strip()
        if body:
            chunks.append({"title": cur_title, "text": body[:CHUNK_MAX], "src": title})
        cur = []
    for b in blocks:
        if re.match(r"^#{1,3} ", b):
            flush()
            cur_title = re.sub(r"^#+\s*", "", b).strip()
        else:
            cur.append(b)
    flush()
    return chunks


def build_index():
    chunks = []
    files = sorted(glob.glob(os.path.join(DOCS_DIR, "*.md"))) + [f for f in EXTRA if os.path.exists(f)]
    for f in files:
        text = _read(f)
        if not text:
            continue
        title = os.path.basename(f)
        chunks.extend(chunk_markdown(text, title))
    # 去重（同标题+同文本）
    seen = set()
    out = []
    for c in chunks:
        k = c["title"] + "|" + c["text"][:80]
        if k in seen:
            continue
        seen.add(k)
        out.append(c)
    with open(INDEX_FILE, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=1)
    return out


def _tok(s):
    # 简单分词：中文按字符 bigram + 英文按词
    s = s.lower()
    toks = set(re.findall(r"[a-z0-9_]+", s))
    cjk = re.findall(r"[\u4e00-\u9fff]", s)
    toks.update(cjk)
    for i in range(len(cjk) - 1):
        toks.add(cjk[i] + cjk[i + 1])
    return toks


def search(query, top_k=4):
    if not os.path.exists(INDEX_FILE):
        build_index()
    with open(INDEX_FILE, encoding="utf-8") as f:
        chunks = json.load(f)
    qt = _tok(query)
    scored = []
    for c in chunks:
        ct = _tok(c["text"] + " " + c["title"])
        inter = len(qt & ct)
        if inter == 0:
            continue
        # 加权：标题命中加分
        if qt & _tok(c["title"]):
            inter += 2
        scored.append((inter, c))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:top_k]]


def _ds_direct(query):
    """文档未命中时，fallback 直连 DeepSeek 直接回答通用知识。"""
    try:
        from deepseek_assistants import ds_chat
        return ds_chat(query, system="你是AI学习助手，用简洁中文回答，150字内。", max_tokens=300)
    except Exception as e:
        return f"（文档未命中，且AI直接回答失败：{e}）"


def answer(query):
    hits = search(query)
    if not hits:
        ans = _ds_direct(query)
        return f"💡 系统文档未直接覆盖此问题，AI直接回答：\n{ans}\n\n（如需系统内部操作，请换更具体的关键词）"
    ctx = "\n\n".join(f"[来源:{c['src']} / {c['title']}]\n{c['text'][:600]}" for c in hits)
    prompt = ("你是 AI 学习系统的运维知识助手。请依据下方系统文档片段回答用户问题；"
              "如果文档片段不足以回答，不要说'文档未覆盖'，而是用你自己的知识直接回答，"
              "并在末尾注明'（系统文档未覆盖，AI通用回答）'。回答要简洁（200字内），并列出引用来源文件名。\n\n"
              f"问题：{query}\n\n系统文档片段：\n{ctx}")
    try:
        ans = v15.llm_chat(prompt, system="你是严谨的系统运维知识助手，答案可溯源；文档没有的用通用知识补。", max_tokens=400)
    except Exception as e:
        ans = f"（LLM 生成失败：{e}，以下为直接检索结果）\n" + "\n".join(
            f"- [{c['src']}]({c['title']})：{c['text'][:150]}" for c in hits)
    srcs = "\n".join(f"📄 {c['src']}（{c['title']}）" for c in hits)
    return f"{ans}\n\n引用：\n{srcs}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="重建索引")
    ap.add_argument("--query", default="", help="查询问题")
    ap.add_argument("query_pos", nargs="?", default="", help="查询问题（位置参数）")
    args = ap.parse_args()

    if args.rebuild:
        n = len(build_index())
        print(f"知识索引已重建：{n} 个片段")
        return
    q = args.query or args.query_pos
    if not q:
        print("用法：python system_rag.py --rebuild | python system_rag.py \"问题\"")
        print("      python system_rag.py --reindex --query \"问题\"")
        return
    print(answer(q))


if __name__ == "__main__":
    main()
