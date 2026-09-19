#!/usr/bin/env python
"""
learning_system.py - 间隔重复学习系统主运行模块
V16交付保障版

包含：
- T8: 群指令解析器（顺序消费制+异常路径回执）
- T9: 两段式回执（即时确认+延迟答案/下次日期）
- T10: 选题算法（到期优先+NOT_STARTED补足+intro_offset）

用法：
  python learning_system.py --poll              # 轮询群消息，处理新指令
  python learning_system.py --select            # 执行今日选题，推送早报
  python learning_system.py --status            # 查看系统状态
  python learning_system.py --reindex           # 重建消费索引
"""
from v19_integration import BASE_TOKEN
import subprocess, json, sys, time, argparse, re, os
from datetime import datetime, timedelta

# 导入扩展模块（S7随手记/S8快速销项/S9到期提醒）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from task_insight_extension import handle_extension_command, is_insight_command, is_complete_command, is_task_list_command, send_due_reminder
    EXTENSION_AVAILABLE = True
except ImportError:
    EXTENSION_AVAILABLE = False

# 导入知识链路扩展模块（S10知识检索）
try:
    from knowledge_extension import handle_extension_command as handle_knowledge_command, is_knowledge_command
    KNOWLEDGE_EXTENSION_AVAILABLE = True
except ImportError:
    KNOWLEDGE_EXTENSION_AVAILABLE = False

# V15 Phase3/4 新功能群指令路由（错题本/费曼/番茄/时间块/个性化推荐/知识演进）
try:
    from v15_command_router import handle_v15_command
    V15_ROUTER_AVAILABLE = True
except ImportError as _e:
    print(f"[V15] 指令路由导入失败: {_e}")
    V15_ROUTER_AVAILABLE = False

# V21集成：导入v19_integration模块（告警/倦怠/DLQ/撤回复验）
try:
    from v19_integration import AlertManager, FatigueManager, DLQManager, RevokeVerifier, ConsumeIndexHealthChecker, RevokeSimplifier, ErrorTypeParser, ErrorTypeHandler, EfficiencyOptimizer, Watchdog, HashManager, CircuitBreaker, EditMessageHandler, AdminOverrideManager, CredentialDriftDetector
    V19_INTEGRATION_AVAILABLE = True
except ImportError as e:
    print(f"[V21集成] v19_integration导入失败: {e}")
    V19_INTEGRATION_AVAILABLE = False


CARD_TABLE = "tblpLvxyYpDJgF92"
FLOW_TABLE = "tblbznzCSpPhSz93"
LOG_TABLE = "tblPreh1ipB9LQpf"
TASK_TABLE = "tblz3H4lV7PCrBrX"
CHAT_ID = "oc_1fe154e172ab04622b7ffa810ac172bc"
LARK_NODE_EXE = r"C:\Users\Administrator\AppData\Local\hermes\node\node.exe"
LARK_CLI_SCRIPT = r"C:\Users\Administrator\AppData\Local\hermes\node\node_modules\@larksuite\cli\scripts\run.js"


# 消费索引文件
CONSUME_INDEX_FILE = "D:/AI-Tools/feishu/V13方案增强/scripts/.consume_index.json"

# V38修复：已处理消息ID记录文件（避免重复处理导致消费索引耗尽）
PROCESSED_MESSAGES_FILE = "D:/AI-Tools/feishu/V13方案增强/scripts/.processed_messages.json"
PROCESSED_MESSAGES_RETENTION_DAYS = 7  # 保留最近7天的已处理消息记录

def run_cmd(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, shell=True)
        stdout = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        stderr = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return r.returncode == 0, stdout, stderr
    except subprocess.TimeoutExpired:
        print(f"  [警告] 命令超时({timeout}s): {' '.join(cmd[:3]) if isinstance(cmd, list) else str(cmd)[:50]}")
        return False, "", "命令超时"
    except Exception as e:
        return False, "", str(e)

def load_processed_messages():
    """V38修复：加载已处理消息ID记录（避免重复处理导致消费索引耗尽）"""
    try:
        if os.path.exists(PROCESSED_MESSAGES_FILE):
            with open(PROCESSED_MESSAGES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 清理过期记录（保留最近7天）
                cutoff = (datetime.now() - timedelta(days=PROCESSED_MESSAGES_RETENTION_DAYS)).isoformat()
                cleaned = {k: v for k, v in data.items() if v.get('processed_at', '') > cutoff}
                if len(cleaned) < len(data):
                    save_processed_messages(cleaned)
                return cleaned
    except:
        pass
    return {}

def save_processed_messages(processed_dict):
    """V38修复：保存已处理消息ID记录"""
    try:
        with open(PROCESSED_MESSAGES_FILE, 'w', encoding='utf-8') as f:
            json.dump(processed_dict, f, ensure_ascii=False, indent=2)
    except:
        pass

def is_message_processed(message_id, processed_dict):
    """V38修复：检查消息是否已处理"""
    if not message_id:
        return False
    return message_id in processed_dict

def mark_message_processed(message_id, processed_dict, action=""):
    """V38修复：标记消息为已处理"""
    if not message_id:
        return
    processed_dict[message_id] = {
        "processed_at": datetime.now().isoformat(),
        "action": action
    }
    # 定期保存（每10条保存一次，避免频繁IO）
    if len(processed_dict) % 10 == 0:
        save_processed_messages(processed_dict)

def update_system_status(status="running", health_issues=0, extra=None):
    """更新系统状态文件（V18优化：每次执行后更新last_success_time）"""
    try:
        state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".system_state.json")
        state = {}
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
            except:
                pass
        now = datetime.now().isoformat()
        state["last_success_time"] = now
        state["last_check"] = now
        state["status"] = status
        state["health_issues"] = health_issues
        if extra:
            state.update(extra)
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"  [警告] 系统状态更新失败: {e}")
        return False

def parse_markdown_table(stdout):
    lines = stdout.split("\n")
    records = []
    header = None
    for line in lines:
        if line.startswith("| _record_id"):
            header = [h.strip() for h in line.split("|")]
            continue
        if line.startswith("| rec") and header:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= len(header):
                record = {}
                for i, h in enumerate(header):
                    if i < len(parts):
                        record[h] = parts[i]
                records.append(record)
    return records

def parse_select_value(val):
    if not val:
        return ""
    val = str(val).strip()
    if val.startswith("[") and val.endswith("]"):
        val = val.strip("[]\"' ")
    return val

def parse_datetime(ts_str):
    if not ts_str:
        return None
    ts_str = str(ts_str).strip()
    for fmt in ["%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
        try:
            dt = datetime.strptime(ts_str, fmt)
            if dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            return dt
        except:
            continue
    return None

# ============================================================
# T8: 群指令解析器
# ============================================================

class InstructionParser:
    """顺序消费制指令解析器"""

    VALID_RESULTS = {"会", "不会", "模糊"}

    def __init__(self):
        self.current_index = self._load_index()

    def _load_index(self):
        """加载当前消费索引"""
        try:
            with open(CONSUME_INDEX_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("current_index", 0)
        except:
            return 0

    def _save_index(self):
        """保存当前消费索引"""
        try:
            with open(CONSUME_INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump({"current_index": self.current_index,
                           "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False)
        except:
            pass

    def parse(self, message_text, today_cards):
        """
        解析用户消息
        返回：(action, data) 或 (None, None) 如果是非指令消息
        action: "answer" / "requery" / "pause" / "resume" / "ignore"
        """
        if not message_text:
            return "ignore", None

        text = message_text.strip()

        # 闲聊检测（非指令消息）
        if not self._looks_like_instruction(text):
            return "ignore", None

        # 重新获取今日卡片（V42修复：支持"开始闪卡复习/闪卡复习/闪卡"）
        if text in ("今日卡片", "卡片", "今日复习", "复习", "开始闪卡复习", "闪卡复习", "闪卡"):
            return "requery", None

        # V42修复：系统体检指令
        if text.startswith("系统体检") or text.startswith("体检"):
            return "health_check", {"raw": text}

        # 暂停
        pause_match = re.match(r'^暂停\s*(\d+)?\s*(天|日)?$', text)
        if pause_match:
            days = int(pause_match.group(1)) if pause_match.group(1) else 2
            return "pause", {"days": days}

        # 查看待办任务（2026-09-16 新增：@机器人"显示所有待办任务"等）
        # 不依赖@前缀剥离：直接全文匹配"动词+待办/任务"意图
        # 显示已完成任务（2026-09-16 新增，优先于 list_todo）
        if re.search(r'(查看|显示|列出).{0,12}(已完成|完成)', text) or re.search(r'已完成.{0,10}(任务|待办)', text):
            return "list_done", None
        # 显示待办任务（排除"已完成"干扰）
        if re.search(r'(查看|显示|列出|读取|列举|有哪些|有什么|全部|所有).{0,12}(待办|任务)|(待办|任务).{0,10}(有哪些|有什么|列表|清单)', text):
            return "list_todo", None

        # 新建任务指令（支持多种说法）
        for prefix in ["新建任务：", "新建任务:", "创建任务：", "创建任务:", "记录任务：", "记录任务:", "新增任务：", "新增任务:"]:
            if text.startswith(prefix):
                task_name = text[len(prefix):].strip()
                if task_name:
                    return "create_task", {"task_name": task_name}

        # 恢复
        if text in ("恢复", "继续", "resume"):
            return "resume", None

        # D6: 手动撤回命令（!revoke 或 !撤销）
        if text.startswith("!revoke") or text.startswith("!撤销"):
            parts = text.split()
            target_event_id = parts[1] if len(parts) > 1 else None
            return "revoke", {"target_event_id": target_event_id}

        # 答题指令（有编号：会2 / 不会3 / 模糊1）
        numbered_match = re.match(r'^(会|不会|模糊)\s*(\d+)$', text)
        if numbered_match:
            result = numbered_match.group(1)
            card_num = int(numbered_match.group(2)) - 1  # 转为0-based
            if 0 <= card_num < len(today_cards):
                return "answer", {"result": result, "card_index": card_num, "explicit": True}
            else:
                return "error", {"reason": f"编号超出范围（今日共{len(today_cards)}张）"}

        # 答题指令（无编号：会 / 不会 / 模糊，顺序消费）
        if text in self.VALID_RESULTS:
            if self.current_index < len(today_cards):
                card_index = self.current_index
                self.current_index += 1
                self._save_index()
                return "answer", {"result": text, "card_index": card_index, "explicit": False}
            else:
                return "error", {"reason": "今日卡片已全部答完"}

        # V21集成：带错因的答题指令（不会 记不清 / 不会 理解错 / 不会 题目歧义 / 不会 已过期）
        if V19_INTEGRATION_AVAILABLE:
            try:
                et_result = ErrorTypeParser.parse_with_error_type(text)
                if et_result and len(et_result) >= 3 and et_result[2]:
                    result = et_result[0]
                    error_type = et_result[1]
                    if result in self.VALID_RESULTS and self.current_index < len(today_cards):
                        card_index = self.current_index
                        self.current_index += 1
                        self._save_index()
                        print(f"  [V21错因] 解析到带错因答题: result={result}, error_type={error_type}")
                        return "answer", {"result": result, "card_index": card_index, "explicit": False, "error_type": error_type}
                    elif result in self.VALID_RESULTS:
                        return "error", {"reason": "今日卡片已全部答完"}
            except Exception as et_e:
                print(f"  [V21错因] 解析异常: {et_e}")

        # 批量指令（会1会2会3）
        batch_matches = re.findall(r'(会|不会|模糊)\s*(\d+)', text)
        if batch_matches and len(batch_matches) > 1:
            answers = []
            for result, num in batch_matches:
                idx = int(num) - 1
                if 0 <= idx < len(today_cards):
                    answers.append({"result": result, "card_index": idx})
            if answers:
                return "batch_answer", {"answers": answers}

        # 解析失败
        return "parse_error", {"raw": text}

    def _looks_like_instruction(self, text):
        """判断是否像指令消息"""
        # 有效答题指令
        if text in self.VALID_RESULTS:
            return True
        # 有编号的答题指令
        if re.match(r'^(会|不会|模糊)\s*\d+$', text):
            return True
        # 批量指令
        if re.findall(r'(会|不会|模糊)\s*\d+', text):
            return True
        # 以会/不会/模糊开头的格式错误指令（如"会 一"）
        if re.match(r'^(会|不会|模糊)\s+\S+', text):
            return True
        # D6: 手动撤回命令（!revoke 或 !撤销）
        if text.startswith("!revoke") or text.startswith("!撤销"):
            return True
        # 系统指令
        if text in ("今日卡片", "卡片", "今日复习", "复习", "恢复", "继续", "resume"):
            return True
        if re.match(r'^暂停\s*\d*\s*(天|日)?$', text):
            return True
        # 查看待办任务（2026-09-16 新增）
        if re.search(r'(查看|显示|列出|读取|列举|有哪些|有什么|全部|所有).{0,12}(?!已完成)(待办|任务)|(?!已完成)(待办|任务).{0,10}(有哪些|有什么|列表|清单)', text):
            return True
        # 显示已完成任务
        if re.search(r'(查看|显示|列出).{0,12}(已完成|完成)', text) or re.search(r'已完成.{0,10}(任务|待办)', text):
            return True
        # V42修复：新建任务/创建任务/记录任务/新增任务 前缀
        for _p in ["新建任务：", "新建任务:", "创建任务：", "创建任务:", "记录任务：", "记录任务:", "新增任务：", "新增任务:"]:
            if text.startswith(_p):
                return True
        # V42修复：闪卡复习 / 系统体检 / 学知识
        if any(_k in text for _k in ("闪卡", "体检", "学知识")):
            return True
        return False

    def reset_index(self):
        """重置消费索引（每日早报推送后调用）"""
        self.current_index = 0
        self._save_index()

# ============================================================
# T9: 两段式回执
# ============================================================

class ReceiptSender:
    """两段式回执发送器"""

    def send_immediate(self, result, card_title=None, explicit=False):
        """第一段：即时确认（V15优化：不发送到群里，只打印）"""
        # V15优化：不发送即时回执，避免大量消息打扰
        # 只在控制台打印，减少群消息量
        print(f"  [答题记录] {result} - {card_title[:20] if card_title else ''}...")
        return "已记录"
    def send_delayed(self, answer, next_date, interval):
        """第二段：延迟答案+下次日期（+300ms）"""
        time.sleep(0.3)  # 模拟derive计算延迟
        msg = f"💡 答案：{answer[:100]}\n📅 下次复习：{next_date}（{interval}天后）"
        self._send_message(msg)
        return msg

    def send_error(self, reason):
        """解析失败回执"""
        msg = f"❓ 没看懂。{reason}\n请发：会/不会/模糊（或「会 2」指定编号）"
        self._send_message(msg)
        return msg

    def send_batch_result(self, results):
        """批量回执（V15优化：不发送到群里，只打印，避免大量消息打扰）"""
        lines = []
        for r in results:
            if r["success"]:
                lines.append(f"✓ 会{r['num']} 已记")
            else:
                lines.append(f"❓ 会{r['num']} 没看懂")
        msg = " / ".join(lines)
        # V15优化：不发送即时回执，避免大量消息打扰
        print(f"  [批量回执] {msg}")
        return msg

    def send_revoke(self):
        """撤回回执"""
        msg = "↩️ 已撤销刚才的记录"
        self._send_message(msg)
        return msg

    def _send_message(self, text, retries=2):
        """发送消息到群（V40加固：重试 + 失败判定 + 告警落盘 + 返回状态）

        修复背景（2026-09-16）：此前仅打印错误即返回，早报在 user 授权缺失时
        “静默失败”——消息没发出，但脚本仍标记幂等已推送、schtasks 判退出码 0，
        造成“早报正常”假象。现改为：失败即重试，仍失败则写告警并返回 False，
        调用方（cmd_select）据此不置幂等标记 + 返回非 0 退出码。
        """
        if not hasattr(self, "failed"):
            self.failed = []
        cmd = [LARK_NODE_EXE, LARK_CLI_SCRIPT, "im", "+messages-send",
               "--chat-id", CHAT_ID, "--as", "bot",
               "--msg-type", "text", "--content", json.dumps({"text": text}, ensure_ascii=False)]
        last_err = ""
        for attempt in range(max(1, retries)):
            try:
                ok, stdout, stderr = run_cmd(cmd)
            except Exception as e:
                ok, stdout, stderr = False, "", str(e)
            if ok:
                if attempt > 0:
                    print(f"  [发送重试] 第{attempt+1}次成功")
                return True
            last_err = (stderr or stdout or "").strip()
            low = last_err.lower()
            if any(k in low for k in ("need_user_authorization", "unauthorized",
                                      "invalid_access_token", "99991663")):
                print("  [AUTH] user 授权缺失/失效，需重新执行 lark-cli auth login")
                break
            if attempt < retries - 1:
                time.sleep(1.5)
        # 失败：告警落盘 + 控制台告警
        self.failed.append(text[:40])
        self._alert(f"消息发送失败（累计{len(self.failed)}条）: {last_err[:200]}")
        print(f"  [ERROR] 消息发送失败: {last_err[:200]}")
        return False

    def _alert(self, msg):
        """失败告警落盘，便于 schtasks/健康自检抓取"""
        try:
            logf = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "learning_alerts.log")
            with open(logf, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
        except Exception as e:
            print(f"  [WARN] 告警落盘失败: {e}")

# ============================================================
# T10: 选题算法
# ============================================================

class CardSelector:
    """每日选题算法"""

    DAILY_LIMIT = 3  # 每日推送3张
    NEW_CARD_DAILY_LIMIT = 1  # 新卡每日上限1张

    def select(self, all_cards, today=None):
        """
        选题算法：
        1. 到期复习卡优先（下次复习日期 <= 今天）
        2. 不足用NOT_STARTED卡补足（按intro_offset到期）
        3. 新卡每日上限1张
        4. 前置依赖过滤
        5. MASTERED/ARCHIVED排除
        """
        if today is None:
            today = datetime.now().strftime("%Y-%m-%d")

        # 过滤有效卡片
        valid_cards = []
        # 先建立record_id到卡片的映射，用于依赖检查
        card_map = {}
        for c in all_cards:
            rid = c.get("_record_id", "")
            if rid:
                card_map[rid] = c

        for c in all_cards:
            status = parse_select_value(c.get("卡片状态", ""))
            if status in ("MASTERED", "ARCHIVED"):
                continue
            cold_val = c.get("cold_archived", "false")
            cold = str(cold_val).lower() == "true" if cold_val is not None else False
            if cold:
                continue
            # D3: 前置依赖过滤 - 依赖卡未达LEARNING则不出题
            prereq = c.get("前置依赖", "")
            if prereq:
                # 前置依赖可能是record_id或关联记录列表
                prereq_id = ""
                if isinstance(prereq, list) and prereq:
                    prereq_id = str(prereq[0])
                elif isinstance(prereq, str) and prereq.startswith("rec"):
                    prereq_id = prereq
                if prereq_id and prereq_id in card_map:
                    prereq_card = card_map[prereq_id]
                    prereq_status = parse_select_value(prereq_card.get("卡片状态", ""))
                    if prereq_status not in ("LEARNING", "REVIEWING", "MASTERED"):
                        continue  # 依赖卡未达LEARNING，跳过
            valid_cards.append(c)

        # 分类：到期复习卡 / 新卡（NOT_STARTED）
        due_cards = []
        new_cards = []

        for c in valid_cards:
            status = parse_select_value(c.get("卡片状态", ""))
            next_date = c.get("下次复习日期", "")
            intro_offset = c.get("intro_offset", "0")
            created = c.get("创建日期", "")

            if status == "NOT_STARTED":
                # 新卡：检查intro_offset是否到期
                try:
                    offset = int(float(intro_offset))
                except:
                    offset = 0
                if created:
                    created_dt = parse_datetime(created)
                    if created_dt:
                        intro_date = (created_dt + timedelta(days=offset)).strftime("%Y-%m-%d")
                        if intro_date <= today:
                            new_cards.append((c, intro_date))
                continue

            # 复习卡：检查下次复习日期
            if next_date and next_date <= today:
                due_cards.append((c, next_date))

        # 排序：到期卡按下次复习日期升序（越早到期越优先）
        due_cards.sort(key=lambda x: x[1])
        # 新卡按intro_offset升序
        new_cards.sort(key=lambda x: x[1])

        # 选题：先到期卡，不足用新卡补足（新卡上限1张）
        # C9/F16 tags间隔微调：同标签卡片不在同一天出现（避免同知识点集中复习）
        selected = []
        selected_tags = set()  # 已选卡片的标签集合
        
        def get_card_tags(card):
            """获取卡片的标签列表"""
            tags = card.get("标签", "")
            if isinstance(tags, list):
                return set(tags)
            elif tags:
                return {str(tags)}
            return set()
        
        def has_tag_conflict(card):
            """检查卡片是否与已选卡片有标签冲突"""
            card_tags = get_card_tags(card)
            if not card_tags or not selected_tags:
                return False
            # 有共同标签则冲突
            return bool(card_tags & selected_tags)
        
        # 先选到期卡（跳过与已选卡片标签冲突的卡片）
        skipped_due = []
        for c, _ in due_cards:
            if len(selected) >= self.DAILY_LIMIT:
                break
            if has_tag_conflict(c):
                skipped_due.append(c)
                print(f"  [tags微调] 跳过同标签卡片: {c.get('卡片问题正面','')[:20]}... (标签冲突，推迟到下一天)")
                continue
            selected.append(c)
            selected_tags.update(get_card_tags(c))
        
        # 如果跳过了标签冲突的卡片且还有名额，用新卡补足
        new_count = 0
        for c, _ in new_cards:
            if len(selected) >= self.DAILY_LIMIT:
                break
            if new_count >= self.NEW_CARD_DAILY_LIMIT:
                break
            if has_tag_conflict(c):
                print(f"  [tags微调] 跳过同标签新卡: {c.get('卡片问题正面','')[:20]}... (标签冲突)")
                continue
            selected.append(c)
            selected_tags.update(get_card_tags(c))
            new_count += 1
        
        # 如果还有名额且有被跳过的到期卡（标签冲突），检查是否可以选入（当已选卡片标签不冲突时）
        # 注意：这里不强制选入被跳过的卡片，因为tags微调的目的就是避免同标签集中
        # 如果所有可选卡片都标签冲突，说明当天只有同知识点的卡片，允许选入（不强制跳过）
        if len(selected) < self.DAILY_LIMIT and skipped_due:
            for c in skipped_due:
                if len(selected) >= self.DAILY_LIMIT:
                    break
                # 二次检查：如果此时已选卡片标签不冲突，可以选入
                if not has_tag_conflict(c):
                    selected.append(c)
                    selected_tags.update(get_card_tags(c))
                    print(f"  [tags微调] 二次选入被跳过卡片: {c.get('卡片问题正面','')[:20]}... (标签已不冲突)")
        
        return selected

    def format_morning_report(self, cards):
        """格式化早报消息（每条独立消息，不含答案）"""
        reports = []
        for i, c in enumerate(cards):
            title = c.get("卡片问题正面", "未知卡片")
            report = (
                f"📇 今日复习 {i+1}/{len(cards)}\n"
                f"Q：{title}\n"
                f"（答完后我会告诉你答案和下次复习时间）\n"
                f"──────────\n"
                f"直接回复：会 / 不会 / 模糊"
            )
            reports.append(report)
        return reports

# ============================================================
# 主流程
# ============================================================

def cmd_poll():
    """轮询群消息，处理新指令（V18优化：单次执行+超时控制+系统状态更新）"""
    start_time = time.time()
    MAX_EXECUTION_TIME = 480  # 8分钟最大执行时间，避免任务计划10分钟超时

    # V42修复：poll 互斥锁（防止定时任务与手动运行并发，避免同一消息被重复处理）
    import msvcrt
    POLL_LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".poll.lock")
    _lock_fh = None
    try:
        _lock_fh = open(POLL_LOCK_FILE, "a+", encoding="utf-8")
        try:
            msvcrt.locking(_lock_fh.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            print("[轮询模式] 另一 poll 进程正在运行，本次跳过（互斥锁保护）")
            return 0
    except Exception as _lock_e:
        print(f"[轮询模式] 互斥锁获取异常（继续执行）: {_lock_e}")

    print("[轮询模式] 读取群消息...")
    update_system_status(status="poll_running", extra={"poll_start": datetime.now().isoformat()})
    # V37优化：SYSTEM类型日志 - 系统启动
    write_system_log("SYSTEM", "学习系统轮询启动", "INFO", "system", f"启动时间={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, 最大执行时间={MAX_EXECUTION_TIME}s")

    # 读取最近消息
    # R8 S5-09: 熔断器检查 - 读取消息前检查熔断状态
    poll_circuit_breaker = None
    if V19_INTEGRATION_AVAILABLE:
        try:
            poll_circuit_breaker = CircuitBreaker.get_instance("feishu_poll", failure_threshold=3, recovery_timeout=60)
            if not poll_circuit_breaker.can_execute():
                print(f"  [熔断] 飞书消息读取处于熔断状态，跳过本次轮询")
                update_system_status(status="circuit_open", extra={"circuit_breaker": "feishu_poll"})
                return 1
        except Exception as cb_e:
            print(f"  [熔断] 熔断器检查异常: {cb_e}")
    
    cmd = ["lark-cli", "im", "+chat-messages-list",
           "--chat-id", CHAT_ID, "--as", "user",
           "--page-size", "50", "--order", "desc"]
    ok, stdout, stderr = run_cmd(cmd, timeout=60)
    
    # R8 S5-09: 熔断器记录 - 读取消息结果
    if poll_circuit_breaker:
        try:
            if ok:
                poll_circuit_breaker.record_success()
            else:
                poll_circuit_breaker.record_failure(reason=f"读取消息失败: {stderr[:100]}")
        except Exception as cb_e:
            print(f"  [熔断] 熔断器记录异常: {cb_e}")
    
    if not ok:
        print(f"读取消息失败: {stderr}")
        update_system_status(status="poll_failed", health_issues=1)
        # V37优化：ERROR类型日志 - 读取消息失败
        write_system_log("ERROR", "轮询读取消息失败", "ERROR", "system", f"错误信息={stderr[:200]}")
        # V21集成：AlertManager双通道告警
        if V19_INTEGRATION_AVAILABLE:
            try:
                alert_result = AlertManager.send_alert("ERROR", "轮询读取消息失败", stderr[:200], channel="both")
                print(f"  [V21告警] 已发送告警: local={alert_result.get('local')}, feishu={alert_result.get('feishu')}")
            except Exception as alert_e:
                print(f"  [V21告警] 告警发送异常: {alert_e}")
        return 1

    # 解析消息（JSON格式）
    try:
        data = json.loads(stdout)
        messages = data.get("data", {}).get("messages", [])
    except:
        print("消息解析失败")
        return 1

    print(f"读取到 {len(messages)} 条消息")

    # 日志四合一-RECEIVED：记录收到消息
    user_msg_count = sum(1 for m in messages if m.get("sender", {}).get("sender_type", "") != "app")
    if user_msg_count > 0:
        write_system_log("INSTRUCTION", f"轮询读取到{user_msg_count}条用户消息", "INFO", "user", f"总消息{len(messages)}条，用户消息{user_msg_count}条")

    # 获取今日卡片
    all_cards = get_all_cards()
    selector = CardSelector()
    today_cards = selector.select(all_cards)

    parser = InstructionParser()
    sender = ReceiptSender()

    # V38修复：加载已处理消息记录（避免重复处理导致消费索引耗尽）
    processed_messages = load_processed_messages()
    initial_processed_count = len(processed_messages)
    new_processed_count = 0

    # 处理用户消息（跳过机器人消息）
    for msg in reversed(messages):  # 按时间正序处理
        sender_type = msg.get("sender", {}).get("sender_type", "")
        if sender_type == "app":
            continue  # 跳过机器人消息

        # V38修复：消息去重（跳过已处理的消息，避免重复处理导致消费索引耗尽）
        msg_id = msg.get("message_id", "")
        if is_message_processed(msg_id, processed_messages):
            continue

        # lark-cli返回的消息内容在顶层content字段（纯文本，含"（由XXX发送）"后缀）
        text = msg.get("content", "")
        if not text:
            text = msg.get("body", {}).get("content", "")
        # 去掉"（由XXX发送）"后缀
        text = re.sub(r'（由[^）]+发送）\s*$', '', text).strip()
        # 去掉开头的"@机器人名"前缀（飞书@消息以"@名字 内容"形式出现，
        # 统一剥掉@前缀后，re.match类指令（洞察/完成/待办等）才能识别）
        text = re.sub(r'^@\S+\s*', '', text).strip()
        # 提取纯文本（飞书text消息content可能为JSON格式 {"text":"..."}）
        if isinstance(text, str) and text.startswith("{"):
            try:
                text = json.loads(text).get("text", "")
            except:
                pass

        if not text:
            # V38修复：空文本消息也标记为已处理，避免每次轮询都检查
            mark_message_processed(msg_id, processed_messages, action="empty_text")
            continue

        # 过滤系统回执消息（避免循环解析）
        system_receipt_patterns = [
            "❓ 没看懂", "✓ 已记录", "💡 答案", "📅 下次复习",
            "📋 到期提醒", "📇 今日复习", "🔍 知识检索",
            "✅ 洞察已记录", "✅ 任务已完成", "↩️ 已撤销",
            "⚠ 已记录但标记", "🔴 权限失效", "📭 今日无待复习",
            "请发：会/不会/模糊", "未找到相关知识",
            # V15根因修复：批量回执也是系统消息，不要当成用户指令
            "✓ 会", "❓ 会",
            # V15根因修复：创建/完成/归档任务的系统回执，防止被当成新指令重复处理
            "✅ 已创建任务", "❌ 创建失败", "✅ 待办已创建", "❌ 待办创建失败",
        ]
        is_system_receipt = any(p in text for p in system_receipt_patterns)
        if is_system_receipt:
            # V38修复：系统回执消息也标记为已处理
            mark_message_processed(msg_id, processed_messages, action="system_receipt")
            continue  # 跳过系统回执，避免循环解析

        # 显示类指令（查看待办/已完成）优先于自然语态销项：
        # 防止"显示所有已完成任务"被 D2 逻辑改写成"完成：显示所有任务"导致误判
        _is_display_cmd = bool(
            re.search(r'(查看|显示|列出|读取|列举|有哪些|有什么|全部|所有).{0,12}(待办|任务)', text)
            or re.search(r'(查看|显示|列出).{0,12}(已完成|完成)', text)
            or re.search(r'已完成.{0,10}(任务|待办)', text)
        )

        # P0修复：先处理基础任务指令（创建/完成/归档），不要被扩展指令吃掉
        task_prefixes = [
            "新建任务：", "新建任务:", "创建任务：", "创建任务:",
            "记录任务：", "记录任务:", "新增任务：", "新增任务:",
            "完成：", "完成:", "归档：", "归档:"
        ]
        is_task_instruction = any(text.startswith(p) for p in task_prefixes)
        # D2修复：自然语态销项/归档（无冒号前缀也识别），对齐用户手册XI
        if not is_task_instruction and not _is_display_cmd:
            _nl_complete = ["搞定", "已完成", "做完了", "done", "完成"]
            _nl_archive = ["收起来", "存档", "归档"]
            _low = text.lower()
            if any(k in _low for k in _nl_complete) or any(k in text for k in _nl_archive):
                # 剥离自然语态动词，仅保留任务名，避免 parse_complete 搜不到
                _strip = ["搞定", "已完成", "做完了", "done", "收起来", "存档", "归档", "完成了", "完成"]
                _body = text
                for _k in _strip:
                    _body = _body.replace(_k, "")
                _body = re.sub(r'^了+|了+$', '', _body)
                _body = _body.strip(" ：:，。.、")
                # 自然语态转规范前缀式，复用既有完成/归档分支
                if any(k in text for k in _nl_archive):
                    text = "归档：" + _body
                else:
                    text = "完成：" + _body
                is_task_instruction = True

        # V15 新功能群指令（错题本/费曼/番茄/时间块/今日推荐/知识演进）
        if not is_task_instruction and V15_ROUTER_AVAILABLE:
            try:
                v15_handled, v15_reply = handle_v15_command(text)
            except Exception as _ve:
                v15_handled, v15_reply = False, ""
                print(f"  [V15路由异常] {_ve}")
            if v15_handled:
                if v15_reply:
                    sender._send_message(v15_reply)
                print(f"  消息: {text[:30]}... → V15功能指令已处理")
                mark_message_processed(msg_id, processed_messages, action="v15_feature")
                new_processed_count += 1
                continue

        # 扩展指令处理（2026-09-17 修复：去掉 not is_task_instruction，让"完成/销项/归档"能进 handle_extension_command；
        # handle_extension_command 自带 handled 标记，非指令会自然返回 False，不会误吞普通消息）
        if not is_task_instruction and EXTENSION_AVAILABLE:
            handled, result = handle_extension_command(text)
            if handled:
                print(f"  消息: {text[:30]}... → 扩展指令已处理: {result}")
                # V38修复：标记消息为已处理
                mark_message_processed(msg_id, processed_messages, action="extension")
                new_processed_count += 1
                continue

        # 知识链路扩展指令（S10知识检索）- 同样跳过基础任务指令
        if not is_task_instruction and KNOWLEDGE_EXTENSION_AVAILABLE:
            handled, result = handle_knowledge_command(text)
            if handled:
                print(f"  消息: {text[:30]}... → 知识检索已处理: {result}")
                # V38修复：标记消息为已处理
                mark_message_processed(msg_id, processed_messages, action="knowledge")
                new_processed_count += 1
                continue

        # S5-10: 管理员修正指令（!admin override <event_id> <new_result> [reason]）
        if V19_INTEGRATION_AVAILABLE and text.startswith("!admin"):
            print(f"  消息: {text[:50]}... → 管理员修正指令")
            # 获取发送者ID（尝试多种可能的字段名）
            sender_info = msg.get("sender", {})
            sender_id = sender_info.get("id", "") or sender_info.get("open_id", "") or sender_info.get("user_id", "") or sender_info.get("sender_id", "")
            
            # 白名单校验
            if not AdminOverrideManager.is_admin(sender_id):
                reject_msg = f"❌ 权限拒绝：您不在管理员白名单中，无权执行管理员修正指令。\n当前白名单管理员数: {len(AdminOverrideManager.get_admin_list())}"
                sender._send_message(reject_msg)
                print(f"  [管理员修正] 非白名单用户拒绝: sender_id={sender_id}")
                write_system_log("SECURITY", "管理员修正指令被拒绝", "WARN", "admin_override", f"sender_id={sender_id}, text={text[:50]}")
                mark_message_processed(msg_id, processed_messages, action="admin_rejected")
                new_processed_count += 1
                continue
            
            # 白名单用户：解析并执行修正指令
            parse_result = AdminOverrideManager.parse_admin_command(text)
            if not parse_result.get("valid"):
                sender._send_message(f"❌ 指令解析失败: {parse_result.get('error', '未知错误')}\n格式: !admin override <event_id> <new_result> [reason]\n允许结果: 会/不会/模糊")
                mark_message_processed(msg_id, processed_messages, action="admin_parse_error")
                new_processed_count += 1
                continue
            
            # 执行修正
            override_result = AdminOverrideManager.execute_override(
                event_id=parse_result["event_id"],
                new_result=parse_result["new_result"],
                admin_user_id=sender_id,
                reason=parse_result.get("reason", "")
            )
            
            if override_result.get("success"):
                success_msg = f"✅ 管理员修正成功\n原event_id: {parse_result['event_id']}\n修正结果: {parse_result['new_result']}\n新event_id: {override_result.get('new_event_id', '未知')}"
                if parse_result.get("reason"):
                    success_msg += f"\n修正原因: {parse_result['reason']}"
                sender._send_message(success_msg)
                print(f"  [管理员修正] 修正成功: {parse_result['event_id']} -> {parse_result['new_result']}")
                write_system_log("INSTRUCTION", "管理员修正执行成功", "INFO", "admin_override", f"event_id={parse_result['event_id']}, new_result={parse_result['new_result']}, new_event_id={override_result.get('new_event_id', '')}")
            else:
                sender._send_message(f"❌ 管理员修正失败: {override_result.get('error', '未知错误')}")
                print(f"  [管理员修正] 修正失败: {override_result.get('error', '未知')}")
            
            mark_message_processed(msg_id, processed_messages, action="admin_override")
            new_processed_count += 1
            continue

        action, data = parser.parse(text, today_cards)
        # V38修复：解析后的消息统一标记为已处理（包括answer/revoke/requery/parse_error等）
        mark_message_processed(msg_id, processed_messages, action=action)
        new_processed_count += 1
        print(f"  消息: {text[:30]}... → 动作: {action}")

        # 日志四合一-PARSED：记录解析结果
        if action != "ignore":
            parse_detail = f"动作={action}"
            if data and "result" in data:
                parse_detail += f", 结果={data['result']}"
            if data and "card_index" in data:
                parse_detail += f", 卡片索引={data['card_index']}"
            write_system_log("INSTRUCTION", f"解析指令: {text[:30]}", "INFO", "parser", parse_detail, msg.get("message_id", ""))

        if action == "answer":
            # 记录流水
            card = today_cards[data["card_index"]]
            result = data["result"]
            msg_id = msg.get("message_id", "")

            # D1: ARCHIVED卡答题拒绝 - 已归档卡无法答题
            card_status = parse_select_value(card.get("卡片状态", ""))
            if card_status == "ARCHIVED":
                sender._send_message("❌ 该卡片已归档，无法答题。如需重新学习，请先取消归档。")
                print(f"  [D1拒绝] ARCHIVED卡答题被拒绝: {card.get('卡片问题正面','')[:30]}")
                continue

            # V21集成：错因（使用parse返回的error_type，支持「不会 记不清」等格式）
            error_type = data.get("error_type", "") if data else ""
            if error_type:
                print(f"  [V21错因] 使用parse返回的错因: {error_type}")

            # 写流水（P0修复：检查返回值，失败时回滚消费索引）
            flow_data = {
                "卡片ID": card.get("_record_id", ""),
                "卡片标题": card.get("卡片问题正面", ""),
                "结果": [result],
                "event_id": f"{card.get('_record_id','')}|{result}|{int(time.time()*1000)}",
                "来源": ["群指令"],
                "event_type": ["COMMIT"],
            }
            # V21集成：错因字段（如果解析到错因）
            if error_type:
                flow_data["错因"] = [error_type]
            write_ok = write_flow(flow_data)
            # 日志四合一-COMMITTED：记录流水写入成功
            if write_ok:
                write_system_log("INSTRUCTION", f"答题流水写入成功: {result}", "INFO", "system", f"卡片={card.get('_record_id','')}, 结果={result}, event_id={flow_data['event_id']}", flow_data["event_id"])
                # S3同日改判修复：标记同日同卡片的较早记录为superseded
                try:
                    superseded_count = mark_superseded_same_day(card.get("_record_id", ""), flow_data["event_id"])
                    if superseded_count > 0:
                        print(f"  [S3修复] 已标记{superseded_count}条较早记录为superseded")
                except Exception as s3_e:
                    print(f"  [S3修复] 标记superseded异常（不影响主流程）: {s3_e}")

                # R2修复：状态迁移（升级）检查
                try:
                    card_status = parse_select_value(card.get("卡片状态", ""))
                    upgraded, new_status, upgrade_reason = check_and_upgrade_status(card.get("_record_id", ""), card_status)
                    if upgraded:
                        print(f"  [R2状态迁移] 卡片升级: {card_status} → {new_status}（{upgrade_reason}）")
                        # 更新本地card对象的状态，避免后续使用旧状态
                        card["卡片状态"] = [new_status]
                        # 发送升级通知
                        try:
                            sender._send_message(f"🎉 卡片升级：{card.get('卡片问题正面','')[:30]}... 状态从 {card_status} 升级为 {new_status}（{upgrade_reason}）")
                        except:
                            pass
                except Exception as upgrade_e:
                    print(f"  [R2状态迁移] 状态迁移检查异常（不影响主流程）: {upgrade_e}")

                # V37优化：错因标记→卡片表更新（错因字段+版本号+1）
                if error_type:
                    try:
                        current_version = card.get("version", 1)
                        if isinstance(current_version, list):
                            current_version = current_version[0] if current_version else 1
                        new_version = int(current_version) + 1 if current_version else 2
                        card_updates = {
                            "错因": error_type,
                            "version": new_version
                        }
                        card_update_ok = update_card(card.get("_record_id", ""), card_updates)
                        if card_update_ok:
                            print(f"  [V37错因] 卡片表已更新: 错因={error_type}, 版本={current_version}→{new_version}")
                        else:
                            print(f"  [V37错因] 卡片表更新失败（不影响主流程）")
                    except Exception as err_e:
                        print(f"  [V37错因] 卡片表更新异常（不影响主流程）: {err_e}")
                    
                    # R5 S2-02接线：ErrorTypeHandler处理错因分类后的业务动作
                    if V19_INTEGRATION_AVAILABLE:
                        try:
                            handler_result = ErrorTypeHandler.handle_error_type(
                                card_id=card.get("_record_id", ""),
                                error_type=error_type,
                                current_version=card.get("version", 1)
                            )
                            if handler_result.get("success"):
                                print(f"  [R5错因处理] ErrorTypeHandler执行成功: {handler_result.get('action', 'N/A')}")
                            else:
                                print(f"  [R5错因处理] ErrorTypeHandler执行失败: {handler_result.get('reason', '未知原因')}")
                        except Exception as handler_e:
                            print(f"  [R5错因处理] ErrorTypeHandler异常（不影响主流程）: {handler_e}")

            if not write_ok:
                # 写入失败：回滚消费索引，发送错误回执，不继续后续处理
                print(f"  [P0修复] 流水写入失败，回滚消费索引: {parser.current_index} -> {parser.current_index - 1}")
                parser.current_index = max(0, parser.current_index - 1)
                parser._save_index()
                sender._send_message("❌ 答题记录写入失败，请稍后重试。（系统已记录错误日志）")
                # V21集成：DLQManager加入死信队列，自动重试
                if V19_INTEGRATION_AVAILABLE:
                    try:
                        dlq_ok = DLQManager.add_failed_message(
                            message_id=msg_id,
                            message_text=text[:100],
                            error_type="write_flow_failed",
                            error_detail=f"流水写入失败: card={card.get('_record_id','')}, result={result}"
                        )
                        dlq_stats = DLQManager.get_queue_stats()
                        print(f"  [V21 DLQ] 失败消息已加入队列: {dlq_ok}, 队列统计: total={dlq_stats['total']}, pending={dlq_stats['pending']}")
                    except Exception as dlq_e:
                        print(f"  [V21 DLQ] 加入死信队列异常: {dlq_e}")
                # V21集成：AlertManager告警
                if V19_INTEGRATION_AVAILABLE:
                    try:
                        AlertManager.send_alert("WARN", "流水写入失败", f"card={card.get('_record_id','')}, result={result}, msg_id={msg_id}", channel="local")
                    except:
                        pass
                continue

            # 即时回执
            sender.send_immediate(result, card.get("卡片问题正面", ""), data["explicit"])

            # 触发derive重算（单卡）
            # 延迟回执（答案+下次日期）
            answer = card.get("标准答案背面", card.get("标准答案_AI", "暂无答案"))
            next_date = (datetime.now() + timedelta(days=get_interval(result))).strftime("%Y-%m-%d")
            sender.send_delayed(answer, next_date, get_interval(result))
            # 日志四合一-DERIVED：记录派生计算完成
            write_system_log("INSTRUCTION", f"派生计算完成: {result}, 下次复习={next_date}", "INFO", "derive", f"卡片={card.get('_record_id','')}, 间隔={get_interval(result)}天, 下次日期={next_date}", flow_data["event_id"])

        elif action == "batch_answer":
            # S5-03批量部分失败实现：逐条处理，记录成功/失败，发送✓/❓/✓回执
            batch_answers = data.get("answers", []) if data else []
            batch_results = []
            print(f"  [S5-03批量] 收到批量指令，共{len(batch_answers)}条答案")
            
            for ans in batch_answers:
                result = ans.get("result", "")
                card_idx = ans.get("card_index", -1)
                num = card_idx + 1
                
                if card_idx < 0 or card_idx >= len(today_cards):
                    batch_results.append({"num": num, "success": False, "reason": "卡片编号无效"})
                    print(f"    [批量] 会{num}: 失败（卡片编号无效）")
                    continue
                
                card = today_cards[card_idx]
                card_status = parse_select_value(card.get("卡片状态", ""))
                if card_status == "ARCHIVED":
                    batch_results.append({"num": num, "success": False, "reason": "卡片已归档"})
                    print(f"    [批量] 会{num}: 失败（卡片已归档）")
                    continue
                
                # 写流水
                flow_data = {
                    "卡片ID": card.get("_record_id", ""),
                    "卡片标题": card.get("卡片问题正面", ""),
                    "结果": [result],
                    "event_id": f"{card.get('_record_id','')}|{result}|{int(time.time()*1000)}",
                    "来源": ["群指令"],
                    "event_type": ["COMMIT"],
                }
                write_ok = write_flow(flow_data)
                
                if write_ok:
                    # 标记同日较早记录为superseded
                    try:
                        mark_superseded_same_day(card.get("_record_id", ""), flow_data["event_id"])
                    except Exception as s3_e:
                        print(f"    [批量] 标记superseded异常: {s3_e}")
                    
                    batch_results.append({"num": num, "success": True, "result": result})
                    print(f"    [批量] 会{num}: 成功（{result}）")
                    write_system_log("INSTRUCTION", f"批量答题成功: 会{num}={result}", "INFO", "system", f"卡片={card.get('_record_id','')}, event_id={flow_data['event_id']}", flow_data["event_id"])
                else:
                    batch_results.append({"num": num, "success": False, "reason": "流水写入失败"})
                    print(f"    [批量] 会{num}: 失败（流水写入失败）")
                    # 加入死信队列
                    if V19_INTEGRATION_AVAILABLE:
                        try:
                            DLQManager.add_failed_message(
                                message_id=msg.get("message_id", ""),
                                message_text=f"会{num}={result}",
                                error_type="batch_write_flow_failed",
                                error_detail=f"批量答题流水写入失败: card={card.get('_record_id','')}"
                            )
                        except Exception as dlq_e:
                            print(f"    [批量] 加入死信队列异常: {dlq_e}")
            
            # 发送批量回执（✓/❓/✓）
            if batch_results:
                sender.send_batch_result(batch_results)
                success_count = sum(1 for r in batch_results if r["success"])
                fail_count = len(batch_results) - success_count
                print(f"  [S5-03批量] 批量处理完成: 成功{success_count}条, 失败{fail_count}条")
                write_system_log("INSTRUCTION", f"批量答题完成: 成功{success_count}条, 失败{fail_count}条", "INFO", "system", f"总{len(batch_results)}条, 成功{success_count}条, 失败{fail_count}条")

        elif action == "parse_error":
            sender.send_error("格式不正确")

        elif action == "error":
            sender.send_error(data.get("reason", ""))

        elif action == "requery":
            # 重新推送今日卡片
            reports = selector.format_morning_report(today_cards)
            for r in reports:
                sender._send_message(r)
                time.sleep(0.5)


        elif action == "health_check":
            # V42修复：系统体检（调用 system_health_check.py 并回发群）
            print("  [系统体检] 收到指令，执行健康自检...")
            try:
                import subprocess as sp
                cmd = [sys.executable, "system_health_check.py"]
                hc = sp.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=180, cwd=os.path.dirname(os.path.abspath(__file__)))
                out = (hc.stdout or "") + ("\n" + hc.stderr[-300:] if hc.returncode != 0 and hc.stderr else "")
                lines = [ln for ln in out.splitlines() if ln.strip()]
                if not lines:
                    lines = ["健康自检执行完成（无输出）"]
                body = "\n".join(lines[:40])
                sender._send_message("🩺 系统体检结果：\n" + body)
                write_system_log("INSTRUCTION", "系统体检执行完成", "INFO", "health_check", f"返回码={hc.returncode}, 输出行数={len(lines)}")
            except Exception as _hc_e:
                sender._send_message(f"❌ 系统体检执行异常: {str(_hc_e)[:80]}")
                print(f"  [系统体检] 异常: {_hc_e}")


        elif action == "list_todo":
            # 查看待办任务（2026-09-16 新增）：读任务总表，过滤未完成，发群
            print("  [查看待办] 收到指令，读取任务总表...")
            try:
                rows = get_all_tasks()
                done_states = {"已完成", "完成", "已归档", "ARCHIVED", "DONE", "已取消", "取消"}
                open_tasks = [r for r in rows if str(r.get("状态", "")).strip() not in done_states]
                if not open_tasks:
                    sender._send_message("📋 当前没有待办任务，全部完成 🎉")
                else:
                    open_tasks.sort(key=lambda r: (str(r.get("优先级", "")), str(r.get("截止日期", "") or "")), reverse=False)
                    lines = [f"📋 待办任务 {len(open_tasks)} 项："]
                    for i, t in enumerate(open_tasks, 1):
                        name = str(t.get("任务名称", "")).strip()
                        pri = str(t.get("优先级", "")).strip() or "-"
                        due = str(t.get("截止日期", "") or "").split("T")[0] if t.get("截止日期") else ""
                        cat = str(t.get("类别", "")).strip() or "-"
                        if isinstance(t.get("类别"), list) and t.get("类别"):
                            cat = str(t["类别"][0])
                        lines.append(f"{i}. {name}｜{pri}｜{cat}｜截止 {due if due else '未设'}")
                    sender._send_message("\n".join(lines))
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"  [查看待办] 异常: {e}")
                sender._send_message("⚠️ 读取待办任务失败，请稍后再试")


        elif action == "list_done":
            # 显示已完成任务（2026-09-16 新增）
            print("  [查看已完成] 收到指令，读取任务总表...")
            try:
                rows = get_all_tasks()
                done_states = {"已完成", "完成", "已归档", "ARCHIVED", "DONE", "已取消", "取消"}
                done_tasks = [r for r in rows if str(r.get("状态", "")).strip() in done_states]
                if not done_tasks:
                    sender._send_message("📋 暂无已完成任务记录")
                else:
                    done_tasks.sort(key=lambda r: str(r.get("完成日期") or r.get("实际完成日期") or r.get("创建日期") or ""), reverse=True)
                    lines = [f"✅ 已完成任务 {len(done_tasks)} 项："]
                    for i, t in enumerate(done_tasks[:30], 1):
                        name = str(t.get("任务名称", "")).strip()
                        pri = str(t.get("优先级", "")).strip() or "-"
                        done_at = str(t.get("实际完成日期") or t.get("完成日期") or "").split("T")[0] or ""
                        lines.append(f"{i}. {name}｜{pri}｜{done_at if done_at else '完成'}")
                    sender._send_message("\n".join(lines))
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"  [查看已完成] 异常: {e}")
                sender._send_message("⚠️ 读取已完成任务失败，请稍后再试")


        elif action == "create_task":
            # 新建任务
            task_name = data.get("task_name", "")
            print(f"  [新建任务] 收到任务: {task_name}")
            try:
                import urllib.request as ur
                import json as js
                from datetime import datetime as dt
                env_path = r"C:\Users\Administrator\AppData\Local\hermes\profiles\agent6_scheduler\scripts\feishu_insight_link.env"
                app_id = ""
                app_secret = ""
                for line in open(env_path, encoding="utf-8-sig"):
                    line = line.strip()
                    if line.startswith("FEISHU_APP_ID="):
                        app_id = line.split("=", 1)[1]
                    elif line.startswith("FEISHU_APP_SECRET="):
                        app_secret = line.split("=", 1)[1]
                req = ur.Request(
                    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                    data=js.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with ur.urlopen(req, timeout=30) as r:
                    token = js.load(r)["tenant_access_token"]
                url = "https://open.feishu.cn/open-apis/bitable/v1/apps/X8N1bvN3na99dFsyu0gcU8zTnHf/tables/tblz3H4lV7PCrBrX/records"
                today_ms = int(dt.now().timestamp() * 1000)
                body = {
                    "fields": {
                        "任务名称": task_name,
                        "状态": "待办",
                        "优先级": "中",
                        "类别": "工作",
                        "截止日期": today_ms
                    }
                }
                req = ur.Request(
                    url,
                    data=js.dumps(body).encode(),
                    headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                    method="POST",
                )
                with ur.urlopen(req, timeout=30) as r:
                    resp = js.load(r)
                if resp.get("code") == 0:
                    sender._send_message(f"✅ 已创建任务：{task_name}")
                    print(f"  [新建任务] 成功: {task_name}")
                else:
                    sender._send_message(f"❌ 创建失败: {resp.get('msg', '未知错误')}")
            except Exception as e:
                sender._send_message(f"❌ 创建任务异常: {str(e)[:50]}")
                print(f"  [新建任务] 异常: {e}")
        elif action == "revoke":
            # D6: 手动撤回 - 标记原流水superseded，写入REVOKE流水
            target_eid = data.get("target_event_id")

            # V21修复：!revoke不带参数时，自动定位最近一条答题记录
            if not target_eid and V19_INTEGRATION_AVAILABLE:
                try:
                    latest_eid, msg = RevokeSimplifier.get_latest_answer_event_id()
                    if latest_eid:
                        target_eid = latest_eid
                        print(f"  [V21撤回简化] 自动定位最近一条: {msg}")
                        sender._send_message(f"🔍 自动定位最近一条答题记录\n{msg}")
                    else:
                        sender._send_message(f"❌ 未找到可撤回的答题记录: {msg}")
                except Exception as simplify_e:
                    print(f"  [V21撤回简化] 定位异常: {simplify_e}")

            if target_eid:
                # 查找原流水
                all_flows = get_all_flows()
                target_flow = None
                for f in all_flows:
                    if f.get("event_id", "") == target_eid:
                        target_flow = f
                        break
                if target_flow:
                    # 标记原流水superseded=TRUE
                    original_record_id = target_flow.get("_record_id", "")
                    if original_record_id:
                        update_data = {"superseded": True}
                        update_flow(original_record_id, update_data)
                    # 写入REVOKE流水
                    revoke_data = {
                        "卡片ID": target_flow.get("卡片ID", ""),
                        "卡片标题": target_flow.get("卡片标题", ""),
                        "结果": ["REVOKE"],
                        "event_id": f"{target_eid}_REVOKE_{int(time.time()*1000)}",
                        "来源": ["用户撤回"],
                        "revoke_of": target_eid,
                        "superseded": False,
                        "event_type": ["REVOKE"],
                    }
                    write_flow(revoke_data)
                    sender.send_revoke()
                    print(f"  [D6撤回] 已撤回流水: {target_eid}")
                    # V21集成：RevokeVerifier撤回复验 - 写入后自动读取复验
                    if V19_INTEGRATION_AVAILABLE:
                        try:
                            verified, details = RevokeVerifier.verify_revoke(target_eid)
                            print(f"  [V21撤回复验] verified={verified}, issues={details.get('issues', [])}")
                            if verified:
                                sender._send_message(f"✅ 撤回复验通过\n原流水superseded: {details.get('original_superseded')}\nREVOKE流水: {details.get('revoke_flow_found')}\nrevoke_of正确: {details.get('revoke_of_correct')}\nevent_id唯一: {details.get('event_id_unique')}")
                            else:
                                sender._send_message(f"⚠️ 撤回复验发现问题: {'; '.join(details.get('issues', ['未知']))}")
                        except Exception as verify_e:
                            print(f"  [V21撤回复验] 复验异常: {verify_e}")
                else:
                    sender._send_message(f"❌ 未找到流水: {target_eid}")
            else:
                sender._send_message("❌ 请指定要撤回的流水ID：!revoke <event_id>，或使用!revoke不带参数自动撤回最近一条")

        elif action == "ignore":
            pass  # 闲聊，静默丢弃

    elapsed = time.time() - start_time
    print(f"轮询完成（耗时{elapsed:.1f}s）")

    # V38修复：保存已处理消息记录（避免重复处理导致消费索引耗尽）
    save_processed_messages(processed_messages)
    print(f"  [V38去重] 已处理消息记录: 初始{initial_processed_count}条, 新增{new_processed_count}条, 总计{len(processed_messages)}条")

    update_system_status(status="poll_completed", extra={
        "poll_elapsed_seconds": round(elapsed, 1),
        "poll_messages_processed": len(messages),
        "poll_new_processed": new_processed_count,
        "poll_end_time": datetime.now().isoformat()
    })
    # V37优化：SYSTEM类型日志 - 系统完成
    write_system_log("SYSTEM", "学习系统轮询完成", "INFO", "system", f"耗时={elapsed:.1f}s, 处理消息={len(messages)}条")

    # V42修复：释放互斥锁
    if _lock_fh is not None:
        try:
            _lock_fh.seek(0)
            msvcrt.locking(_lock_fh.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
        _lock_fh.close()

    # S2-02接线：消费索引健康检查
    if V19_INTEGRATION_AVAILABLE:
        try:
            health_result = ConsumeIndexHealthChecker.check()
            if not health_result.get("healthy", True):
                issues = "; ".join(health_result.get("issues", []))
                write_system_log("WARN", f"消费索引健康检查异常: {issues}", "WARN", "system",
                                 f"current_index={health_result.get('current_index')}, age_minutes={health_result.get('age_minutes', 0):.1f}, unconsumed_count={health_result.get('unconsumed_count', 0)}")
        except Exception as health_e:
            print(f"  [WARN] 消费索引健康检查异常: {health_e}")
    
    # S8-09接线：凭据漂移检测（每小时检查一次）
    if V19_INTEGRATION_AVAILABLE:
        try:
            if CredentialDriftDetector.should_check_now():
                credential_result = CredentialDriftDetector.run_full_check(send_alert_on_failure=True)
                if not credential_result.get("overall_healthy", True):
                    issues = "; ".join(credential_result.get("issues", []))
                    print(f"  [S8-09] 凭据漂移检测异常: {issues}")
                    write_system_log("WARN", f"凭据漂移检测异常: {issues}", "WARN", "credential",
                                     f"usage_summary={json.dumps(credential_result.get('usage_summary', {}), ensure_ascii=False)}")
                else:
                    print(f"  [S8-09] 凭据漂移检测正常: success_rate={credential_result.get('usage_summary', {}).get('success_rate', 0)}%")
        except Exception as credential_e:
            print(f"  [WARN] 凭据漂移检测异常: {credential_e}")
    
    # R5 S2-02接线：看门狗检测"进程活着但功能死了"
    if V19_INTEGRATION_AVAILABLE:
        try:
            watchdog_result = Watchdog.check_health()
            if not watchdog_result.get("healthy", True):
                issues = "; ".join(watchdog_result.get("issues", []))
                print(f"  [R5看门狗] 系统健康检查异常: {issues}")
                write_system_log("WARN", f"看门狗检测到系统异常: {issues}", "WARN", "system",
                                 f"last_success={watchdog_result.get('last_success_time', 'N/A')}, should_alert={watchdog_result.get('should_alert', False)}")
        except Exception as watchdog_e:
            print(f"  [WARN] 看门狗检查异常: {watchdog_e}")
    
    # R5 S2-02接线：效率优化器定期维护（每10次轮询执行一次）
    if V19_INTEGRATION_AVAILABLE:
        try:
            maintenance_counter_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".maintenance_counter.json")
            maintenance_count = 0
            if os.path.exists(maintenance_counter_file):
                try:
                    with open(maintenance_counter_file, 'r', encoding='utf-8') as f:
                        counter_data = json.load(f)
                        maintenance_count = counter_data.get("count", 0)
                except:
                    pass
            
            maintenance_count += 1
            if maintenance_count >= 10:
                maintenance_result = EfficiencyOptimizer.run_maintenance()
                if maintenance_result.get("success"):
                    print(f"  [R5效率优化] 维护完成: {len(maintenance_result.get('actions', []))}项操作, 释放{maintenance_result.get('freed_space', 0)}字节")
                maintenance_count = 0
            
            try:
                with open(maintenance_counter_file, 'w', encoding='utf-8') as f:
                    json.dump({"count": maintenance_count, "last_update": datetime.now().isoformat()}, f)
            except:
                pass
        except Exception as optimizer_e:
            print(f"  [WARN] 效率优化器异常: {optimizer_e}")
    
    return 0

def cmd_select():
    """执行今日选题，推送早报"""
    print("[选题模式] 执行今日选题...")

    # V39修复：早报幂等保护——今天已推送过则跳过
    try:
        from v19_integration import DailyPusher
        if DailyPusher._already_pushed("morning"):
            print("  [幂等保护] 今日早报已推送过，跳过")
            return 0
    except Exception as e:
        print(f"  [WARN] 早报幂等检查异常: {e}")

    all_cards = get_all_cards()
    selector = CardSelector()
    today_cards = selector.select(all_cards)

    # V21集成：FatigueManager倦怠降速 - 倦怠模式下限制每日卡片数
    if V19_INTEGRATION_AVAILABLE:
        try:
            is_fatigue = FatigueManager.is_fatigue_mode()
            daily_limit = FatigueManager.get_daily_card_count(default_count=3)
            if is_fatigue and len(today_cards) > daily_limit:
                print(f"  [V21倦怠降速] 倦怠模式激活，今日卡片数从 {len(today_cards)} 降为 {daily_limit}")
                today_cards = today_cards[:daily_limit]
            elif is_fatigue:
                print(f"  [V21倦怠降速] 倦怠模式激活，今日卡片数 {len(today_cards)}（未超过限制 {daily_limit}）")
        except Exception as fatigue_e:
            print(f"  [V21倦怠降速] 倦怠检查异常: {fatigue_e}")

    print(f"  选中 {len(today_cards)} 张卡片:")
    for i, c in enumerate(today_cards):
        title = c.get("卡片问题正面", "未知")
        status = parse_select_value(c.get("卡片状态", ""))
        print(f"    [{i+1}] {title[:40]}... ({status})")

    # 重置消费索引
    parser = InstructionParser()
    parser.reset_index()

    # 推送早报（静默期不推送，只输出）
    now = datetime.now()
    if 23 <= now.hour or now.hour < 7:
        print("  [静默期] 不推送，07:00后自动推送")
    else:
        sender = ReceiptSender()
        # D4: 空队列处理 - 队列为空时推送提示，不硬凑
        if not today_cards:
            sender._send_message("📭 今日无待复习卡片\n（所有卡片均未到期，且无新卡可引入）")
            print("  [D4空队列] 今日无待复习卡片，已推送提示")
            # V40加固：空队列提示也纳入失败判定
            if getattr(sender, "failed", None):
                print(f"  [ALERT] 早报有 {len(sender.failed)} 条发送失败，返回非0以便重试")
                return 1
        else:
            reports = selector.format_morning_report(today_cards)
            for r in reports:
                sender._send_message(r)
                time.sleep(0.5)
            # V40加固：早报主体发送失败 → 不置幂等标记，返回非0（便于重试/告警）
            if getattr(sender, "failed", None):
                print(f"  [ALERT] 早报主体有 {len(sender.failed)} 条发送失败，跳过幂等标记并返回非0")
                return 1
            # V39修复：标记早报已推送（幂等保护）
            try:
                from v19_integration import DailyPusher
                DailyPusher._mark_pushed("morning")
            except:
                pass
            print("  早报已推送")

            # V44增强：注入每日三察（西安天气+社会规律/自然规律/人性洞察）到早报
            try:
                import sys as _sys
                _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from insight_daily import build_report
                ins_report, _ = build_report("llm")
                if ins_report:
                    body = ins_report.split("\n", 1)[1] if "\n" in ins_report else ins_report
                    sender._send_message(body)
                    print("  [V44增强] 三察洞察已注入早报")
                else:
                    print("  [V44增强] 三察生成为空，跳过")
            except Exception as ins_e:
                print(f"  [WARN] 三察注入失败(已忽略): {ins_e}")

            # V39增强：早报合并今日待办+已完成事项
            try:
                from task_insight_extension import get_tasks_summary
                tasks = get_tasks_summary(days_ahead=3)
                task_msg_parts = []
                if tasks["today_pending"]:
                    part = "📋 今日待办:\n"
                    for t in tasks["today_pending"][:5]:
                        part += f"  ⏰ {t['name']}\n"
                    task_msg_parts.append(part)
                if tasks["today_completed"]:
                    part = f"✅ 昨日已完成 ({len(tasks['today_completed'])}项):\n"
                    for t in tasks["today_completed"][:5]:
                        part += f"  ✓ {t['name']}\n"
                    task_msg_parts.append(part)
                if tasks["upcoming"]:
                    part = f"📅 即将到期 ({len(tasks['upcoming'])}项):\n"
                    for t in tasks["upcoming"][:3]:
                        from datetime import datetime as _dt
                        days = (t["due_date"] - _dt.now().date()).days if t["due_date"] else "?"
                        part += f"  • {t['name']} ({days}天后)\n"
                    task_msg_parts.append(part)
                # V41增强：任务优先级矩阵（艾森豪威尔矩阵可视化面板）
                try:
                    _all_todo = tasks.get("all_active") or (tasks["today_pending"] + tasks["upcoming"])
                    _ui = [t for t in _all_todo if t.get("priority", "低") == "高"]
                    _nui = [t for t in _all_todo if t.get("priority", "低") == "中"]
                    _nun = [t for t in _all_todo if t.get("priority", "低") not in ("高", "中")]
                    _mat = "📊 任务优先级矩阵:\n"
                    _mat += f"  🔴 重要紧急: {len(_ui)}个\n"
                    _mat += f"  🟡 重要不紧急: {len(_nui)}个\n"
                    _mat += f"  🟢 紧急不重要: 0个\n"
                    _mat += f"  ⚪ 不重要不紧急: {len(_nun)}个\n"
                    if _ui:
                        _mat += "  🔴 详情: " + "、".join(t['name'][:14] for t in _ui[:3]) + "\n"
                    sender._send_message(_mat)
                    print("  [V41增强] 任务优先级矩阵已推送")
                except Exception as _mat_e:
                    print(f"  [WARN] 任务优先级矩阵异常: {_mat_e}")

                # V15增强：每日三件事（从今日待办中选出最重要的3件）
                try:
                    if tasks["today_pending"]:
                        top3 = tasks["today_pending"][:3]
                        three_things = "🎯 今日三件事（最重要）:\n"
                        for i, t in enumerate(top3):
                            _p = t.get("priority", "低")
                            three_things += f"  {i+1}. [{_p}] {t['name']}\n"
                        sender._send_message(three_things)
                        print("  [V15增强] 每日三件事已推送")
                except Exception as three_e:
                    print(f"  [WARN] 每日三件事异常: {three_e}")
                    
                if task_msg_parts:
                    sender._send_message("\n".join(task_msg_parts))
                    print("  [V39增强] 早报待办事项已推送")
            except Exception as task_e:
                print(f"  [WARN] 早报待办加载异常: {task_e}")

        # S5-05: DLQ死信队列次日汇总补录
        if V19_INTEGRATION_AVAILABLE:
            try:
                from v19_integration import DLQManager
                dlq_summary = DLQManager.get_daily_summary()
                if dlq_summary.get("needs_attention"):
                    print(f"  [DLQ补录] 发现待处理消息: pending={dlq_summary['pending']}, dead={dlq_summary['dead']}")
                    # 自动重试pending消息
                    if dlq_summary["pending"] > 0:
                        print(f"  [DLQ补录] 自动重试 {dlq_summary['pending']} 条pending消息...")
                        retry_result = DLQManager.retry_pending(
                            max_retries=3,
                            max_messages=10,
                            parser=parser,
                            today_cards=today_cards
                        )
                        print(f"  [DLQ补录] 重试结果: retried={retry_result['retried']}, success={retry_result['success']}, failed={retry_result['failed']}, dead={retry_result['dead']}")
                    
                    # 推送DLQ汇总消息
                    summary_lines = [
                        "📋 DLQ死信队列日报",
                        f"日期: {dlq_summary.get('date', '未知')}",
                        f"队列总数: {dlq_summary.get('total', 0)}",
                        f"待重试: {dlq_summary.get('pending', 0)}",
                        f"已成功: {dlq_summary.get('success', 0)}",
                        f"已死亡: {dlq_summary.get('dead', 0)}",
                    ]
                    if dlq_summary.get("failed_messages"):
                        summary_lines.append("")
                        summary_lines.append("昨日失败消息:")
                        for fm in dlq_summary["failed_messages"][:5]:
                            summary_lines.append(f"  - {fm.get('message_text', '未知')} ({fm.get('error_type', '未知')})")
                    if dlq_summary.get("pending", 0) > 0:
                        summary_lines.append("")
                        summary_lines.append("⚠️  有待重试消息，系统已自动重试，请检查重试结果")
                    
                    sender._send_message("\n".join(summary_lines))
                    print("  [DLQ补录] DLQ汇总已推送")
                else:
                    print("  [DLQ补录] DLQ队列正常，无需补录")
            except Exception as dlq_e:
                print(f"  [DLQ补录] DLQ汇总补录异常: {dlq_e}")

        # S9: 推送到期提醒（如果有即将到期的任务）
        if EXTENSION_AVAILABLE:
            try:
                send_due_reminder(3)
                print("  到期提醒已推送")
            except Exception as e:
                print(f"  到期提醒推送失败: {e}")

    # V40加固：任何子消息发送失败都返回非0（sender 仅在非静默期定义）
    try:
        _failed = getattr(sender, "failed", None)
    except Exception:
        _failed = None
    if _failed:
        print(f"  [ALERT] 本次推送共 {len(_failed)} 条发送失败，返回非0")
        return 1

    return 0

def cmd_status():
    """查看系统状态"""
    print("[系统状态]")
    all_cards = get_all_cards()
    flows = get_all_flows()

    status_count = {}
    for c in all_cards:
        s = parse_select_value(c.get("卡片状态", ""))
        status_count[s] = status_count.get(s, 0) + 1

    print(f"  卡片总数: {len(all_cards)}")
    print(f"  流水总数: {len(flows)}")
    print(f"  状态分布:")
    for s, n in sorted(status_count.items()):
        print(f"    {s}: {n}")

    # 今日选题
    selector = CardSelector()
    today_cards = selector.select(all_cards)
    print(f"  今日选题: {len(today_cards)} 张")

    return 0

def write_system_log(log_type, message, severity="INFO", source="system", detail="", event_id=""):
    """写入系统事件日志（日志四合一：RECEIVED/PARSED/COMMITTED/DERIVED）"""
    import tempfile
    tmp_file = None
    try:
        log_data = {
            "log_type": [log_type],
            "message": message,
            "severity": [severity],
            "source": [source],
            "detail": detail,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "resolved": False,
        }
        if event_id:
            log_data["event_id"] = event_id

        tmp_filename = f"tmp_log_{int(time.time()*1000)}.json"
        tmp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), tmp_filename)
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False)

        cmd = ["lark-cli", "base", "+record-upsert",
               "--base-token", BASE_TOKEN, "--table-id", LOG_TABLE,
               "--as", "user", "--json", f"@{tmp_file}"]
        ok, stdout, stderr = run_cmd(cmd, timeout=30)
        if not ok:
            print(f"  [WARN] 系统日志写入失败: {stderr[:100]}")
        return ok
    except Exception as e:
        print(f"  [WARN] 系统日志写入异常: {e}")
        return False
    finally:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except:
                pass

def get_all_tasks():
    """读取任务总表全部记录（2026-09-16 新增，供"查看待办"指令）"""
    cmd = ["lark-cli", "base", "+record-list", "--base-token", BASE_TOKEN,
           "--table-id", TASK_TABLE, "--as", "user", "--limit", "200", "--format", "json"]
    ok, stdout, _ = run_cmd(cmd, timeout=60)
    if ok:
        try:
            data = json.loads(stdout)
            fields = data["data"]["fields"]
            rows = data["data"]["data"]
            record_ids = data["data"].get("record_id_list", [])
            records = []
            for i, row in enumerate(rows):
                record = {"_record_id": record_ids[i] if i < len(record_ids) else ""}
                for j, field in enumerate(fields):
                    val = row[j] if j < len(row) else None
                    if isinstance(val, list) and len(val) > 0 and field not in ("关联知识卡片",):
                        val = val[0]
                    record[field] = val
                records.append(record)
            return records
        except Exception as e:
            print(f"  [ERROR] 解析任务表JSON失败: {e}")
            return []
    return []


def get_all_cards():
    """获取所有学习卡记录（使用JSON格式，避免markdown解析问题）"""
    cmd = ["lark-cli", "base", "+record-list", "--base-token", BASE_TOKEN,
           "--table-id", CARD_TABLE, "--as", "user", "--limit", "200", "--format", "json"]
    ok, stdout, _ = run_cmd(cmd, timeout=60)
    if ok:
        try:
            data = json.loads(stdout)
            fields = data["data"]["fields"]
            rows = data["data"]["data"]
            record_ids = data["data"].get("record_id_list", [])
            records = []
            for i, row in enumerate(rows):
                record = {"_record_id": record_ids[i] if i < len(record_ids) else ""}
                for j, field in enumerate(fields):
                    val = row[j] if j < len(row) else None
                    # 处理单选/多选字段（数组形式）
                    if isinstance(val, list) and len(val) > 0:
                        val = val[0] if field not in ("tags",) else val
                    record[field] = val
                records.append(record)
            return records
        except Exception as e:
            print(f"  [ERROR] 解析学习卡JSON失败: {e}")
            return []
    return []

def get_all_flows():
    """获取所有流水记录（使用JSON格式，避免markdown截断event_id中的|字符）"""
    cmd = ["lark-cli", "base", "+record-list", "--base-token", BASE_TOKEN,
           "--table-id", FLOW_TABLE, "--as", "user", "--limit", "200", "--format", "json"]
    ok, stdout, _ = run_cmd(cmd, timeout=60)
    if ok:
        try:
            data = json.loads(stdout)
            fields = data["data"]["fields"]
            rows = data["data"]["data"]
            record_ids = data["data"].get("record_id_list", [])
            records = []
            for i, row in enumerate(rows):
                record = {"_record_id": record_ids[i] if i < len(record_ids) else ""}
                for j, field in enumerate(fields):
                    val = row[j] if j < len(row) else None
                    # 处理单选字段（数组形式）
                    if isinstance(val, list) and len(val) > 0:
                        val = val[0]
                    record[field] = val
                records.append(record)
            return records
        except Exception as e:
            print(f"  [ERROR] 解析流水JSON失败: {e}")
            return []
    return []

def write_flow(data):
    """写入流水记录（使用临时JSON文件方式，避免中文编码问题）"""
    import tempfile
    tmp_file = None
    try:
        # R7 S5-07: 计算记录hash值并写入（用于数据完整性校验）
        if V19_INTEGRATION_AVAILABLE:
            try:
                # 补充默认字段用于hash计算
                hash_data = data.copy()
                if "客户端时间戳" not in hash_data:
                    hash_data["客户端时间戳"] = datetime.now().isoformat()
                if "自然日" not in hash_data:
                    hash_data["自然日"] = datetime.now().strftime("%Y-%m-%d")
                record_hash = HashManager.compute_hash(hash_data)
                data["record_hash"] = record_hash
                # 默认untrusted=False
                if "untrusted" not in data:
                    data["untrusted"] = False
            except Exception as hash_e:
                print(f"  [WARN] Hash计算失败（不影响写入）: {hash_e}")
        
        # 创建临时JSON文件（在当前目录内，lark-cli要求@文件路径在当前目录）
        tmp_filename = f"tmp_flow_{int(time.time()*1000)}.json"
        tmp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), tmp_filename)
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        cmd = ["lark-cli", "base", "+record-upsert",
               "--base-token", BASE_TOKEN, "--table-id", FLOW_TABLE,
               "--as", "user", "--json", f"@./{tmp_filename}"]
        ok, stdout, stderr = run_cmd(cmd, timeout=60)

        if not ok:
            print(f"  [ERROR] 流水写入失败: {stderr[:200]}")
            # 写入失败时记录到本地错误日志
            try:
                with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "write_errors.log"), "a", encoding="utf-8") as ef:
                    ef.write(f"[{datetime.now().isoformat()}] 流水写入失败: {stderr[:200]}\n")
                    ef.write(f"  data: {json.dumps(data, ensure_ascii=False)[:500]}\n")
            except:
                pass
        return ok
    except Exception as e:
        print(f"  [ERROR] 流水写入异常: {e}")
        return False
    finally:
        # 清理临时文件
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except:
                pass

def update_card(record_id, updates):
    """更新卡片记录（用于更新错因字段、版本号等）（使用临时JSON文件方式，避免中文编码问题）"""
    if not record_id:
        return False
    import tempfile
    tmp_file = None
    try:
        # 创建临时JSON文件
        tmp_filename = f"tmp_card_{int(time.time()*1000)}.json"
        tmp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), tmp_filename)
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(updates, f, ensure_ascii=False)

        cmd = ["lark-cli", "base", "+record-upsert",
               "--base-token", BASE_TOKEN, "--table-id", CARD_TABLE,
               "--as", "user", "--record-id", record_id,
               "--json", f"@./{tmp_filename}"]
        ok, stdout, stderr = run_cmd(cmd, timeout=60)

        if not ok:
            print(f"  [ERROR] 卡片更新失败: {stderr[:200]}")
        return ok
    except Exception as e:
        print(f"  [ERROR] 卡片更新异常: {e}")
        return False
    finally:
        # 清理临时文件
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except:
                pass

def update_flow(record_id, updates):
    """更新流水记录（用于标记superseded等）（使用临时JSON文件方式，避免中文编码问题）"""
    if not record_id:
        return False
    # 移除_record_id字段，使用--record-id参数
    updates.pop("_record_id", None)
    tmp_file = None
    try:
        tmp_filename = f"tmp_flow_update_{int(time.time()*1000)}.json"
        tmp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), tmp_filename)
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(updates, f, ensure_ascii=False)

        cmd = ["lark-cli", "base", "+record-upsert",
               "--base-token", BASE_TOKEN, "--table-id", FLOW_TABLE,
               "--as", "user", "--record-id", record_id,
               "--json", f"@./{tmp_filename}"]
        ok, stdout, stderr = run_cmd(cmd, timeout=60)
        if not ok:
            print(f"  [ERROR] 流水更新失败: {stderr[:300]}")
        return ok
    except Exception as e:
        print(f"  [ERROR] 流水更新异常: {e}")
        return False
    finally:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except:
                pass

def mark_superseded_same_day(card_id, current_event_id):
    """标记同日同卡片的较早记录为superseded=TRUE（S3同日改判修复）
    支持跨日6h宽限期：23:59和00:01视为同一天（6h内取末条）
    
    Args:
        card_id: 卡片record_id
        current_event_id: 当前新写入的event_id（不标记这条）
    Returns:
        int: 被标记为superseded的记录数
    """
    if not card_id:
        return 0
    
    try:
        all_flows = get_all_flows()
        if not all_flows:
            return 0
        
        # 筛选该卡片的流水
        card_flows = [f for f in all_flows if f.get("卡片ID", "") == card_id]
        if len(card_flows) <= 1:
            return 0
        
        # S4-19跨日6h宽限期：计算每条记录的有效日期（考虑跨日6h宽限）
        # 规则：如果两条记录时间差在6小时内，且跨午夜，则视为同一天
        CROSS_DAY_GRACE_HOURS = 6
        
        def get_effective_day(flow):
            """获取记录的有效日期（考虑跨日6h宽限）"""
            natural_day = flow.get("自然日", "")
            timestamp_str = flow.get("客户端时间戳", "")
            
            if not timestamp_str:
                return natural_day
            
            try:
                # 解析时间戳（支持多种格式）
                if isinstance(timestamp_str, str):
                    if "T" in timestamp_str:
                        # ISO 8601格式
                        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                        if ts.tzinfo is not None:
                            ts = ts.replace(tzinfo=None)
                    elif "/" in timestamp_str:
                        # yyyy/MM/dd HH:mm格式
                        ts = datetime.strptime(timestamp_str, "%Y/%m/%d %H:%M")
                    else:
                        return natural_day
                    
                    # 跨日6h宽限期：如果时间在00:00-06:00之间，视为前一天
                    if ts.hour < CROSS_DAY_GRACE_HOURS:
                        effective_date = (ts - timedelta(days=1)).strftime("%Y-%m-%d")
                        return effective_date
                    
                    return ts.strftime("%Y-%m-%d")
            except:
                pass
            
            return natural_day
        
        # 按有效日期分组（考虑跨日6h宽限）
        from collections import defaultdict
        day_groups = defaultdict(list)
        for f in card_flows:
            effective_day = get_effective_day(f)
            if effective_day:
                day_groups[effective_day].append(f)
        
        marked_count = 0
        for day, flows in day_groups.items():
            # S7-12修复：排除非答题记录（INIT/REVOKE/ADMIN_OVERRIDE），只对有效答题记录进行superseded标记
            valid_answer_results = {"会", "不会", "模糊"}
            answer_flows = [f for f in flows if f.get("结果", "") in valid_answer_results]
            if len(answer_flows) <= 1:
                continue
            
            # 按客户端时间戳排序，找到最新的有效答题记录
            flows_sorted = sorted(answer_flows, key=lambda x: x.get("客户端时间戳", "") or "")
            latest_flow = flows_sorted[-1]
            
            # 将较早的有效答题记录标记为superseded=TRUE
            for f in flows_sorted[:-1]:
                record_id = f.get("_record_id", "")
                if not record_id:
                    continue
                # 跳过当前新写入的记录（如果它是较早的记录，说明时间戳有问题，也跳过）
                if f.get("event_id", "") == current_event_id:
                    continue
                # 已经是superseded的跳过
                if f.get("superseded", False):
                    continue
                
                ok = update_flow(record_id, {"superseded": True})
                if ok:
                    marked_count += 1
                    print(f"  [S3修复] 标记superseded: record_id={record_id}, event_id={f.get('event_id','')}, day={day}")
        
        if marked_count > 0:
            print(f"  [S3修复] 同日改判superseded标记完成: 共标记{marked_count}条（含跨日6h宽限期）")
        
        return marked_count
    
    except Exception as e:
        print(f"  [S3修复] 标记superseded异常: {e}")
        return 0

def get_interval(result, consecutive_correct=0):
    """根据答题结果和连续正确次数获取间隔天数（V15增强：个性化间隔）
    
    间隔策略：
    - 不会：1天
    - 模糊：1天
    - 会（根据连续正确次数递增）：
      * 0次：2天
      * 1次：3天
      * 2次：5天
      * 3次：7天
      * 4次：15天
      * 5次+：30天
    """
    if result == "不会":
        return 1
    elif result == "模糊":
        return 1
    else:  # "会"
        # V15增强：根据连续正确次数调整间隔
        if consecutive_correct == 0:
            return 2
        elif consecutive_correct == 1:
            return 3
        elif consecutive_correct == 2:
            return 5
        elif consecutive_correct == 3:
            return 7
        elif consecutive_correct == 4:
            return 15
        else:
            return 30

def calculate_consecutive_correct(card_id):
    """
    计算指定卡片的连续正确次数
    从最近一条有效答题记录往前数，遇到"不会"或"模糊"则停止
    排除superseded=TRUE的记录和非答题记录（INIT/REVOKE/ADMIN_OVERRIDE）
    """
    if not card_id:
        return 0, []
    
    all_flows = get_all_flows()
    card_flows = [f for f in all_flows if f.get("卡片ID", "") == card_id]
    
    # 过滤有效答题记录（R7 S5-07: 排除untrusted=TRUE的记录，避免M值被污染）
    valid_results = {"会", "不会", "模糊"}
    valid_flows = []
    for f in card_flows:
        result = f.get("结果", "")
        superseded = f.get("superseded", False)
        untrusted = f.get("untrusted", False)
        # 处理数组类型
        if isinstance(untrusted, list):
            untrusted = untrusted[0] if untrusted else False
        if result in valid_results and superseded != True and untrusted != True:
            valid_flows.append(f)
    
    # 按event_id中的时间戳排序
    def get_timestamp(f):
        event_id = f.get("event_id", "")
        if event_id and "|" in event_id:
            try:
                return int(event_id.split("|")[-1])
            except:
                pass
        return 0
    
    valid_flows_sorted = sorted(valid_flows, key=get_timestamp)
    
    # 计算连续正确次数（从最近一条往前数）
    consecutive = 0
    for f in reversed(valid_flows_sorted):
        if f.get("结果", "") == "会":
            consecutive += 1
        else:
            break
    
    return consecutive, valid_flows_sorted

def check_and_upgrade_status(card_id, current_status=""):
    """
    检查并升级卡片状态
    升级门槛：
    - NOT_STARTED → LEARNING：首次作答
    - LEARNING → REVIEWING：连续正确≥3 + 跨≥3自然日 + 间隔≥3天
    - REVIEWING → MASTERED：连续正确≥5 + 跨≥7自然日
    - MASTERED → ARCHIVED：180天无反馈（暂不自动归档）
    
    返回：(是否升级, 新状态, 升级原因)
    """
    if not card_id:
        return False, current_status, "卡片ID为空"
    
    # 获取当前卡片状态
    if not current_status:
        all_cards = get_all_cards()
        card = next((c for c in all_cards if c.get("_record_id", "") == card_id), None)
        if not card:
            return False, "", "卡片不存在"
        current_status = parse_select_value(card.get("卡片状态", ""))
    
    # 计算连续正确次数
    consecutive, valid_flows = calculate_consecutive_correct(card_id)
    
    # NOT_STARTED → LEARNING：首次作答
    if current_status == "NOT_STARTED" and len(valid_flows) > 0:
        new_status = "LEARNING"
        update_ok = update_card(card_id, {"卡片状态": [new_status]})
        if update_ok:
            print(f"  [状态迁移] 卡片{card_id}: NOT_STARTED → LEARNING（首次作答）")
            return True, new_status, "首次作答"
        else:
            print(f"  [状态迁移] 卡片{card_id}: 状态更新失败")
            return False, current_status, "状态更新失败"
    
    # LEARNING → REVIEWING：连续正确≥3 + 跨≥3自然日
    if current_status == "LEARNING" and consecutive >= 3:
        # 检查连续正确的3条记录是否跨≥3自然日
        # 连续正确的3条记录 = 最近3条有效答题记录（都是"会"）
        if len(valid_flows) >= 3:
            # 获取最近3条有效答题记录（应该都是"会"，因为连续正确≥3）
            recent_3 = valid_flows[-3:]
            # 检查是否都是"会"
            if all(f.get("结果", "") == "会" for f in recent_3):
                def get_ts(f):
                    event_id = f.get("event_id", "")
                    if event_id and "|" in event_id:
                        try:
                            return int(event_id.split("|")[-1])
                        except:
                            pass
                    return 0
                
                first_ts = get_ts(recent_3[0])
                last_ts = get_ts(recent_3[-1])
                
                if first_ts > 0 and last_ts > 0:
                    from datetime import datetime
                    first_date = datetime.fromtimestamp(first_ts/1000).date()
                    last_date = datetime.fromtimestamp(last_ts/1000).date()
                    days_diff = (last_date - first_date).days
                    
                    # 跨≥3自然日 = 日期差≥2天（如9月10日、9月11日、9月12日 = 跨3个自然日，日期差=2天）
                    if days_diff >= 2:
                        new_status = "REVIEWING"
                        update_ok = update_card(card_id, {"卡片状态": [new_status]})
                        if update_ok:
                            print(f"  [状态迁移] 卡片{card_id}: LEARNING → REVIEWING（连续正确={consecutive}, 跨{days_diff+1}个自然日）")
                            return True, new_status, f"连续正确={consecutive}, 跨{days_diff+1}个自然日"
                        else:
                            print(f"  [状态迁移] 卡片{card_id}: 状态更新失败")
                            return False, current_status, "状态更新失败"
                    else:
                        return False, current_status, f"连续正确={consecutive}, 但仅跨{days_diff+1}个自然日（需≥3个自然日）"
                else:
                    return False, current_status, f"连续正确={consecutive}, 但时间戳无效"
            else:
                return False, current_status, f"连续正确={consecutive}, 但最近3条记录不都是'会'"
        else:
            return False, current_status, f"连续正确={consecutive}, 但有效答题记录不足3条"
    
    # REVIEWING → MASTERED：连续正确≥5 + 跨≥7自然日
    if current_status == "REVIEWING" and consecutive >= 5:
        if len(valid_flows) >= 5:
            correct_flows = [f for f in valid_flows if f.get("结果", "") == "会"]
            if len(correct_flows) >= 5:
                recent_correct = correct_flows[-5:]
                def get_ts(f):
                    event_id = f.get("event_id", "")
                    if event_id and "|" in event_id:
                        try:
                            return int(event_id.split("|")[-1])
                        except:
                            pass
                    return 0
                first_ts = get_ts(recent_correct[0])
                last_ts = get_ts(recent_correct[-1])
                days_diff = (last_ts - first_ts) / (1000 * 60 * 60 * 24)
                
                if days_diff >= 7:
                    new_status = "MASTERED"
                    update_ok = update_card(card_id, {"卡片状态": [new_status]})
                    if update_ok:
                        print(f"  [状态迁移] 卡片{card_id}: REVIEWING → MASTERED（连续正确={consecutive}, 跨{days_diff:.1f}天）")
                        return True, new_status, f"连续正确={consecutive}, 跨{days_diff:.1f}天"
                    else:
                        print(f"  [状态迁移] 卡片{card_id}: 状态更新失败")
                        return False, current_status, "状态更新失败"
                else:
                    return False, current_status, f"连续正确={consecutive}, 但仅跨{days_diff:.1f}天（需≥7天）"
            else:
                return False, current_status, f"连续正确={consecutive}, 但有效'会'记录不足5条"
        else:
            return False, current_status, f"连续正确={consecutive}, 但有效答题记录不足5条"
    
    return False, current_status, f"当前状态={current_status}, 连续正确={consecutive}, 未达升级门槛"

def main():
    parser = argparse.ArgumentParser(description="间隔重复学习系统主运行模块")
    parser.add_argument("--poll", action="store_true", help="轮询群消息（单次执行）")
    parser.add_argument("--poll-once", action="store_true", help="单次轮询群消息（与--poll等价，显式单次模式）")
    parser.add_argument("--select", action="store_true", help="执行今日选题")
    parser.add_argument("--status", action="store_true", help="查看系统状态")
    parser.add_argument("--reindex", action="store_true", help="重建消费索引")
    args = parser.parse_args()

    if args.poll or args.poll_once:
        return cmd_poll()
    elif args.select:
        return cmd_select()
    elif args.status:
        return cmd_status()
    elif args.reindex:
        p = InstructionParser()
        p.reset_index()
        print("消费索引已重置")
        return 0
    else:
        parser.print_help()
        return 0

if __name__ == "__main__":
    sys.exit(main())
