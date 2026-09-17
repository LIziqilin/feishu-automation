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
    """发送消息到群（2026-09-16 改为 bot 身份 + 新版 CLI，与 learning_system._send_message 对齐）"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from v19_integration import LARK_NODE_EXE, LARK_CLI_SCRIPT
        cmd = [LARK_NODE_EXE, LARK_CLI_SCRIPT, "im", "+messages-send",
               "--chat-id", CHAT_ID, "--as", "bot",
               "--msg-type", "text", "--content", json.dumps({"text": text}, ensure_ascii=False)]
    except Exception:
        cmd = ["lark-cli", "im", "+messages-send",
               "--chat-id", CHAT_ID, "--as", "user", "--text", text]
    return run_cmd(cmd)

# ============================================================
# S7: 随手记洞察
# ============================================================

def parse_insight_command(text):
    """解析「写洞察：xxx」「洞察 xxx」「记录洞察 xxx」等指令"""
    for prefix in ("写洞察", "记录洞察", "记洞察", "洞察"):
        m = re.match(r'^' + prefix + r'[：:]\s*(.+)$', text)
        if m:
            return m.group(1).strip()
        m = re.match(r'^' + prefix + r'\s+(.+)$', text)
        if m:
            return m.group(1).strip()
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
        send_message("💡 写洞察请带上内容，例如：洞察：今天学习了XX")
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
    """解析「完成 xxx」或「完成：xxx」指令（V15增强：增加别名）"""
    # 主指令：完成
    match = re.match(r'^完成[：:]\s*(.+)$', text)
    if match:
        return match.group(1).strip()
    match = re.match(r'^完成\s+(.+)$', text)
    if match:
        return match.group(1).strip()
    # V15增强：增加别名
    aliases = ['销项', '搞定', 'done', '已完成']
    for alias in aliases:
        match = re.match(r'^' + alias + r'[：:]\s*(.+)$', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.match(r'^' + alias + r'\s+(.+)$', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None

def search_task(keyword):
    """在任务总表搜索匹配的任务（优先 lark-cli --as user；失败回退 bot token 直连）"""
    cmd = ["lark-cli", "base", "+record-list", "--base-token", BASE_TOKEN,
           "--table-id", TASK_TABLE, "--as", "user", "--limit", "100"]
    ok, stdout, stderr = run_cmd(cmd)
    if ok and "| rec" in stdout:
        tasks = []
        for line in stdout.split("\n"):
            if line.startswith("| rec"):
                parts = line.split("|")
                if len(parts) >= 3:
                    record_id = parts[1].strip()
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
    # 回退：用 bot token 直连（v15_features.list_records 已验证可用）
    try:
        import v15_features as vf
        recs = vf.list_records(TASK_TABLE)
        tasks = []
        for r in recs:
            f = r.get("fields", {})
            name = f.get("任务名称") or ""
            st = f.get("状态") or ""
            if keyword in str(name):
                tasks.append({"record_id": r.get("record_id") or r.get("id"), "name": name, "status": st})
        return tasks
    except Exception as _e:
        print(f"  [search_task 回退失败] {_e}")
        return []

def complete_task(record_id):
    """将任务标记为已完成（使用--record-id参数更新）"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    fields = {
        "状态": "已完成",
        "实际完成日期": now,
    }
    tmp_filename = "tmp_task_" + str(int(time.time()*1000)) + ".json"
    tmp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), tmp_filename)
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(fields, f, ensure_ascii=False)

        cmd = ["lark-cli", "base", "+record-upsert", "--base-token", BASE_TOKEN,
               "--table-id", TASK_TABLE, "--as", "user",
               "--record-id", record_id,
               "--json", "@./" + tmp_filename]
        ok, stdout, stderr = run_cmd(cmd, timeout=60)
        if ok:
            return True, "任务已完成"
        # 回退：bot token 直连 upsert（v15_features.update_record 已验证可用）
        try:
            import v15_features as vf
            vf.update_record(TASK_TABLE, record_id, fields)
            return True, "任务已完成"
        except Exception as _e:
            return False, (stderr or "")[:120] + " | fallback:" + str(_e)[:80]
    except Exception as e:
        return False, "写入异常: " + str(e)
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
            # V15增强：完成率统计和归档建议
            msg = f"✅ 任务已完成\n📋 {task['name']}\n🕐 完成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n💡 小提示：\n- 完成3天后可自动归档\n- 回复「归档 {task['name'][:20]}」手动归档"
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
# S8.2: 待办归档（V14增强）
# ============================================================

def parse_archive_command(text):
    """解析「归档 xxx」或「归档：xxx」指令（V15增强：增加别名）"""
    # 主指令：归档
    match = re.match(r'^归档[：:]\s*(.+)$', text)
    if match:
        return match.group(1).strip()
    match = re.match(r'^归档\s+(.+)$', text)
    if match:
        return match.group(1).strip()
    # V15增强：增加别名
    aliases = ['archive', '收起来', '存档']
    for alias in aliases:
        match = re.match(r'^' + alias + r'[：:]\s*(.+)$', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.match(r'^' + alias + r'\s+(.+)$', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def archive_task(record_id, task_name):
    """将已完成任务标记为已归档（使用--record-id参数更新）"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    fields = {
        "状态": "已归档",
        "复盘备注": "[归档于" + now + "] " + (task_name or ""),
    }
    tmp_filename = "tmp_archivetask_" + str(int(time.time()*1000)) + ".json"
    tmp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), tmp_filename)
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(fields, f, ensure_ascii=False)

        cmd = ["lark-cli", "base", "+record-upsert", "--base-token", BASE_TOKEN,
               "--table-id", TASK_TABLE, "--as", "user",
               "--record-id", record_id,
               "--json", "@./" + tmp_filename]
        ok, stdout, stderr = run_cmd(cmd, timeout=60)
        if ok:
            return True, "任务已归档"
        return False, stderr[:150]
    except Exception as e:
        return False, "写入异常: " + str(e)
    finally:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except:
                pass


def handle_archive(text):
    """处理归档指令（V14增强：仅已完成任务可归档）"""
    keyword = parse_archive_command(text)
    if not keyword:
        return False, "归档任务名称不能为空"

    tasks = search_task(keyword)
    if not tasks:
        msg = "❌ 未找到包含「" + keyword + "」的任务"
        send_message(msg)
        return False, "任务未找到"

    if len(tasks) > 1:
        task_list = "\n".join(["  " + str(i+1) + ". " + t["name"] + " (状态: " + t["status"] + ")" for i, t in enumerate(tasks[:5])])
        msg = "⚠️ 找到" + str(len(tasks)) + "个匹配任务，请明确指定：\n" + task_list + "\n\n请回复「归档 精确任务名」"
        send_message(msg)
        return False, "多个匹配"

    task = tasks[0]
    # 反证：未完成的任务不能归档（V42修复：状态可能是 list、JSON数组字符串或纯字符串）
    _st = task["status"]
    if isinstance(_st, list):
        _st = _st[0] if _st else ""
    elif isinstance(_st, str):
        _st = _st.strip()
        if _st.startswith("["):
            try:
                _arr = json.loads(_st)
                _st = _arr[0] if _arr else ""
            except Exception:
                pass
    if str(_st).strip() not in ("已完成", "完成"):
        msg = ("❌ 无法归档\n"
               "📋 任务：" + task["name"] + "\n"
               "📊 当前状态：" + task["status"] + "\n"
               "⚠️ 仅「已完成」的任务可以归档\n"
               "💡 请先回复「完成 " + task["name"] + "」完成任务后再归档")
        send_message(msg)
        return False, "任务未完成，不能归档"

    success, result = archive_task(task["record_id"], task["name"])
    if success:
        msg = ("📦 任务已归档\n"
               "📋 " + task["name"] + "\n"
               "🕐 归档时间：" + datetime.now().strftime("%Y-%m-%d %H:%M") + "\n"
               "📝 该任务将从日常待办列表中隐藏，历史记录保留")
        send_message(msg)
        return True, task["record_id"]
    else:
        msg = "❌ 任务归档失败：" + result[:100]
        send_message(msg)
        return False, result


def is_archive_command(text):
    """检测是否为归档指令（V42修复：支持 归档：xxx / 归档 xxx / 归档：归档 xxx 冗余前缀）"""
    return bool(re.match(r'^归档[：:\s]', text))


# ============================================================
# S8.5: 创建待办任务（V39增强）
# ============================================================

def parse_create_task_command(text):
    """解析「待办：xxx」或「待办 xxx」指令
    支持格式：
      待办：完成季度报告 / 新建任务：xxx / 创建任务：xxx
      待办 完成季度报告 截止9-20
      待办：【P0】完成报告 截止2026-09-20 类别工作
    （V42修复：兼容 新建任务/创建任务/记录任务/新增任务 前缀）
    """
    match = re.match(r'^(待办|新建任务|创建任务|记录任务|新增任务)[：:\s]+(.+)$', text)
    if not match:
        return None
    raw = match.group(2).strip()

    # 解析优先级【P0/P1/P2】
    priority = None
    pri_match = re.search(r'【(P[0-2])】', raw)
    if pri_match:
        priority_map = {"P0": "高", "P1": "中", "P2": "低"}
        priority = priority_map.get(pri_match.group(1), "中")
        raw = raw.replace(pri_match.group(0), "").strip()

    # 解析截止日期 截止MM-DD 或 截止YYYY-MM-DD
    due_date = None
    due_match = re.search(r'截止[：:\s]*([0-9]{4}-[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2})', raw)
    if due_match:
        date_str = due_match.group(1)
        if len(date_str) <= 5:  # MM-DD格式，补全年份
            year = datetime.now().year
            date_str = f"{year}-{date_str}"
        try:
            due_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d 18:00")
        except:
            pass
        raw = raw[:due_match.start()] + raw[due_match.end():]
        raw = raw.strip()

    # 解析类别 类别xxx
    category = None
    cat_match = re.search(r'类别[：:\s]*(\S+)', raw)
    if cat_match:
        category = cat_match.group(1)
        raw = raw[:cat_match.start()] + raw[cat_match.end():]
        raw = raw.strip()

    task_name = raw.strip()
    if not task_name:
        return None

    return {
        "name": task_name,
        "priority": priority or "中",
        "due_date": due_date,
        "category": category or "工作",
    }


def create_task_in_table(task_info):
    """在任务总表创建新任务"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    fields = {
        "任务名称": task_info["name"],
        "状态": "待办",
        "优先级": task_info["priority"],
        "类别": task_info["category"],
        "创建日期": now,
    }
    if task_info.get("due_date"):
        fields["截止日期"] = task_info["due_date"]

    tmp_filename = f"tmp_createtask_{int(time.time()*1000)}.json"
    tmp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), tmp_filename)
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(fields, f, ensure_ascii=False)

        cmd = ["lark-cli", "base", "+record-upsert", "--base-token", BASE_TOKEN,
               "--table-id", TASK_TABLE, "--as", "user",
               "--json", f"@./{tmp_filename}"]
        ok, stdout, stderr = run_cmd(cmd, timeout=60)
        if ok:
            try:
                data = json.loads(stdout)
                record_id = data.get("data", {}).get("record", {}).get("record_id_list", ["未知"])[0]
                return True, record_id
            except:
                return True, "创建成功"
        return False, stderr[:150]
    except Exception as e:
        return False, f"写入异常: {e}"
    finally:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except:
                pass


def handle_create_task(text):
    """处理创建待办指令"""
    task_info = parse_create_task_command(text)
    if not task_info:
        msg = "❌ 待办内容不能为空\n格式：待办：任务名称 [截止MM-DD] [类别xxx]"
        send_message(msg)
        return False, "格式错误"

    success, result = create_task_in_table(task_info)
    if success:
        msg = (f"✅ 待办已创建\n"
               f"📋 {task_info['name']}\n"
               f"🏷️ 优先级: {task_info['priority']} | 类别: {task_info['category']}\n")
        if task_info.get("due_date"):
            msg += f"📅 截止: {task_info['due_date']}\n"
        msg += f"🆔 记录ID: {result}\n\n"
        msg += "回复「完成 任务名」可快速销项"
        send_message(msg)
        return True, result
    else:
        msg = f"❌ 待办创建失败：{result[:100]}"
        send_message(msg)
        return False, result


def is_create_task_command(text):
    """检测是否为创建待办指令（V42修复：兼容 新建任务/创建任务/记录任务/新增任务 前缀）"""
    return bool(re.match(r'^(待办|新建任务|创建任务|记录任务|新增任务)[：:\s]', text))


# ============================================================
# S8.6: 任务查询函数（供报告合并使用，V39增强）
# ============================================================

def get_tasks_summary(days_ahead=7):
    """查询任务汇总：今日待办 + 今日已完成 + 未来N天待办
    返回 dict: {today_pending, today_completed, upcoming}
    """
    cmd = ["lark-cli", "base", "+record-list", "--base-token", BASE_TOKEN,
           "--table-id", TASK_TABLE, "--as", "user", "--limit", "200", "--format", "json"]
    ok, stdout, stderr = run_cmd(cmd, timeout=60)
    if not ok:
        return {"today_pending": [], "today_completed": [], "upcoming": [], "all_active": []}

    try:
        data = json.loads(stdout)
        fields = data.get("data", {}).get("fields", [])
        rows = data.get("data", {}).get("data", [])
    except:
        return {"today_pending": [], "today_completed": [], "upcoming": [], "all_active": []}

    # 建立字段索引
    field_idx = {}
    for i, f in enumerate(fields):
        field_idx[f] = i

    today = datetime.now().date()
    today_pending = []
    today_completed = []
    upcoming = []

    for row in rows:
        name = row[field_idx.get("任务名称", 0)] if "任务名称" in field_idx else str(row[0])
        # select字段返回数组格式如['已完成']，需取第一个元素
        status_raw = row[field_idx["状态"]] if "状态" in field_idx else ""
        if isinstance(status_raw, list) and len(status_raw) > 0:
            status = str(status_raw[0])
        else:
            status = str(status_raw) if status_raw and status_raw != "None" else ""
        due_date_str = str(row[field_idx["截止日期"]]) if "截止日期" in field_idx else ""
        actual_complete_str = str(row[field_idx["实际完成日期"]]) if "实际完成日期" in field_idx else ""
        priority_raw = row[field_idx["优先级"]] if "优先级" in field_idx else ""
        if isinstance(priority_raw, list) and len(priority_raw) > 0:
            priority = str(priority_raw[0])
        else:
            priority = str(priority_raw) if priority_raw and priority_raw != "None" else "低"

        if not name or name == "None":
            continue

        # 解析截止日期
        due_date = None
        if due_date_str and due_date_str != "None":
            try:
                if "T" in due_date_str:
                    due_date = datetime.fromisoformat(due_date_str.replace("Z", "+00:00").replace("+08:00", "")).date()
                else:
                    due_date = datetime.strptime(due_date_str[:10], "%Y-%m-%d").date()
            except:
                pass

        # 解析实际完成日期
        actual_complete_date = None
        if actual_complete_str and actual_complete_str != "None":
            try:
                if "T" in actual_complete_str:
                    actual_complete_date = datetime.fromisoformat(actual_complete_str.replace("Z", "+00:00").replace("+08:00", "")).date()
                else:
                    actual_complete_date = datetime.strptime(actual_complete_str[:10], "%Y-%m-%d").date()
            except:
                pass

        task = {"name": name[:40], "status": status, "due_date": due_date, "priority": priority}

        # 已完成状态集合（兼容"已完成"和"完成"两个重复选项）
        COMPLETED_STATUSES = ("已完成", "完成")
        # 非活跃状态（已完成/已归档/已取消，不进待办列表）
        INACTIVE_STATUSES = ("已完成", "完成", "已归档", "已取消")

        # 今日已完成
        if status in COMPLETED_STATUSES and actual_complete_date == today:
            today_completed.append(task)
        # 今日待办（截止今天且未完成/未归档/未取消）
        elif status not in INACTIVE_STATUSES and due_date == today:
            today_pending.append(task)
        # 未来N天待办
        elif status not in INACTIVE_STATUSES and due_date and today < due_date <= (today + timedelta(days=days_ahead)):
            upcoming.append(task)

    # 按截止日期排序
    upcoming.sort(key=lambda x: x["due_date"] or today + timedelta(days=999))

    # V41增强：全部活跃任务（待办+进行中，未完成/未归档/未取消），供早报矩阵面板使用
    all_active = []
    for row in rows:
        _name = row[field_idx.get("任务名称", 0)] if "任务名称" in field_idx else str(row[0])
        if isinstance(_name, list):
            _name = _name[0].get("text", "") if _name else ""
        _status_raw = row[field_idx["状态"]] if "状态" in field_idx else ""
        if isinstance(_status_raw, list) and len(_status_raw) > 0:
            _status = str(_status_raw[0])
        else:
            _status = str(_status_raw) if _status_raw and _status_raw != "None" else ""
        if not _name or _name == "None":
            continue
        if _status in INACTIVE_STATUSES:
            continue
        _pri_raw = row[field_idx["优先级"]] if "优先级" in field_idx else ""
        if isinstance(_pri_raw, list) and len(_pri_raw) > 0:
            _pri = str(_pri_raw[0])
        else:
            _pri = str(_pri_raw) if _pri_raw and _pri_raw != "None" else "低"
        all_active.append({"name": str(_name)[:40], "status": _status, "priority": _pri})

    return {
        "today_pending": today_pending,
        "today_completed": today_completed,
        "upcoming": upcoming,
        "all_active": all_active,
    }


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

                if due_date and task_name and status not in ("已完成", "完成", "已归档", "已取消"):
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
    """检测是否为洞察指令（支持 洞察/写洞察/记录洞察/记洞察，允许裸词或带内容）"""
    return bool(re.match(r'^(洞察|写洞察|记录洞察|记洞察)([：:\s].*)?$', text))

def is_complete_command(text):
    """检测是否为完成任务指令（V42修复：支持"搞定了/已完成"等带"了"后缀，含别名：完成/销项/搞定/done/已完成）"""
    return bool(re.match(r'^(完成|销项|搞定|done|已完成)了?[：:\s]', text, re.IGNORECASE))

def is_task_list_command(text):
    """检测是否为任务列表指令"""
    return text in ("任务", "任务列表", "待办", "todo")


def is_create_task_command(text):
    """检测是否为创建待办指令（V42修复：兼容 待办/新建任务/创建任务/记录任务/新增任务 前缀）"""
    return bool(re.match(r'^(待办|新建任务|创建任务|记录任务|新增任务)[：:\s]', text))

def handle_extension_command(text):
    """
    处理扩展指令
    返回：(handled, result) - handled=True表示已处理
    """
    if is_insight_command(text):
        return True, handle_insight(text)

    if is_create_task_command(text):
        return True, handle_create_task(text)

    if is_archive_command(text):
        return True, handle_archive(text)

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
