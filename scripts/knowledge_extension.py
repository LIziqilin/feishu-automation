#!/usr/bin/env python
"""
knowledge_extension.py - 知识链路扩展模块
S10: 知识检索（「知识：xxx」或「搜索：xxx」指令）
- 在知识索引表中搜索匹配的知识
- 调用LLM（DeepSeek三顺位降级）生成回答
- 在检索日志表中记录检索行为
- 群内返回检索结果+LLM回答
"""
from v19_integration import BASE_TOKEN
import subprocess, json, sys, re, time, os
from datetime import datetime

# 导入LLM三顺位降级模块
try:
    from llm_fallback import query_llm
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False


KNOWLEDGE_TABLE = "tbl0NiUFeQzH2r3n"
RETRIEVAL_LOG_TABLE = "tblCwZyAhZbmJra2"
CHAT_ID = "oc_1fe154e172ab04622b7ffa810ac172bc"

def run_cmd(cmd, timeout=60):
    try:
        # 不使用shell=True，避免多行文本在shell中被截断
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, shell=False)
        stdout = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        stderr = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return r.returncode == 0, stdout, stderr
    except Exception as e:
        return False, "", str(e)

def send_message(text):
    """发送消息到群"""
    cmd = ["lark-cli", "im", "+messages-send",
           "--chat-id", CHAT_ID, "--as", "user", "--text", text]
    return run_cmd(cmd)

# ============================================================
# 知识检索
# ============================================================

def parse_knowledge_command(text):
    """解析「知识：xxx」或「搜索：xxx」指令，或自然语言提问
    V38修复：支持自然语言提问关键词提取
    """
    if not text:
        return None

    # 原有格式：知识：xxx / 搜索：xxx / 查：xxx
    match = re.match(r'^(知识|搜索|查)[：:]\s*(.+)$', text)
    if match:
        return match.group(2).strip()
    match = re.match(r'^(知识|搜索|查)\s+(.+)$', text)
    if match:
        return match.group(2).strip()

    # V38新增：自然语言提问关键词提取
    # 先判断是否是知识检索指令，避免对非指令消息错误提取关键词
    if not is_knowledge_command(text):
        return None

    # 去除提问前缀
    keyword = text
    prefix_patterns = [
        r'^什么是\s*', r'^是什么\s*', r'^什么叫\s*', r'^何谓\s*',
        r'^如何\s*', r'^怎么\s*', r'^怎样\s*', r'^为啥\s*', r'^为什么\s*',
        r'^请问\s*', r'^请教\s*', r'^解释一下\s*', r'^说明一下\s*',
        r'^介绍一下\s*', r'^讲讲\s*', r'^说说\s*',
    ]
    for pattern in prefix_patterns:
        keyword = re.sub(pattern, '', keyword)

    # 去除结尾的问号和标点
    keyword = re.sub(r'[？?！!。，,\s]+$', '', keyword)
    # 去除开头的标点和空格
    keyword = re.sub(r'^[，,。.\s]+', '', keyword)

    if keyword and len(keyword) >= 2:
        return keyword.strip()

    return None

def search_knowledge(keyword, limit=5):
    """在知识索引表中搜索匹配的知识"""
    cmd = ["lark-cli", "base", "+record-list", "--base-token", BASE_TOKEN,
           "--table-id", KNOWLEDGE_TABLE, "--as", "user", "--limit", "100"]
    ok, stdout, stderr = run_cmd(cmd)
    if not ok:
        return []

    results = []
    for line in stdout.split("\n"):
        if line.startswith("| rec"):
            parts = line.split("|")
            if len(parts) >= 3:
                record_id = parts[1].strip()
                # 尝试提取标题和内容
                title = ""
                content = ""
                status = ""
                knowledge_type = ""
                for p in parts:
                    p = p.strip()
                    if p and not p.startswith("rec") and len(p) > 1:
                        if not title:
                            title = p
                        elif not content and len(p) > 5:
                            content = p
                    if "已" in p or "待" in p or "进行" in p:
                        status = p
                    if "知识" in p or "经验" in p or "SOP" in p or "文档" in p:
                        knowledge_type = p

                # 简单匹配：标题或内容包含关键词
                if keyword in title or keyword in content:
                    results.append({
                        "record_id": record_id,
                        "title": title[:50],
                        "content": content[:80],
                        "status": status,
                        "type": knowledge_type
                    })
                    if len(results) >= limit:
                        break

    return results

def log_retrieval(keyword, hit_count, hit_ids):
    """在检索日志表中记录检索行为"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fields = {
        "时间戳": now,
        "检索词": keyword,
        "命中知识ID": ",".join(hit_ids) if hit_ids else "无",
        "命中标题": ",".join([r["title"] for r in []])[:100] if hit_ids else "无",
        "来源": "群指令",
        "工作区": "V16学习系统",
    }

    # 使用临时JSON文件方式，避免中文编码问题
    tmp_filename = f"tmp_knowledge_{int(time.time()*1000)}.json"
    tmp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), tmp_filename)
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(fields, f, ensure_ascii=False)

        cmd = ["lark-cli", "base", "+record-upsert", "--base-token", BASE_TOKEN,
               "--table-id", RETRIEVAL_LOG_TABLE, "--as", "user",
               "--json", f"@./{tmp_filename}"]
        ok, stdout, stderr = run_cmd(cmd, timeout=60)
        if not ok:
            print(f"  [ERROR] 知识检索日志写入失败: {stderr[:200]}")
        return ok
    except Exception as e:
        print(f"  [ERROR] 知识检索日志写入异常: {e}")
        return False
    finally:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except:
                pass

def handle_knowledge(text):
    """处理知识检索指令（集成LLM三顺位降级）"""
    keyword = parse_knowledge_command(text)
    if not keyword:
        return False, "检索词不能为空"

    # 搜索知识
    results = search_knowledge(keyword)

    # 记录检索日志
    hit_ids = [r["record_id"] for r in results]
    log_retrieval(keyword, len(results), hit_ids)

    # 构建检索上下文
    context = ""
    if results:
        context = "\n".join([
            f"[{i+1}] {r['title']}: {r['content'][:100]}"
            for i, r in enumerate(results[:5])
        ])

    # 调用LLM生成回答（三顺位降级）
    llm_answer = ""
    llm_source = ""
    if LLM_AVAILABLE:
        try:
            llm_result = query_llm(keyword, context=context)
            if llm_result.get("success"):
                llm_answer = llm_result.get("answer", "")
                llm_source = llm_result.get("source", "")
        except Exception as e:
            print(f"[LLM] 调用失败: {e}")
            llm_answer = ""
            llm_source = "调用失败"

    # 构建回复
    if results:
        result_list = "\n".join([
            f"  [{i+1}] {r['title']} ({r['type'] or '未分类'})\n      {r['content'][:60]}..."
            for i, r in enumerate(results[:5])
        ])
        knowledge_section = f"📚 找到 {len(results)} 条相关知识：\n\n{result_list}"
    else:
        knowledge_section = "📚 未找到相关知识（知识索引表当前数据较少）"

    # 构建LLM回答部分
    if llm_answer and llm_source != "飞书表格知识索引检索":
        llm_section = f"\n\n🤖 AI回答（来源：{llm_source}）：\n\n{llm_answer[:500]}"
    elif llm_answer:
        llm_section = f"\n\n📖 检索结果：\n\n{llm_answer[:500]}"
    else:
        llm_section = "\n\n⚠️ AI回答生成失败，仅显示检索结果"

    msg = f"🔍 知识检索：「{keyword}」\n\n{knowledge_section}{llm_section}\n\n💡 回复「知识 序号」可查看详情"

    send_message(msg)
    return True, f"找到{len(results)}条结果，LLM来源：{llm_source}"

# ============================================================
# 指令检测
# ============================================================

def is_knowledge_command(text):
    """检测是否为知识检索指令
    V38修复：支持自然语言提问（什么是、是什么、如何、怎么、为什么等）
    """
    if not text or len(text) < 3:
        return False

    # 原有格式：知识：xxx / 搜索：xxx / 查：xxx / 学知识：xxx（V42修复：增加"学知识"前缀）
    if re.match(r'^(知识|搜索|查|学知识)[：:\s]', text):
        return True

    # V38新增：自然语言提问格式
    natural_language_patterns = [
        r'^什么是', r'^是什么', r'^什么叫', r'^何谓',
        r'^如何', r'^怎么', r'^怎样', r'^为啥', r'^为什么',
        r'^请问', r'^请教', r'^解释一下', r'^说明一下',
        r'^介绍一下', r'^讲讲', r'^说说',
    ]
    for pattern in natural_language_patterns:
        if re.match(pattern, text):
            return True

    # 以问号结尾且长度大于5的句子（可能是提问）
    if text.endswith('？') or text.endswith('?'):
        if len(text) >= 5:
            # 排除答题指令（会/不会/模糊）
            if not re.match(r'^(会|不会|模糊)[\s？?]*$', text):
                return True

    return False

def handle_extension_command(text):
    """
    处理知识链路扩展指令
    返回：(handled, result) - handled=True表示已处理
    """
    if is_knowledge_command(text):
        return True, handle_knowledge(text)

    return False, None

if __name__ == "__main__":
    # 测试
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "search":
            keyword = sys.argv[2] if len(sys.argv) > 2 else "测试"
            success, result = handle_knowledge(f"知识：{keyword}")
            print(f"检索结果: {success} - {result}")
        elif cmd == "test":
            print("is_knowledge_command('知识：测试'):", is_knowledge_command("知识：测试"))
            print("is_knowledge_command('搜索 飞书'):", is_knowledge_command("搜索 飞书"))
            print("parse_knowledge_command('知识：间隔重复'):", parse_knowledge_command("知识：间隔重复"))
    else:
        print("用法: python knowledge_extension.py [search <关键词>|test]")
