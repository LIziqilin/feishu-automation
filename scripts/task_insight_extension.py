#!/usr/bin/env python
"""
task_insight_extension.py - S7/S8/S9功能扩展
S7: 随手记洞察（「洞察：xxx」指令）
S8: 快速销项（「完成 xxx」指令）
S9: 到期提醒（检查任务截止日期）

V33修复：handle_insight优先调用InsightArchiver.archive_insight进行结构化归档
（标签/关联科目/AI摘要/行动项等18字段），失败时降级到create_insight基本字段
"""
from v19_integration import BASE_TOKEN
import subprocess, json, sys, re, time, os
from datetime import datetime, timedelta


TASK_TABLE = "tblz3H4lV7PCrBrX"
INSIGHT_TABLE = "tblaqKBl87V9C0q1"
CHAT_ID = "oc_1fe154e172ab04622b7ffa810ac172bc"

# V33修复：尝试导入InsightArchiver（结构化洞察归档）
INSIGHT_ARCHIVER_AVAILABLE = False
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from v19_integration import InsightArchiver
    INSIGHT_ARCHIVER_AVAILABLE = True
    print("[V33修复] InsightArchiver导入成功，将使用结构化归档")
except Exception as e:
    print(f"[V33修复] InsightArchiver导入失败，将使用基本归档: {e}")
    INSIGHT_ARCHIVER_AVAILABLE = False

def run_cmd(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, shell=True)
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
# S7: 随手记洞察
# ============================================================

def parse_insight_command(text):
    """解析「洞察：xxx」或「洞察 xxx」指令"""
    match = re.match(r'^洞察[：:]\s*(.+)$', text)
    if match:
        return match.group(1).strip()
    match = re.match(r'^洞察\s+(.+)$', text)
    if match:
        return match.group(1).strip()
    return None

def create_insight(content):
    """在洞察笔记表创建新记录"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    # 生成标题（取前20字）
    title = content[:20] + "..." if len(content) > 20 else content

    # 构造字段
    fields = {
        "洞察标题": title,
        "内容": content,
        "洞察日期": now,
        "洞察类型": "随手记",
        "状态": "待整理",
        "来源": "群指令",
    }

    # 使用临时JSON文件方式，避免中文编码问题
    tmp_filename = f"tmp_insight_{int(time.time()*1000)}.json"
    tmp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), tmp_filename)
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(fields, f, ensure_ascii=False)

        cmd = ["lark-cli", "base", "+record-upsert", "--base-token", BASE_TOKEN,
               "--table-id", INSIGHT_TABLE, "--as", "user",
               "--json", f"@./{tmp_filename}"]
        ok, stdout, stderr = run_cmd(cmd, timeout=60)

        if ok:
            try:
                data = json.loads(stdout)
                # +record-upsert返回: data.record.record_id_list[0]
                record_id = data.get("data", {}).get("record", {}).get("record_id_list", ["未知"])[0]
                return True, record_id
            except:
                return True, "创建成功"
        return False, stderr[:100]
    except Exception as e:
        return False, f"写入异常: {e}"
    finally:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except:
                pass

def handle_insight(text):
    """处理洞察指令（V33修复：优先使用InsightArchiver结构化归档）"""
    content = parse_insight_command(text)
    if not content:
        return False, "洞察内容不能为空"

    # V33修复：优先使用InsightArchiver结构化归档（标签/关联科目/AI摘要/行动项等18字段）
    if INSIGHT_ARCHIVER_AVAILABLE:
        try:
            print(f"  [V33修复] 使用InsightArchiver结构化归档洞察...")
            archive_result = InsightArchiver.archive_insight(
                insight_text=content,
                related_card_id=None,
                insight_type="随手记"
            )
            
            if archive_result.get("success"):
                record_id = archive_result.get("record_id", "未知")
                structured = archive_result.get("structured", {})
                keywords = structured.get("keywords", [])
                subject = structured.get("subject", "")
                summary = structured.get("summary", "")[:50]
                action_count = len(structured.get("action_items", []))
                
                msg = (f"✅ 洞察已记录（结构化归档）\n"
                       f"📝 内容：{content[:50]}{'...' if len(content)>50 else ''}\n"
                       f"🏷️ 标签：{', '.join(keywords) if keywords else '无'}\n"
                       f"📚 关联科目：{subject}\n"
                       f"📋 AI摘要：{summary}...\n"
                       f"✅ 行动项：{action_count}个\n"
                       f"🆔 记录ID：{record_id}")
                send_message(msg)
                print(f"  [V33修复] 洞察结构化归档成功: record_id={record_id}, 标签={keywords}, 科目={subject}")
                return True, record_id
            else:
                error = archive_result.get("error", "未知错误")
                print(f"  [V33修复] InsightArchiver归档失败，降级到基本归档: {error}")
                # 降级到基本归档
        except Exception as e:
            print(f"  [V33修复] InsightArchiver调用异常，降级到基本归档: {e}")
            # 降级到基本归档

    # 降级方案：基本归档（只填6个基本字段）
    success, result = create_insight(content)
    if success:
        msg = f"✅ 洞察已记录（基本归档）\n📝 内容：{content[:50]}{'...' if len(content)>50 else ''}\n🆔 记录ID：{result}"
        send_message(msg)
        return True, result
    else:
        msg = f"❌ 洞察记录失败：{result}"
        send_message(msg)
        return False, result

# ============================================================
# S8: 快速销项
# ============================================================

def parse_complete_command(text):
    """解析「完成 xxx」或「完成：xxx」指令"""
    match = re.match(r'^完成[：:]\s*(.+)$', text)
    if match:
        return match.group(1).strip()
    match = re.match(r'^完成\s+(.+)$', text)
    if match:
        return match.group(1).strip()
    return None

def search_task(keyword):
    """在任务总表搜索匹配的任务"""
    cmd = ["lark-cli", "base", "+record-list", "--base-token", BASE_TOKEN,
           "--table-id", TASK_TABLE, "--as", "user", "--limit", "100"]
    ok, stdout, stderr = run_cmd(cmd)
    if not ok:
        return []

    # 解析markdown表格
    tasks = []
    for line in stdout.split("\n"):
        if line.startswith("| rec"):
            parts = line.split("|")
            if len(parts) >= 3:
                record_id = parts[1].strip()
                # 任务名称可能在不同列，尝试查找
                task_name = ""
                status = ""
                for p in parts:
                    p = p.strip()
                    if p and not p.startswith("rec") and len(p) > 1 and not p.startswith("20"):
                        if not task_name:
                            task_name = p
                        elif "完成" in p or "进行" in p or "待" in p:
                            status = p
                if keyword in task_name:
                    tasks.append({"record_id": record_id, "name": task_name, "status": status})
    return tasks

def complete_task(record_id):
    """将任务标记为已完成（使用临时JSON文件方式，避免中文编码问题）"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    fields = {
        "状态": "已完成",
        "实际完成日期": now,
        "_record_id": record_id,
    }
    tmp_filename = f"tmp_task_{int(time.time()*1000)}.json"
    tmp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), tmp_filename)
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(fields, f, ensure_ascii=False)

        cmd = ["lark-cli", "base", "+record-upsert", "--base-token", BASE_TOKEN,
               "--table-id", TASK_TABLE, "--as", "user",
               "--json", f"@./{tmp_filename}"]
        ok, stdout, stderr = run_cmd(cmd, timeout=60)
        if ok:
            return True, "任务已完成"
        return False, stderr[:100]
    except Exception as e:
        return False, f"写入异常: {e}"
    finally:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except:
                pass

def handle_complete(text):
    """处理完成任务指令"""
    keyword = parse_complete_command(text)
    if not keyword:
        return False, "任务名称不能为空"

    tasks = search_task(keyword)
    if not tasks:
        msg = f"❌ 未找到包含「{keyword}」的任务"
        send_message(msg)
        return False, "任务未找到"

    if len(tasks) == 1:
        task = tasks[0]
        success, result = complete_task(task["record_id"])
        if success:
            msg = f"✅ 任务已完成\n📋 {task['name']}\n🕐 完成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            send_message(msg)
            return True, task["record_id"]
        else:
            msg = f"❌ 任务更新失败：{result[:100]}"
            send_message(msg)
            return False, result
    else:
        # 多个匹配，列出供选择
        task_list = "\n".join([f"  {i+1}. {t['name']} (状态: {t['status']})" for i, t in enumerate(tasks[:5])])
        msg = f"⚠️ 找到{len(tasks)}个匹配任务，请明确指定：\n{task_list}\n\n请回复「完成 序号」或更精确的任务名称"
        send_message(msg)
        return False, "多个匹配"

# ============================================================
# S9: 到期提醒
# ============================================================

def check_due_tasks(days_ahead=3):
    """检查未来N天内到期的任务"""
    cmd = ["lark-cli", "base", "+record-list", "--base-token", BASE_TOKEN,
           "--table-id", TASK_TABLE, "--as", "user", "--limit", "100"]
    ok, stdout, stderr = run_cmd(cmd)
    if not ok:
        return []

    today = datetime.now().date()
    due_tasks = []

    for line in stdout.split("\n"):
        if line.startswith("| rec"):
            parts = line.split("|")
            if len(parts) >= 3:
                record_id = parts[1].strip()
                # 查找日期和任务名称
                task_name = ""
                due_date = None
                status = ""
                for p in parts:
                    p = p.strip()
                    # 尝试解析日期
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', p)
                    if date_match and not due_date:
                        try:
                            due_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").date()
                        except:
                            pass
                    if p and not p.startswith("rec") and len(p) > 1 and not date_match:
                        if not task_name:
                            task_name = p
                    if "完成" in p or "进行" in p or "待" in p:
                        status = p

                if due_date and task_name and status != "已完成":
                    days_until = (due_date - today).days
                    if 0 <= days_until <= days_ahead:
                        due_tasks.append({
                            "record_id": record_id,
                            "name": task_name,
                            "due_date": due_date.strftime("%Y-%m-%d"),
                            "days_until": days_until,
                            "status": status
                        })

    return sorted(due_tasks, key=lambda x: x["days_until"])

def send_due_reminder(days_ahead=3):
    """发送到期提醒"""
    due_tasks = check_due_tasks(days_ahead)
    if not due_tasks:
        return False, "无即将到期任务"

    task_list = "\n".join([
        f"  ⏰ {t['name']} - {t['due_date']}（{t['days_until']}天后）状态: {t['status']}"
        for t in due_tasks
    ])
    msg = f"📋 到期提醒（未来{days_ahead}天）\n\n{task_list}\n\n回复「完成 任务名称」可快速销项"
    send_message(msg)
    return True, f"{len(due_tasks)}个任务即将到期"

# ============================================================
# 指令检测
# ============================================================

def is_insight_command(text):
    """检测是否为洞察指令"""
    return bool(re.match(r'^洞察[：:\s]', text))

def is_complete_command(text):
    """检测是否为完成任务指令"""
    return bool(re.match(r'^完成[：:\s]', text))

def is_task_list_command(text):
    """检测是否为任务列表指令"""
    return text in ("任务", "任务列表", "待办", "todo")

def handle_extension_command(text):
    """
    处理扩展指令
    返回：(handled, result) - handled=True表示已处理
    """
    if is_insight_command(text):
        return True, handle_insight(text)

    if is_complete_command(text):
        return True, handle_complete(text)

    if is_task_list_command(text):
        due_tasks = check_due_tasks(7)
        if due_tasks:
            task_list = "\n".join([f"  {t['name']} - {t['due_date']}（{t['days_until']}天）" for t in due_tasks])
            send_message(f"📋 待办任务（未来7天）\n\n{task_list}")
        else:
            send_message("📋 暂无即将到期的任务")
        return True, "任务列表已发送"

    return False, None

if __name__ == "__main__":
    # 测试
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "due":
            success, result = send_due_reminder()
            print(f"到期提醒: {success} - {result}")
        elif cmd == "test_insight":
            handle_insight("洞察：测试洞察内容")
        elif cmd == "test_complete":
            handle_complete("完成 测试任务")
    else:
        print("用法: python task_insight_extension.py [due|test_insight|test_complete]")
