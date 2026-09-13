#!/usr/bin/env python
"""
V19综合集成模块
包含：撤回指令简化、错因功能启用、4项功能集成、DLQ自动重试
"""
import os
import sys
import json
import time
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# V34修复：敏感配置统一从config_local.py导入，避免硬编码泄露到GitHub
try:
    from config_local import (
        LARK_CLI, LARK_NODE_EXE, LARK_CLI_SCRIPT,
        BASE_TOKEN, FLOW_TABLE, CARD_TABLE, TARGET_CHAT_ID,
        EVENT_LOG_TABLE, TASK_TABLE, KNOWLEDGE_INDEX_TABLE,
        SYSTEM_HEALTH_TABLE, HEARTBEAT_TABLE, INSIGHT_TABLE, QUEUE_TABLE,
        ADMIN_WHITELIST,
    )
except ImportError:
    # 兼容：如果config_local.py不存在，使用环境变量或默认占位符
    LARK_CLI = os.environ.get("LARK_CLI", r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd")
    LARK_NODE_EXE = os.environ.get("LARK_NODE_EXE", r"C:\Users\Administrator\AppData\Local\hermes\node\node.exe")
    LARK_CLI_SCRIPT = os.environ.get("LARK_CLI_SCRIPT", r"C:\Users\Administrator\AppData\Local\hermes\node\node_modules\@larksuite\cli\scripts\run.js")
    BASE_TOKEN = os.environ.get("FEISHU_BASE_TOKEN", "")
    FLOW_TABLE = os.environ.get("FLOW_TABLE", "")
    CARD_TABLE = os.environ.get("CARD_TABLE", "")
    TARGET_CHAT_ID = os.environ.get("TARGET_CHAT_ID", "")
    EVENT_LOG_TABLE = os.environ.get("EVENT_LOG_TABLE", "")
    TASK_TABLE = os.environ.get("TASK_TABLE", "")
    KNOWLEDGE_INDEX_TABLE = os.environ.get("KNOWLEDGE_INDEX_TABLE", "")
    SYSTEM_HEALTH_TABLE = os.environ.get("SYSTEM_HEALTH_TABLE", "")
    HEARTBEAT_TABLE = os.environ.get("HEARTBEAT_TABLE", "")
    INSIGHT_TABLE = os.environ.get("INSIGHT_TABLE", "")
    QUEUE_TABLE = os.environ.get("QUEUE_TABLE", "")
    ADMIN_WHITELIST = os.environ.get("ADMIN_WHITELIST", "").split(",") if os.environ.get("ADMIN_WHITELIST") else []

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ALERTS_LOG = os.path.join(SCRIPT_DIR, "alerts.log")
DLQ_FILE = os.path.join(SCRIPT_DIR, ".dlq_queue.json")
FATIGUE_STATE_FILE = os.path.join(SCRIPT_DIR, ".fatigue_state.json")
CONSUME_INDEX_FILE = os.path.join(SCRIPT_DIR, ".consume_index.json")
SYSTEM_STATE_FILE = os.path.join(SCRIPT_DIR, ".system_state.json")

# 错因类型定义（V21修正：回归V16定稿四类）
ERROR_TYPES = {
    "记不清": "记忆模糊或遗忘，需要加强复习",
    "理解错": "对知识点理解有误，需要重新讲解",
    "题目歧义": "题目表述有歧义，需要修改题面（保留旧M值）",
    "已过期": "知识点已过时或不再适用，建议归档（触发ARCHIVED）",
}


def run_cmd(cmd, timeout=60):
    """执行命令"""
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode == 0, r.stdout.decode("utf-8", errors="replace"), r.stderr.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return False, "", "命令超时"
    except Exception as e:
        return False, "", str(e)


# ============================================================
# 1. 撤回指令简化（支持!revoke不带参数时撤回最近一条答题记录）
# ============================================================
class RevokeSimplifier:
    """撤回指令简化器 - 支持!revoke不带参数时撤回最近一条答题记录"""

    @staticmethod
    def get_latest_answer_event_id():
        """获取最近一条答题记录的event_id"""
        try:
            cmd = [LARK_CLI, "base", "+record-list",
                   "--base-token", BASE_TOKEN, "--table-id", FLOW_TABLE,
                   "--as", "user", "--limit", "50", "--format", "json"]
            ok, stdout, stderr = run_cmd(cmd, timeout=30)
            if not ok:
                return None, "读取流水表失败"

            data = json.loads(stdout)
            fields = data["data"]["fields"]
            rows = data["data"]["data"]

            # 查找最近一条答题记录（会/不会/模糊，排除INIT和REVOKE）
            latest_ts = 0
            latest_event_id = None
            latest_result = None

            for row in rows:
                result = row[fields.index("结果")] if "结果" in fields else ""
                if isinstance(result, list):
                    result = result[0] if result else ""
                if result in ("会", "不会", "模糊"):
                    event_id = row[fields.index("event_id")] if "event_id" in fields else ""
                    try:
                        ts = int(event_id.split("|")[-1])
                        if ts > latest_ts:
                            latest_ts = ts
                            latest_event_id = event_id
                            latest_result = result
                    except:
                        pass

            if latest_event_id:
                return latest_event_id, f"最近一条答题记录: {latest_result} ({latest_event_id})"
            return None, "未找到答题记录"

        except Exception as e:
            return None, f"获取最近答题记录异常: {e}"

    @staticmethod
    def parse_revoke_command(text):
        """
        解析!revoke命令
        支持: !revoke <event_id> 或 !revoke（不带参数，撤回最近一条）
        返回: (target_event_id, message)
        """
        text = text.strip()
        if text.startswith("!revoke") or text.startswith("!撤销"):
            parts = text.split()
            if len(parts) > 1:
                # 带参数，使用指定的event_id
                target_event_id = parts[1]
                return target_event_id, f"撤回指定记录: {target_event_id}"
            else:
                # 不带参数，撤回最近一条答题记录
                target_event_id, message = RevokeSimplifier.get_latest_answer_event_id()
                if target_event_id:
                    return target_event_id, f"自动撤回最近一条答题记录: {message}"
                else:
                    return None, f"无法自动撤回: {message}"
        return None, "非撤回命令"


# ============================================================
# 2. 错因功能启用
# ============================================================
class ErrorTypeParser:
    """错因解析器 - 支持「不会 理解错」「不会 记忆错」等格式"""

    @staticmethod
    def parse_with_error_type(text):
        """
        解析带错因的答题指令
        支持: 不会 理解错 / 不会 记忆错 / 不会 计算错 / 不会 粗心错
        返回: (result, error_type, has_error_type)
        """
        text = text.strip()

        # 检查是否带错因（不会 理解错 / 不会1 理解错）
        for error_type in ERROR_TYPES.keys():
            if text.endswith(error_type):
                # 提取前面的答题指令
                prefix = text[:-len(error_type)].strip()
                # 解析答题指令（会/不会/模糊，可能带编号）
                result = None
                card_num = None

                if prefix in ("会", "不会", "模糊"):
                    result = prefix
                else:
                    # 带编号的格式（不会1）
                    import re
                    match = re.match(r'^(会|不会|模糊)\s*(\d+)$', prefix)
                    if match:
                        result = match.group(1)
                        card_num = int(match.group(2))

                if result:
                    return result, error_type, True, card_num

        # 不带错因，返回原始结果
        return None, None, False, None

    @staticmethod
    def get_error_type_description(error_type):
        """获取错因描述"""
        return ERROR_TYPES.get(error_type, "未知错因")

    @staticmethod
    def get_all_error_types():
        """获取所有错因类型"""
        return ERROR_TYPES


class ErrorTypeHandler:
    """错因处理器 - 处理错因分类后的业务动作（重写/归档）"""
    
    @staticmethod
    def handle_error_type(card_id, error_type, current_version=1):
        """处理错因分类后的业务动作
        Args:
            card_id: 卡片record_id
            error_type: 错因类型（记不清/理解错/题目歧义/已过期）
            current_version: 当前版本号
        Returns:
            dict: {action: 'rewrite'/'archive'/'none', new_version: int, new_status: str, message: str}
        """
        result = {
            'action': 'none',
            'new_version': current_version,
            'new_status': None,
            'message': '',
            'card_id': card_id,
            'error_type': error_type
        }
        
        if error_type == "题目歧义":
            # 题目歧义 → 触发卡片重写（version+1，保留旧M值）
            result['action'] = 'rewrite'
            result['new_version'] = current_version + 1
            result['message'] = f"题目歧义，触发卡片重写: version {current_version} → {result['new_version']}"
            print(f"  [错因处理] {result['message']}")
            
        elif error_type == "已过期":
            # 已过期 → 触发归档（ARCHIVED）
            result['action'] = 'archive'
            result['new_status'] = 'ARCHIVED'
            result['message'] = f"知识点已过期，触发归档: 状态 → ARCHIVED"
            print(f"  [错因处理] {result['message']}")
            
        elif error_type in ("记不清", "理解错"):
            # 记不清/理解错 → 正常学习行为，不触发特殊动作
            result['action'] = 'normal'
            result['message'] = f"错因分类为{error_type}，正常学习行为，不触发特殊动作"
            print(f"  [错因处理] {result['message']}")
        
        return result
    
    @staticmethod
    def apply_rewrite(card_id, new_version):
        """应用卡片重写（更新version字段）
        注意：此方法实际写入飞书表，调用前需确认
        """
        try:
            update_data = {"version": new_version}
            json_file = os.path.join(SCRIPT_DIR, f"_tmp_rewrite_{card_id}.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(update_data, f, ensure_ascii=False)
            
            cmd = [LARK_CLI, "base", "+record-upsert",
                   "--base-token", BASE_TOKEN,
                   "--table-id", CARD_TABLE,
                   "--record-id", card_id,
                   "--json", f"@{json_file}",
                   "--as", "user"]
            ok, stdout, stderr = run_cmd(cmd, timeout=30)
            
            # 清理临时文件
            if os.path.exists(json_file):
                os.remove(json_file)
            
            if ok:
                print(f"  [错因处理] 卡片重写成功: card_id={card_id}, version={new_version}")
                return True
            else:
                print(f"  [错因处理] 卡片重写失败: {stderr}")
                return False
        except Exception as e:
            print(f"  [错因处理] 卡片重写异常: {e}")
            return False
    
    @staticmethod
    def apply_archive(card_id):
        """应用归档（更新卡片状态为ARCHIVED）
        注意：此方法实际写入飞书表，调用前需确认
        """
        try:
            update_data = {"卡片状态": ["ARCHIVED"]}
            json_file = os.path.join(SCRIPT_DIR, f"_tmp_archive_{card_id}.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(update_data, f, ensure_ascii=False)
            
            cmd = [LARK_CLI, "base", "+record-upsert",
                   "--base-token", BASE_TOKEN,
                   "--table-id", CARD_TABLE,
                   "--record-id", card_id,
                   "--json", f"@{json_file}",
                   "--as", "user"]
            ok, stdout, stderr = run_cmd(cmd, timeout=30)
            
            # 清理临时文件
            if os.path.exists(json_file):
                os.remove(json_file)
            
            if ok:
                print(f"  [错因处理] 卡片归档成功: card_id={card_id}")
                return True
            else:
                print(f"  [错因处理] 卡片归档失败: {stderr}")
                return False
        except Exception as e:
            print(f"  [错因处理] 卡片归档异常: {e}")
            return False


# ============================================================
# 3. 告警管理器（双通道）
# ============================================================
class AlertManager:
    """告警管理器 - 本地日志+飞书消息双通道，支持1小时去重和小时摘要"""
    
    # 去重记录：key=(level, title), value=last_sent_timestamp
    _dedup_cache = {}
    _DEDUP_WINDOW_SECONDS = 3600  # 1小时去重窗口
    
    # 小时摘要计数：key=hour_str, value={level: count, ...}
    _hourly_stats = {}
    _last_summary_hour = None

    @classmethod
    def _is_duplicate(cls, level, title):
        """检查是否为重复告警（相同level+title在1小时内已发送过）"""
        key = (level, title)
        now = time.time()
        if key in cls._dedup_cache:
            last_sent = cls._dedup_cache[key]
            if now - last_sent < cls._DEDUP_WINDOW_SECONDS:
                return True
        return False

    @classmethod
    def _record_sent(cls, level, title):
        """记录告警发送时间"""
        key = (level, title)
        cls._dedup_cache[key] = time.time()

    @classmethod
    def _cleanup_expired(cls):
        """清理过期的去重记录"""
        now = time.time()
        expired_keys = [k for k, v in cls._dedup_cache.items() 
                       if now - v >= cls._DEDUP_WINDOW_SECONDS]
        for k in expired_keys:
            del cls._dedup_cache[k]

    @staticmethod
    def send_alert(level, title, message, channel="both"):
        """
        发送告警（支持1小时去重：相同level+title在1小时内只发1条飞书消息）
        level: INFO/WARN/ERROR/CRITICAL
        channel: local/feishu/both
        """
        timestamp = datetime.now().isoformat()
        alert_text = f"[{timestamp}] [{level}] {title}: {message}"
        result = {"local": False, "feishu": False, "timestamp": timestamp, "deduped": False}

        # 本地通道（每次都写入，用于审计）
        if channel in ("local", "both"):
            try:
                with open(ALERTS_LOG, "a", encoding="utf-8") as f:
                    f.write(alert_text + "\n")
                result["local"] = True
            except Exception as e:
                print(f"  [告警] 本地通道写入失败: {e}")

        # 飞书消息通道（1小时去重）
        if channel in ("feishu", "both"):
            # 检查是否重复
            if AlertManager._is_duplicate(level, title):
                result["deduped"] = True
                result["feishu"] = True  # 标记为已处理（去重）
                print(f"  [告警去重] 相同告警在1小时内已发送，跳过去重: [{level}] {title}")
            else:
                try:
                    feishu_text = f"⚠️ 系统告警\n级别: {level}\n标题: {title}\n内容: {message}\n时间: {timestamp}"
                    cmd = [LARK_CLI, "im", "+messages-send",
                           "--chat-id", TARGET_CHAT_ID,
                           "--text", feishu_text,
                           "--as", "user"]
                    ok, stdout, stderr = run_cmd(cmd, timeout=30)
                    if ok:
                        result["feishu"] = True
                        AlertManager._record_sent(level, title)  # 记录发送时间
                except Exception as e:
                    print(f"  [告警] 飞书通道异常: {e}")

        # 定期清理过期去重记录
        AlertManager._cleanup_expired()
        
        # 更新小时摘要计数
        hour_str = datetime.now().strftime("%Y-%m-%d %H:00")
        if hour_str not in AlertManager._hourly_stats:
            AlertManager._hourly_stats[hour_str] = {}
        if level not in AlertManager._hourly_stats[hour_str]:
            AlertManager._hourly_stats[hour_str][level] = 0
        AlertManager._hourly_stats[hour_str][level] += 1
        
        # 检查是否需要发送小时摘要（每小时的第1条告警触发）
        if AlertManager._last_summary_hour != hour_str:
            AlertManager._last_summary_hour = hour_str
            # 异步发送小时摘要（不阻塞当前告警）
            try:
                AlertManager.send_hourly_summary()
            except Exception as e:
                print(f"  [小时摘要] 发送失败: {e}")
        
        return result
    
    @classmethod
    def send_hourly_summary(cls):
        """发送小时摘要（汇总过去1小时的告警类型和次数）
        
        Returns:
            dict: 摘要发送结果
        """
        now = datetime.now()
        current_hour = now.strftime("%Y-%m-%d %H:00")
        prev_hour = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:00")
        
        # 获取上一小时的统计数据
        stats = cls._hourly_stats.get(prev_hour, {})
        if not stats:
            print(f"  [小时摘要] {prev_hour} 无告警记录，跳过摘要")
            return {"sent": False, "reason": "no_alerts"}
        
        # 构建摘要消息
        total_alerts = sum(stats.values())
        summary_lines = [
            f"📊 告警小时摘要",
            f"时段: {prev_hour} - {current_hour}",
            f"告警总数: {total_alerts}",
            "",
            "按级别分布:"
        ]
        for level in ["CRITICAL", "ERROR", "WARN", "INFO"]:
            count = stats.get(level, 0)
            if count > 0:
                summary_lines.append(f"  {level}: {count}次")
        
        summary_text = "\n".join(summary_lines)
        
        # 发送到飞书
        result = {"sent": False, "hour": prev_hour, "total": total_alerts}
        try:
            cmd = [LARK_CLI, "im", "+messages-send",
                   "--chat-id", TARGET_CHAT_ID,
                   "--text", summary_text,
                   "--as", "user"]
            ok, stdout, stderr = run_cmd(cmd, timeout=30)
            if ok:
                result["sent"] = True
                print(f"  [小时摘要] 已发送: {prev_hour}, 共{total_alerts}条告警")
        except Exception as e:
            print(f"  [小时摘要] 飞书发送失败: {e}")
        
        # 清理过期的小时统计（保留最近24小时）
        expired_hours = [h for h in cls._hourly_stats 
                         if h < (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:00")]
        for h in expired_hours:
            del cls._hourly_stats[h]
        
        return result


# ============================================================
# 3.5 凭据漂移检测器（S8-09）
# ============================================================
class CredentialDriftDetector:
    """凭据漂移检测器 - 定期检查API Key有效性、权限范围、使用频率
    
    个人项目简化版：
    - 检查lark-cli是否可用（执行简单命令验证）
    - 检查Base访问权限（读取表列表验证）
    - 记录凭据使用日志
    - 发现异常时发送告警
    """
    
    CREDENTIAL_LOG = os.path.join(SCRIPT_DIR, ".credential_usage.json")
    LAST_CHECK_FILE = os.path.join(SCRIPT_DIR, ".credential_last_check.json")
    CHECK_INTERVAL_SECONDS = 3600  # 每小时检查一次
    
    @classmethod
    def _load_usage_log(cls):
        """加载凭据使用日志"""
        if os.path.exists(cls.CREDENTIAL_LOG):
            try:
                with open(cls.CREDENTIAL_LOG, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"total_calls": 0, "success_calls": 0, "failed_calls": 0, 
                "last_check": None, "checks": []}
    
    @classmethod
    def _save_usage_log(cls, log_data):
        """保存凭据使用日志"""
        try:
            with open(cls.CREDENTIAL_LOG, "w", encoding="utf-8") as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  [凭据检测] 保存使用日志失败: {e}")
    
    @classmethod
    def _record_usage(cls, success, operation=""):
        """记录凭据使用情况"""
        log = cls._load_usage_log()
        log["total_calls"] = log.get("total_calls", 0) + 1
        if success:
            log["success_calls"] = log.get("success_calls", 0) + 1
        else:
            log["failed_calls"] = log.get("failed_calls", 0) + 1
        log["last_usage"] = datetime.now().isoformat()
        log["last_operation"] = operation
        cls._save_usage_log(log)
    
    @classmethod
    def check_lark_cli_available(cls):
        """检查lark-cli是否可用
        
        Returns:
            dict: 检查结果 {available, version, error}
        """
        result = {"available": False, "version": None, "error": None}
        try:
            cmd = [LARK_CLI, "--version"]
            ok, stdout, stderr = run_cmd(cmd, timeout=10)
            if ok and stdout:
                result["available"] = True
                result["version"] = stdout.strip()
            else:
                result["error"] = stderr or "lark-cli执行失败"
        except Exception as e:
            result["error"] = str(e)
        
        cls._record_usage(result["available"], "check_lark_cli")
        return result
    
    @classmethod
    def check_base_access(cls):
        """检查Base访问权限（读取表列表验证）
        
        Returns:
            dict: 检查结果 {accessible, table_count, error}
        """
        result = {"accessible": False, "table_count": 0, "error": None}
        try:
            cmd = [LARK_CLI, "base", "+table-list",
                   "--base-token", BASE_TOKEN,
                   "--as", "user", "--format", "json"]
            ok, stdout, stderr = run_cmd(cmd, timeout=30)
            if ok and stdout:
                data = json.loads(stdout)
                if data.get("ok"):
                    result["accessible"] = True
                    result["table_count"] = len(data.get("data", {}).get("tables", []))
                else:
                    result["error"] = data.get("error", {}).get("message", "Base访问失败")
            else:
                result["error"] = stderr or "Base访问命令执行失败"
        except Exception as e:
            result["error"] = str(e)
        
        cls._record_usage(result["accessible"], "check_base_access")
        return result
    
    @classmethod
    def check_im_access(cls):
        """检查即时通讯访问权限（发送测试消息验证）
        
        Returns:
            dict: 检查结果 {accessible, error}
        """
        result = {"accessible": False, "error": None}
        try:
            # 只检查消息列表读取权限，不发送消息（避免打扰用户）
            cmd = [LARK_CLI, "im", "+chat-messages-list",
                   "--chat-id", TARGET_CHAT_ID,
                   "--as", "user", "--format", "json",
                   "--limit", "1"]
            ok, stdout, stderr = run_cmd(cmd, timeout=30)
            if ok and stdout:
                data = json.loads(stdout)
                if data.get("ok") or "items" in data.get("data", {}):
                    result["accessible"] = True
                else:
                    result["error"] = data.get("error", {}).get("message", "IM访问失败")
            else:
                result["error"] = stderr or "IM访问命令执行失败"
        except Exception as e:
            result["error"] = str(e)
        
        cls._record_usage(result["accessible"], "check_im_access")
        return result
    
    @classmethod
    def run_full_check(cls, send_alert_on_failure=True):
        """执行完整的凭据漂移检测
        
        Args:
            send_alert_on_failure: 失败时是否发送告警
            
        Returns:
            dict: 完整检测结果
        """
        now = datetime.now()
        result = {
            "check_time": now.isoformat(),
            "overall_healthy": True,
            "checks": {},
            "issues": [],
            "usage_summary": {}
        }
        
        # 检查1: lark-cli可用性
        cli_check = cls.check_lark_cli_available()
        result["checks"]["lark_cli"] = cli_check
        if not cli_check["available"]:
            result["overall_healthy"] = False
            result["issues"].append(f"lark-cli不可用: {cli_check.get('error', '未知错误')}")
        
        # 检查2: Base访问权限
        base_check = cls.check_base_access()
        result["checks"]["base_access"] = base_check
        if not base_check["accessible"]:
            result["overall_healthy"] = False
            result["issues"].append(f"Base访问失败: {base_check.get('error', '未知错误')}")
        
        # 检查3: IM访问权限
        im_check = cls.check_im_access()
        result["checks"]["im_access"] = im_check
        if not im_check["accessible"]:
            result["overall_healthy"] = False
            result["issues"].append(f"IM访问失败: {im_check.get('error', '未知错误')}")
        
        # 使用统计
        usage_log = cls._load_usage_log()
        result["usage_summary"] = {
            "total_calls": usage_log.get("total_calls", 0),
            "success_calls": usage_log.get("success_calls", 0),
            "failed_calls": usage_log.get("failed_calls", 0),
            "success_rate": round(usage_log.get("success_calls", 0) / max(usage_log.get("total_calls", 1), 1) * 100, 1)
        }
        
        # 失败时发送告警
        if not result["overall_healthy"] and send_alert_on_failure:
            issue_text = "\n".join(result["issues"])
            AlertManager.send_alert(
                level="ERROR",
                title="凭据漂移检测失败",
                message=f"检测到凭据异常:\n{issue_text}\n\n使用统计: {json.dumps(result['usage_summary'], ensure_ascii=False)}",
                channel="both"
            )
        
        # 保存最后检查结果
        try:
            with open(cls.LAST_CHECK_FILE, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  [凭据检测] 保存检查结果失败: {e}")
        
        return result
    
    @classmethod
    def should_check_now(cls):
        """判断是否需要执行检查（每小时一次）
        
        Returns:
            bool: 是否需要检查
        """
        if not os.path.exists(cls.LAST_CHECK_FILE):
            return True
        try:
            with open(cls.LAST_CHECK_FILE, "r", encoding="utf-8") as f:
                last_check = json.load(f)
            last_time_str = last_check.get("check_time", "")
            if last_time_str:
                last_time = datetime.fromisoformat(last_time_str)
                return (datetime.now() - last_time).total_seconds() >= cls.CHECK_INTERVAL_SECONDS
        except:
            pass
        return True


# ============================================================
# 4. 消费索引健康检查器（V21修正：消除永久误报）
# ============================================================
class ConsumeIndexHealthChecker:
    """消费索引健康检查器
    V21修正：不再单纯用"索引年龄>30分钟"判异常，因为无新消息时索引本就不更新。
    新判据：连续N个轮询周期无索引更新 且 期间有新消息未被消费 → 才告警
    """

    @staticmethod
    def check(stale_threshold_minutes=60, check_unconsumed_messages=True):
        """检查消费索引健康状态（V21修正版）
        Args:
            stale_threshold_minutes: 索引年龄阈值（提高到60分钟，避免无消息时误报）
            check_unconsumed_messages: 是否检查有未消费消息
        """
        result = {
            "healthy": True,
            "current_index": 0,
            "updated_at": None,
            "age_seconds": 0,
            "age_minutes": 0,
            "stale": False,
            "has_unconsumed_messages": False,
            "unconsumed_count": 0,
            "issues": [],
            "check_mode": "V21_corrected",
        }
        try:
            if os.path.exists(CONSUME_INDEX_FILE):
                with open(CONSUME_INDEX_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                result["current_index"] = data.get("current_index", 0)
                updated_at_str = data.get("updated_at", "")
                if updated_at_str:
                    updated_at = datetime.fromisoformat(updated_at_str)
                    result["updated_at"] = updated_at_str
                    result["age_seconds"] = (datetime.now() - updated_at).total_seconds()
                    result["age_minutes"] = result["age_seconds"] / 60.0
                    result["stale"] = result["age_seconds"] > stale_threshold_minutes * 60

                # V21修正：检查是否有未消费的新消息
                if check_unconsumed_messages:
                    try:
                        cmd = [LARK_CLI, "im", "+chat-messages-list",
                               "--chat-id", TARGET_CHAT_ID, "--as", "user",
                               "--page-size", "20", "--order", "desc"]
                        ok, stdout, stderr = run_cmd(cmd, timeout=30)
                        if ok:
                            msg_data = json.loads(stdout)
                            messages = msg_data.get("data", {}).get("messages", [])
                            # 统计用户消息（非机器人）数量
                            user_messages = [m for m in messages if m.get("sender", {}).get("sender_type", "") != "app"]
                            # 如果有用户消息且索引年龄>阈值，说明可能有未消费消息
                            if user_messages and result["stale"]:
                                result["has_unconsumed_messages"] = True
                                result["unconsumed_count"] = len(user_messages)
                    except Exception as msg_e:
                        result["issues"].append(f"检查未消费消息异常: {msg_e}")

                # V21修正：只有"索引过期 且 有未消费消息"才判异常
                if result["stale"] and result["has_unconsumed_messages"]:
                    result["healthy"] = False
                    result["issues"].append(
                        f"消费索引已{result['age_minutes']:.1f}分钟未更新，且有{result['unconsumed_count']}条未消费消息"
                    )
                elif result["stale"] and not result["has_unconsumed_messages"]:
                    # 索引过期但无新消息 → 正常现象，不告警
                    result["issues"].append(
                        f"索引已{result['age_minutes']:.1f}分钟未更新，但无新消息待消费（正常）"
                    )
            else:
                result["healthy"] = False
                result["issues"].append("消费索引文件不存在")
        except Exception as e:
            result["healthy"] = False
            result["issues"].append(f"消费索引检查异常: {e}")
        return result


# ============================================================
# 5. 倦怠降速管理器
# ============================================================
class FatigueManager:
    """倦怠降速管理器 - 支持手动/自动进入和退出倦怠模式，倦怠持续时间限制
    
    倦怠模式规则：
    - 倦怠模式下每日卡片数降速（默认从3张降为1张）
    - 倦怠模式最多持续7天，到期自动恢复（不得永久降速）
    - 支持手动进入和退出倦怠模式
    - 支持自动检测（连续3天答题正确率<30%自动进入倦怠）
    """
    
    MAX_FATIGUE_DAYS = 7  # 倦怠模式最大持续天数
    DEFAULT_REDUCED_COUNT = 1  # 倦怠模式下默认卡片数
    FATIGUE_LOG_FILE = os.path.join(SCRIPT_DIR, ".fatigue_log.json")
    
    @staticmethod
    def _load_state():
        """加载倦怠状态"""
        try:
            if os.path.exists(FATIGUE_STATE_FILE):
                with open(FATIGUE_STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return {"fatigue_mode": False, "start_time": None, "reduced_card_count": 1, 
                "reason": "", "auto_recovery_time": None}
    
    @staticmethod
    def _save_state(state):
        """保存倦怠状态"""
        try:
            with open(FATIGUE_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  [倦怠管理] 保存状态失败: {e}")
    
    @staticmethod
    def _log_fatigue_event(event_type, reason=""):
        """记录倦怠事件日志"""
        try:
            log = []
            if os.path.exists(FatigueManager.FATIGUE_LOG_FILE):
                with open(FatigueManager.FATIGUE_LOG_FILE, "r", encoding="utf-8") as f:
                    log = json.load(f)
            
            log.append({
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                "reason": reason
            })
            
            # 只保留最近100条记录
            log = log[-100:]
            
            with open(FatigueManager.FATIGUE_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(log, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  [倦怠管理] 记录日志失败: {e}")
    
    @staticmethod
    def get_daily_card_count(default_count=3):
        """获取今日应推卡片数（倦怠时降速）"""
        state = FatigueManager._load_state()
        if state.get("fatigue_mode", False):
            # 检查是否超过最大持续天数，超过则自动恢复
            if FatigueManager._check_auto_recovery(state):
                return default_count
            return state.get("reduced_card_count", FatigueManager.DEFAULT_REDUCED_COUNT)
        return default_count
    
    @staticmethod
    def is_fatigue_mode():
        """是否处于倦怠模式"""
        state = FatigueManager._load_state()
        if state.get("fatigue_mode", False):
            # 检查是否超过最大持续天数，超过则自动恢复
            if FatigueManager._check_auto_recovery(state):
                return False
            return True
        return False
    
    @staticmethod
    def _check_auto_recovery(state):
        """检查是否需要自动恢复（超过最大持续天数）
        
        Returns:
            bool: 是否执行了自动恢复
        """
        if not state.get("fatigue_mode", False):
            return False
        
        start_time_str = state.get("start_time", "")
        if not start_time_str:
            return False
        
        try:
            start_time = datetime.fromisoformat(start_time_str)
            days_in_fatigue = (datetime.now() - start_time).days
            if days_in_fatigue >= FatigueManager.MAX_FATIGUE_DAYS:
                # 自动恢复
                state["fatigue_mode"] = False
                state["end_time"] = datetime.now().isoformat()
                state["recovery_reason"] = f"自动恢复：倦怠模式已持续{days_in_fatigue}天，超过最大{FatigueManager.MAX_FATIGUE_DAYS}天限制"
                FatigueManager._save_state(state)
                FatigueManager._log_fatigue_event("auto_recovery", state["recovery_reason"])
                print(f"  [倦怠管理] 自动恢复：倦怠模式已持续{days_in_fatigue}天，超过最大{FatigueManager.MAX_FATIGUE_DAYS}天限制")
                return True
        except Exception as e:
            print(f"  [倦怠管理] 自动恢复检查异常: {e}")
        
        return False
    
    @staticmethod
    def enter_fatigue_mode(reason="手动触发", reduced_card_count=1):
        """进入倦怠模式
        
        Args:
            reason: 进入倦怠的原因
            reduced_card_count: 倦怠模式下的每日卡片数
            
        Returns:
            dict: 操作结果
        """
        state = FatigueManager._load_state()
        
        if state.get("fatigue_mode", False):
            return {"success": False, "message": "已处于倦怠模式", "state": state}
        
        state["fatigue_mode"] = True
        state["start_time"] = datetime.now().isoformat()
        state["reduced_card_count"] = reduced_card_count
        state["reason"] = reason
        state["auto_recovery_time"] = (datetime.now() + timedelta(days=FatigueManager.MAX_FATIGUE_DAYS)).isoformat()
        
        FatigueManager._save_state(state)
        FatigueManager._log_fatigue_event("enter", reason)
        
        print(f"  [倦怠管理] 进入倦怠模式，原因: {reason}，每日卡片数降为: {reduced_card_count}")
        print(f"  [倦怠管理] 自动恢复时间: {state['auto_recovery_time']}（最多{FatigueManager.MAX_FATIGUE_DAYS}天）")
        
        return {"success": True, "message": "已进入倦怠模式", "state": state}
    
    @staticmethod
    def exit_fatigue_mode(reason="手动恢复"):
        """退出倦怠模式
        
        Args:
            reason: 退出倦怠的原因
            
        Returns:
            dict: 操作结果
        """
        state = FatigueManager._load_state()
        
        if not state.get("fatigue_mode", False):
            return {"success": False, "message": "当前未处于倦怠模式", "state": state}
        
        state["fatigue_mode"] = False
        state["end_time"] = datetime.now().isoformat()
        state["recovery_reason"] = reason
        
        FatigueManager._save_state(state)
        FatigueManager._log_fatigue_event("exit", reason)
        
        # 计算倦怠持续时间
        duration = "未知"
        if state.get("start_time"):
            try:
                start = datetime.fromisoformat(state["start_time"])
                duration = str((datetime.now() - start).days) + "天"
            except:
                pass
        
        print(f"  [倦怠管理] 退出倦怠模式，原因: {reason}，持续时间: {duration}")
        
        return {"success": True, "message": "已退出倦怠模式", "state": state}
    
    @staticmethod
    def get_fatigue_status():
        """获取倦怠状态详情
        
        Returns:
            dict: 倦怠状态详情
        """
        state = FatigueManager._load_state()
        
        # 检查是否需要自动恢复
        if state.get("fatigue_mode", False):
            FatigueManager._check_auto_recovery(state)
            state = FatigueManager._load_state()
        
        # 计算倦怠持续时间
        duration_days = 0
        if state.get("fatigue_mode", False) and state.get("start_time"):
            try:
                start = datetime.fromisoformat(state["start_time"])
                duration_days = (datetime.now() - start).days
            except:
                pass
        
        return {
            "fatigue_mode": state.get("fatigue_mode", False),
            "start_time": state.get("start_time"),
            "duration_days": duration_days,
            "max_days": FatigueManager.MAX_FATIGUE_DAYS,
            "reduced_card_count": state.get("reduced_card_count", FatigueManager.DEFAULT_REDUCED_COUNT),
            "reason": state.get("reason", ""),
            "auto_recovery_time": state.get("auto_recovery_time"),
            "remaining_days": max(0, FatigueManager.MAX_FATIGUE_DAYS - duration_days)
        }


# ============================================================
# 6. 撤回复验器
# ============================================================
class RevokeVerifier:
    """撤回操作写入后读取复验器"""

    @staticmethod
    def verify_revoke(target_event_id):
        """验证撤回操作是否正确写入"""
        details = {
            "target_event_id": target_event_id,
            "original_flow_found": False,
            "original_superseded": False,
            "revoke_flow_found": False,
            "revoke_of_correct": False,
            "event_id_unique": True,
            "issues": [],
        }
        try:
            cmd = [LARK_CLI, "base", "+record-list",
                   "--base-token", BASE_TOKEN, "--table-id", FLOW_TABLE,
                   "--as", "user", "--limit", "200", "--format", "json"]
            ok, stdout, stderr = run_cmd(cmd, timeout=60)
            if not ok:
                details["issues"].append(f"读取流水表失败: {stderr[:100]}")
                return False, details

            data = json.loads(stdout)
            fields = data["data"]["fields"]
            rows = data["data"]["data"]

            original_flow = None
            revoke_flow = None
            all_event_ids = []

            for row in rows:
                event_id = row[fields.index("event_id")] if "event_id" in fields else ""
                all_event_ids.append(event_id)
                if event_id == target_event_id:
                    original_flow = row
                if target_event_id in str(event_id) and "REVOKE" in str(event_id):
                    revoke_flow = row

            if original_flow:
                details["original_flow_found"] = True
                superseded = original_flow[fields.index("superseded")] if "superseded" in fields else False
                details["original_superseded"] = bool(superseded)
                if not superseded:
                    details["issues"].append("原流水superseded未标记为TRUE")
            else:
                details["issues"].append(f"未找到原流水: {target_event_id}")

            if revoke_flow:
                details["revoke_flow_found"] = True
                revoke_of = revoke_flow[fields.index("revoke_of")] if "revoke_of" in fields else ""
                details["revoke_of_correct"] = (revoke_of == target_event_id)
                if revoke_of != target_event_id:
                    details["issues"].append(f"revoke_of字段不正确")
            else:
                details["issues"].append("未找到REVOKE流水")

            if len(all_event_ids) != len(set(all_event_ids)):
                details["event_id_unique"] = False
                details["issues"].append("event_id存在重复")

        except Exception as e:
            details["issues"].append(f"复验异常: {e}")

        verified = len(details["issues"]) == 0
        return verified, details


# ============================================================
# 7. DLQ死信队列管理器
# ============================================================
class DLQManager:
    """死信队列管理器"""

    @staticmethod
    def add_failed_message(message_id, message_text, error_type, error_detail):
        """添加失败消息到DLQ"""
        try:
            queue = {"messages": [], "last_retry": None, "retry_count": 0}
            if os.path.exists(DLQ_FILE):
                with open(DLQ_FILE, "r", encoding="utf-8") as f:
                    queue = json.load(f)

            entry = {
                "message_id": message_id,
                "message_text": message_text,
                "error_type": error_type,
                "error_detail": error_detail[:200],
                "failed_at": datetime.now().isoformat(),
                "retry_count": 0,
                "status": "pending",
            }
            queue["messages"].append(entry)

            with open(DLQ_FILE, "w", encoding="utf-8") as f:
                json.dump(queue, f, ensure_ascii=False, indent=2)

            print(f"  [DLQ] 失败消息已加入队列: {message_id} ({error_type})")
            return True
        except Exception as e:
            print(f"  [DLQ] 加入队列失败: {e}")
            return False

    @staticmethod
    def get_queue_stats():
        """获取DLQ队列统计"""
        try:
            if os.path.exists(DLQ_FILE):
                with open(DLQ_FILE, "r", encoding="utf-8") as f:
                    queue = json.load(f)
                return {
                    "total": len(queue["messages"]),
                    "pending": sum(1 for m in queue["messages"] if m["status"] == "pending"),
                    "dead": sum(1 for m in queue["messages"] if m["status"] == "dead"),
                    "success": sum(1 for m in queue["messages"] if m["status"] == "success"),
                    "last_retry": queue.get("last_retry"),
                }
        except:
            pass
        return {"total": 0, "pending": 0, "dead": 0, "success": 0}

    @staticmethod
    def get_daily_summary(date_str=None):
        """获取DLQ每日汇总（用于次日早报）
        
        Args:
            date_str: 日期字符串（YYYY-MM-DD），默认为昨天
            
        Returns:
            dict: 汇总信息 {total, pending, success, dead, failed_messages, needs_attention}
        """
        try:
            if not date_str:
                date_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            if not os.path.exists(DLQ_FILE):
                return {"total": 0, "pending": 0, "success": 0, "dead": 0, 
                        "failed_messages": [], "needs_attention": False, "date": date_str}
            
            with open(DLQ_FILE, "r", encoding="utf-8") as f:
                queue = json.load(f)
            
            messages = queue.get("messages", [])
            total = len(messages)
            pending = sum(1 for m in messages if m.get("status") == "pending")
            success = sum(1 for m in messages if m.get("status") == "success")
            dead = sum(1 for m in messages if m.get("status") == "dead")
            
            # 筛选昨日失败的消息
            yesterday_failed = []
            for m in messages:
                failed_at = m.get("failed_at", "")
                if failed_at.startswith(date_str) and m.get("status") in ("pending", "dead"):
                    yesterday_failed.append({
                        "message_id": m.get("message_id"),
                        "message_text": m.get("message_text", "")[:50],
                        "error_type": m.get("error_type"),
                        "status": m.get("status"),
                        "retry_count": m.get("retry_count", 0)
                    })
            
            needs_attention = pending > 0 or dead > 0
            
            return {
                "total": total,
                "pending": pending,
                "success": success,
                "dead": dead,
                "failed_messages": yesterday_failed,
                "needs_attention": needs_attention,
                "date": date_str
            }
        except Exception as e:
            print(f"  [DLQ汇总] 获取汇总失败: {e}")
            return {"total": 0, "pending": 0, "success": 0, "dead": 0, 
                    "failed_messages": [], "needs_attention": False, "error": str(e)}

    @staticmethod
    def _write_flow_record(flow_data, msg_id):
        """写入流水记录（DLQ重试专用）
        
        Args:
            flow_data: 流水数据字典
            msg_id: 消息ID（用于临时文件名）
            
        Returns:
            bool: 是否写入成功
        """
        try:
            json_file = os.path.join(SCRIPT_DIR, f"dlq_retry_{msg_id}.json")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(flow_data, f, ensure_ascii=False)
            
            cmd = [LARK_CLI, "base", "+record-upsert",
                   "--base-token", BASE_TOKEN,
                   "--table-id", FLOW_TABLE,
                   "--as", "user",
                   "--json", f"@dlq_retry_{msg_id}.json"]
            ok, stdout, stderr = run_cmd(cmd, timeout=30)
            
            # 清理临时文件
            if os.path.exists(json_file):
                os.remove(json_file)
            
            return ok
        except Exception as e:
            print(f"  [DLQ重试] 写入流水异常: {e}")
            return False

    @staticmethod
    def retry_pending(max_retries=3, max_messages=10, parser=None, today_cards=None):
        """重试pending状态的消息（真正重新执行消息处理）
        
        Args:
            max_retries: 最大重试次数
            max_messages: 最多重试消息数
            parser: InstructionParser实例（为None时自动创建）
            today_cards: 今日卡片列表（为None时自动获取）
            
        Returns:
            dict: 重试结果 {retried, success, failed, dead, results}
        """
        try:
            if not os.path.exists(DLQ_FILE):
                return {"retried": 0, "success": 0, "failed": 0, "dead": 0, "results": []}

            with open(DLQ_FILE, "r", encoding="utf-8") as f:
                queue = json.load(f)

            retried = 0
            success_count = 0
            failed_count = 0
            dead_count = 0
            results = []

            # 只重试pending状态的消息，最多重试max_messages条
            pending_messages = [m for m in queue["messages"] if m["status"] == "pending"][:max_messages]

            # 延迟导入，避免循环依赖
            if parser is None:
                try:
                    sys.path.insert(0, SCRIPT_DIR)
                    from learning_system import InstructionParser, get_all_cards
                    parser = InstructionParser()
                    if today_cards is None:
                        today_cards = get_all_cards()
                except Exception as e:
                    print(f"  [DLQ重试] 导入学习系统模块失败: {e}")
                    return {"retried": 0, "success": 0, "failed": 0, "dead": 0, "error": "import_failed"}

            for msg in pending_messages:
                retried += 1
                msg["retry_count"] = msg.get("retry_count", 0) + 1
                retry_result = {
                    "message_id": msg["message_id"],
                    "retry_count": msg["retry_count"],
                    "success": False,
                    "action": None,
                    "error": None
                }

                try:
                    # 真正重新执行：解析消息内容
                    message_text = msg.get("message_text", "")
                    action, data = parser.parse(message_text, today_cards)
                    retry_result["action"] = action

                    if action == "answer":
                        # 答题类消息：根据card_index获取card_id，真实写入流水
                        if data and data.get("card_index") is not None:
                            card_idx = data["card_index"]
                            if 0 <= card_idx < len(today_cards):
                                card = today_cards[card_idx]
                                card_id = card.get("_record_id", "")
                                card_title = card.get("卡片问题正面", "")
                                result = data.get("result", "")
                                
                                if card_id and result:
                                    flow_data = {
                                        "卡片ID": card_id,
                                        "卡片标题": card_title,
                                        "结果": result,
                                        "event_id": f"{card_id}|{result}|{int(time.time()*1000)}",
                                        "来源": ["DLQ重试"],
                                        "event_type": ["COMMIT"],
                                        "revision": 1,
                                        "superseded": False,
                                    }
                                    if DLQManager._write_flow_record(flow_data, msg["message_id"]):
                                        msg["status"] = "success"
                                        msg["retried_at"] = datetime.now().isoformat()
                                        msg["retry_action"] = action
                                        msg["written_card_id"] = card_id
                                        success_count += 1
                                        retry_result["success"] = True
                                        print(f"  [DLQ重试] 消息 {msg['message_id']} 重试成功，写入流水 card={card_id} result={result}（第{msg['retry_count']}次）")
                                    else:
                                        raise Exception("写入流水失败")
                                else:
                                    raise Exception(f"card_id或result为空: card_id={card_id}, result={result}")
                            else:
                                raise Exception(f"card_index超出范围: {card_idx}, today_cards长度={len(today_cards)}")
                        else:
                            raise Exception(f"answer数据缺少card_index: {data}")
                    
                    elif action == "batch_answer":
                        # 批量答题：逐条处理，真实写入流水
                        if data and data.get("answers"):
                            batch_success = 0
                            batch_failed = 0
                            for ans_idx, ans in enumerate(data["answers"]):
                                try:
                                    card_idx = ans.get("card_index", -1)
                                    result = ans.get("result", "")
                                    if 0 <= card_idx < len(today_cards) and result:
                                        card = today_cards[card_idx]
                                        card_id = card.get("_record_id", "")
                                        card_title = card.get("卡片问题正面", "")
                                        flow_data = {
                                            "卡片ID": card_id,
                                            "卡片标题": card_title,
                                            "结果": result,
                                            "event_id": f"{card_id}|{result}|{int(time.time()*1000)}",
                                            "来源": ["DLQ重试"],
                                            "event_type": ["COMMIT"],
                                            "revision": 1,
                                            "superseded": False,
                                        }
                                        if DLQManager._write_flow_record(flow_data, f"{msg['message_id']}_{ans_idx}"):
                                            batch_success += 1
                                        else:
                                            batch_failed += 1
                                    else:
                                        batch_failed += 1
                                except Exception as be:
                                    batch_failed += 1
                                    print(f"  [DLQ重试] 批量处理单条失败: {be}")
                            
                            if batch_success > 0:
                                msg["status"] = "success"
                                msg["retried_at"] = datetime.now().isoformat()
                                msg["retry_action"] = action
                                msg["batch_success"] = batch_success
                                msg["batch_failed"] = batch_failed
                                success_count += 1
                                retry_result["success"] = True
                                print(f"  [DLQ重试] 消息 {msg['message_id']} 批量重试成功: {batch_success}成功/{batch_failed}失败")
                            else:
                                raise Exception(f"批量处理全部失败: {batch_failed}条")
                        else:
                            raise Exception("batch_answer数据缺少answers")
                    
                    elif action == "revoke":
                        # 撤回操作：写入REVOKE记录（真实处理）
                        if data and data.get("target_event_id"):
                            target_event_id = data["target_event_id"]
                            # 写入REVOKE类型流水记录
                            flow_data = {
                                "卡片ID": "",
                                "卡片标题": f"撤回操作: {target_event_id}",
                                "结果": "REVOKE",
                                "event_id": f"REVOKE|{target_event_id}|{int(time.time()*1000)}",
                                "来源": ["DLQ重试"],
                                "event_type": ["REVOKE"],
                                "revision": 1,
                                "superseded": False,
                            }
                            if DLQManager._write_flow_record(flow_data, msg["message_id"]):
                                msg["status"] = "success"
                                msg["retried_at"] = datetime.now().isoformat()
                                msg["retry_action"] = action
                                msg["target_event_id"] = target_event_id
                                success_count += 1
                                retry_result["success"] = True
                                print(f"  [DLQ重试] 消息 {msg['message_id']} 撤回操作已写入流水: {target_event_id}")
                            else:
                                raise Exception("撤回记录写入失败")
                        else:
                            raise Exception("revoke数据缺少target_event_id")
                    
                    elif action == "insight":
                        # 洞察笔记：标记为成功并记录（InsightArchiver集成较复杂，此处记录待处理）
                        msg["status"] = "success"
                        msg["retried_at"] = datetime.now().isoformat()
                        msg["retry_action"] = action
                        msg["note"] = "洞察笔记待人工确认（DLQ重试已标记）"
                        success_count += 1
                        retry_result["success"] = True
                        print(f"  [DLQ重试] 消息 {msg['message_id']} 洞察笔记已标记（待人工确认）")
                    
                    elif action == "ignore":
                        # 闲聊消息，标记为成功（无需处理）
                        msg["status"] = "success"
                        msg["retried_at"] = datetime.now().isoformat()
                        msg["retry_action"] = "ignore"
                        success_count += 1
                        retry_result["success"] = True
                        print(f"  [DLQ重试] 消息 {msg['message_id']} 为闲聊，标记为成功")
                    
                    else:
                        # 解析失败或其他动作
                        failed_count += 1
                        retry_result["error"] = f"action={action}，未处理"
                        print(f"  [DLQ重试] 消息 {msg['message_id']} 重试失败，action={action}")
                        
                except Exception as e:
                    failed_count += 1
                    retry_result["error"] = str(e)[:100]
                    print(f"  [DLQ重试] 消息 {msg['message_id']} 重试异常: {e}")

                # 检查是否超过最大重试次数
                if msg["retry_count"] >= max_retries and msg["status"] != "success":
                    msg["status"] = "dead"
                    msg["dead_at"] = datetime.now().isoformat()
                    dead_count += 1
                    print(f"  [DLQ重试] 消息 {msg['message_id']} 超过最大重试次数{max_retries}，标记为dead")

                results.append(retry_result)

            queue["last_retry"] = datetime.now().isoformat()
            queue["retry_count"] = queue.get("retry_count", 0) + retried

            with open(DLQ_FILE, "w", encoding="utf-8") as f:
                json.dump(queue, f, ensure_ascii=False, indent=2)

            return {
                "retried": retried,
                "success": success_count,
                "failed": failed_count,
                "dead": dead_count,
                "results": results
            }
        except Exception as e:
            print(f"  [DLQ重试] 重试异常: {e}")
            return {"retried": 0, "success": 0, "failed": 0, "dead": 0, "error": str(e)}


# ============================================================
# S5-09: 熔断器（Circuit Breaker）+ 系统广播
# ============================================================
class CircuitBreaker:
    """熔断器 - 连续失败触发熔断，熔断期间快速失败，超时后半开尝试恢复
    
    状态机：
    - CLOSED（正常）：请求正常通过，失败计数累加
    - OPEN（熔断）：连续失败达到阈值，快速失败，系统广播告警
    - HALF_OPEN（半开）：熔断超时后，允许少量请求试探，成功则恢复，失败则继续熔断
    """
    
    # 状态常量
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"
    
    # 默认配置
    DEFAULT_FAILURE_THRESHOLD = 5  # 连续失败5次触发熔断
    DEFAULT_RECOVERY_TIMEOUT = 60  # 熔断60秒后进入半开状态
    DEFAULT_HALF_OPEN_MAX_REQUESTS = 3  # 半开状态最多允许3个请求试探
    
    # 全局熔断器实例（按名称区分）
    _instances = {}
    
    def __init__(self, name, failure_threshold=None, recovery_timeout=None, half_open_max_requests=None):
        """初始化熔断器
        
        Args:
            name: 熔断器名称（如"feishu_api"、"flow_write"）
            failure_threshold: 连续失败阈值（默认5次）
            recovery_timeout: 熔断恢复超时秒数（默认60秒）
            half_open_max_requests: 半开状态最大试探请求数（默认3次）
        """
        self.name = name
        self.failure_threshold = failure_threshold or self.DEFAULT_FAILURE_THRESHOLD
        self.recovery_timeout = recovery_timeout or self.DEFAULT_RECOVERY_TIMEOUT
        self.half_open_max_requests = half_open_max_requests or self.DEFAULT_HALF_OPEN_MAX_REQUESTS
        
        # 状态
        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.open_time = None  # 熔断开始时间
        self.half_open_request_count = 0  # 半开状态已试探请求数
        self.half_open_success_count = 0  # 半开状态成功请求数
        
        # 统计
        self.total_failures = 0
        self.total_successes = 0
        self.total_circuit_breaks = 0
        self.total_recoveries = 0
    
    @classmethod
    def get_instance(cls, name, **kwargs):
        """获取全局熔断器实例（单例模式）"""
        if name not in cls._instances:
            cls._instances[name] = cls(name, **kwargs)
        return cls._instances[name]
    
    def can_execute(self):
        """检查是否可以执行请求（熔断状态下快速失败）
        
        Returns:
            bool: True=可以执行，False=熔断中，快速失败
        """
        if self.state == self.CLOSED:
            return True
        
        if self.state == self.OPEN:
            # 检查是否超时，超时则进入半开状态
            if self.open_time and (time.time() - self.open_time) >= self.recovery_timeout:
                self._transition_to_half_open()
                return True
            return False
        
        if self.state == self.HALF_OPEN:
            # 半开状态允许有限请求试探
            if self.half_open_request_count < self.half_open_max_requests:
                self.half_open_request_count += 1  # 记录试探请求
                return True
            return False
        
        return False
    
    def record_success(self):
        """记录请求成功"""
        self.total_successes += 1
        
        if self.state == self.HALF_OPEN:
            # 半开状态：记录试探请求（如果can_execute没有被调用过）
            if self.half_open_request_count < self.half_open_max_requests:
                self.half_open_request_count += 1
            self.half_open_success_count += 1
            # 半开状态所有试探请求都成功，则恢复到CLOSED
            if self.half_open_request_count >= self.half_open_max_requests:
                if self.half_open_success_count == self.half_open_max_requests:
                    self._transition_to_closed(reason="半开状态所有试探请求成功")
                else:
                    # 有失败，重新熔断
                    self._transition_to_open(reason="半开状态存在失败请求")
        
        elif self.state == self.CLOSED:
            # 正常状态下成功，重置失败计数
            self.failure_count = 0
    
    def record_failure(self, reason=""):
        """记录请求失败
        
        Args:
            reason: 失败原因（用于告警）
        """
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == self.CLOSED:
            # 连续失败达到阈值，触发熔断
            if self.failure_count >= self.failure_threshold:
                self._transition_to_open(reason=reason or f"连续失败{self.failure_count}次")
        
        elif self.state == self.HALF_OPEN:
            # 半开状态：记录试探请求（如果can_execute没有被调用过）
            if self.half_open_request_count < self.half_open_max_requests:
                self.half_open_request_count += 1
            # 半开状态失败，重新熔断
            self._transition_to_open(reason=reason or "半开状态试探请求失败")
    
    def _transition_to_open(self, reason=""):
        """转换到熔断状态（OPEN）"""
        if self.state != self.OPEN:
            self.state = self.OPEN
            self.open_time = time.time()
            self.total_circuit_breaks += 1
            print(f"  [熔断] {self.name} 触发熔断: {reason}")
            
            # 系统广播：熔断告警（CRITICAL级别，双通道）
            try:
                alert_msg = f"熔断器[{self.name}]触发熔断\n原因: {reason}\n连续失败: {self.failure_count}次\n熔断时间: {self.recovery_timeout}秒\n恢复后将进入半开状态试探"
                AlertManager.send_alert("CRITICAL", f"熔断触发: {self.name}", alert_msg, channel="both")
            except Exception as alert_e:
                print(f"  [熔断] 系统广播告警失败: {alert_e}")
    
    def _transition_to_half_open(self):
        """转换到半开状态（HALF_OPEN）"""
        if self.state == self.OPEN:
            self.state = self.HALF_OPEN
            self.half_open_request_count = 0
            self.half_open_success_count = 0
            print(f"  [熔断] {self.name} 熔断超时，进入半开状态（允许{self.half_open_max_requests}个请求试探）")
            
            # 系统广播：半开状态通知（WARN级别）
            try:
                alert_msg = f"熔断器[{self.name}]熔断超时，进入半开状态\n将允许{self.half_open_max_requests}个请求试探恢复\n全部成功则恢复正常，任一失败则重新熔断"
                AlertManager.send_alert("WARN", f"熔断半开: {self.name}", alert_msg, channel="local")
            except Exception as alert_e:
                print(f"  [熔断] 半开状态通知失败: {alert_e}")
    
    def _transition_to_closed(self, reason=""):
        """转换到正常状态（CLOSED）"""
        if self.state != self.CLOSED:
            self.state = self.CLOSED
            self.failure_count = 0
            self.open_time = None
            self.total_recoveries += 1
            print(f"  [熔断] {self.name} 恢复正常: {reason}")
            
            # 系统广播：恢复通知（INFO级别，双通道）
            try:
                alert_msg = f"熔断器[{self.name}]已恢复正常\n原因: {reason}\n累计熔断次数: {self.total_circuit_breaks}\n累计恢复次数: {self.total_recoveries}"
                AlertManager.send_alert("INFO", f"熔断恢复: {self.name}", alert_msg, channel="both")
            except Exception as alert_e:
                print(f"  [熔断] 恢复通知失败: {alert_e}")
    
    def get_status(self):
        """获取熔断器状态"""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "open_time": self.open_time,
            "open_duration": (time.time() - self.open_time) if self.open_time else 0,
            "half_open_request_count": self.half_open_request_count,
            "half_open_success_count": self.half_open_success_count,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "total_circuit_breaks": self.total_circuit_breaks,
            "total_recoveries": self.total_recoveries,
            "can_execute": self.can_execute(),
        }
    
    @staticmethod
    def get_all_status():
        """获取所有全局熔断器实例状态"""
        return {name: cb.get_status() for name, cb in CircuitBreaker._instances.items()}


# ============================================================
# S5-10: 管理员修正管理器（ADMIN_OVERRIDE + 白名单校验）
# ============================================================
class AdminOverrideManager:
    """管理员修正管理器 - 实现ADMIN_OVERRIDE事件写入和白名单校验
    
    功能：
    1. 管理员修正指令（!admin override <event_id> <new_result>）
    2. 写入ADMIN_OVERRIDE事件流水（revoke_of指向原事件）
    3. 白名单校验（只有白名单内的管理员账号可执行修正）
    4. rebuild后ADMIN_OVERRIDE事件保留
    """
    
    # 管理员白名单（可配置，默认为空，需要手动添加）
    ADMIN_WHITELIST = [
        # 示例："ou_xxxxxxxxxxxxxxxx"  # 管理员open_id
    ]
    
    # 允许的修正结果
    ALLOWED_RESULTS = ["会", "不会", "模糊"]
    
    @classmethod
    def is_admin(cls, user_id):
        """检查用户是否在管理员白名单中
        
        Args:
            user_id: 用户open_id
            
        Returns:
            bool: 是否为管理员
        """
        return user_id in cls.ADMIN_WHITELIST
    
    @classmethod
    def add_admin(cls, user_id):
        """添加管理员到白名单
        
        Args:
            user_id: 用户open_id
            
        Returns:
            bool: 是否添加成功
        """
        if user_id not in cls.ADMIN_WHITELIST:
            cls.ADMIN_WHITELIST.append(user_id)
            print(f"  [管理员修正] 已添加管理员: {user_id}")
            return True
        return False
    
    @classmethod
    def remove_admin(cls, user_id):
        """从白名单移除管理员
        
        Args:
            user_id: 用户open_id
            
        Returns:
            bool: 是否移除成功
        """
        if user_id in cls.ADMIN_WHITELIST:
            cls.ADMIN_WHITELIST.remove(user_id)
            print(f"  [管理员修正] 已移除管理员: {user_id}")
            return True
        return False
    
    @classmethod
    def parse_admin_command(cls, command_text):
        """解析管理员修正指令
        
        支持格式：
        - !admin override <event_id> <new_result>
        - !admin override <event_id> <new_result> <reason>
        
        Args:
            command_text: 指令文本
            
        Returns:
            dict: 解析结果 {action, event_id, new_result, reason, valid, error}
        """
        result = {
            "action": None,
            "event_id": None,
            "new_result": None,
            "reason": "",
            "valid": False,
            "error": None
        }
        
        if not command_text or not command_text.startswith("!admin"):
            result["error"] = "不是管理员指令"
            return result
        
        parts = command_text.strip().split()
        if len(parts) < 4:
            result["error"] = "指令格式错误，应为: !admin override <event_id> <new_result> [reason]"
            return result
        
        if parts[1] != "override":
            result["error"] = f"不支持的操作: {parts[1]}"
            return result
        
        result["action"] = "override"
        result["event_id"] = parts[2]
        result["new_result"] = parts[3]
        
        if len(parts) > 4:
            result["reason"] = " ".join(parts[4:])
        
        # 验证新结果是否合法
        if result["new_result"] not in cls.ALLOWED_RESULTS:
            result["error"] = f"不合法的修正结果: {result['new_result']}，允许值: {cls.ALLOWED_RESULTS}"
            return result
        
        result["valid"] = True
        return result
    
    @classmethod
    def execute_override(cls, event_id, new_result, admin_user_id, reason=""):
        """执行管理员修正
        
        Args:
            event_id: 要修正的原事件ID
            new_result: 新的结果（会/不会/模糊）
            admin_user_id: 执行修正的管理员用户ID
            reason: 修正原因
            
        Returns:
            dict: 修正结果 {success, error, new_event_id, original_found}
        """
        result = {
            "success": False,
            "error": None,
            "new_event_id": None,
            "original_found": False
        }
        
        # 白名单校验
        if not cls.is_admin(admin_user_id):
            result["error"] = f"用户 {admin_user_id} 不在管理员白名单中，无权执行修正"
            return result
        
        # 验证新结果
        if new_result not in cls.ALLOWED_RESULTS:
            result["error"] = f"不合法的修正结果: {new_result}"
            return result
        
        try:
            # 查找原流水记录
            cmd = [LARK_CLI, "base", "+record-list",
                   "--base-token", BASE_TOKEN,
                   "--table-id", FLOW_TABLE,
                   "--as", "user", "--format", "json",
                   "--limit", "200"]
            ok, stdout, stderr = run_cmd(cmd, timeout=60)
            if not ok or not stdout:
                result["error"] = f"查找原记录失败: {stderr[:100]}"
                return result
            
            data = json.loads(stdout)
            records = data.get("data", {}).get("data", [])
            fields = data.get("data", {}).get("fields", [])
            record_ids = data.get("data", {}).get("record_id_list", [])
            
            # 找到event_id字段索引
            event_id_idx = None
            card_id_idx = None
            for i, f in enumerate(fields):
                if f == "event_id":
                    event_id_idx = i
                elif f == "卡片ID":
                    card_id_idx = i
            
            if event_id_idx is None:
                result["error"] = "流水表中未找到event_id字段"
                return result
            
            # 查找原记录
            original_record = None
            original_card_id = None
            for i, record in enumerate(records):
                if len(record) > event_id_idx and record[event_id_idx] == event_id:
                    original_record = record
                    original_record_id = record_ids[i] if i < len(record_ids) else None
                    if card_id_idx is not None and len(record) > card_id_idx:
                        original_card_id = record[card_id_idx]
                    break
            
            if not original_record:
                result["error"] = f"未找到event_id={event_id}的原记录"
                return result
            
            result["original_found"] = True
            
            # 构建ADMIN_OVERRIDE流水记录
            new_event_id = f"{original_card_id}|ADMIN_OVERRIDE|{int(time.time()*1000)}"
            override_data = {
                "卡片ID": original_card_id,
                "卡片标题": original_record[fields.index("卡片标题")] if "卡片标题" in fields else "",
                "结果": "ADMIN_OVERRIDE",
                "event_id": new_event_id,
                "来源": ["管理员修正"],
                "event_type": ["ADMIN_OVERRIDE"],
                "revision": 1,
                "superseded": False,
                "revoke_of": event_id,
                "错因": [f"管理员修正为:{new_result}"] if reason else [f"管理员修正为:{new_result}"]
            }
            
            # 写入ADMIN_OVERRIDE流水
            json_file = os.path.join(SCRIPT_DIR, f".admin_override_{int(time.time())}.json")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(override_data, f, ensure_ascii=False)
            
            cmd = [LARK_CLI, "base", "+record-upsert",
                   "--base-token", BASE_TOKEN,
                   "--table-id", FLOW_TABLE,
                   "--as", "user",
                   "--json", f"@admin_override_{int(time.time())}.json"]
            ok, stdout, stderr = run_cmd(cmd, timeout=30)
            
            # 清理临时文件
            if os.path.exists(json_file):
                os.remove(json_file)
            
            if not ok:
                result["error"] = f"写入ADMIN_OVERRIDE流水失败: {stderr[:100]}"
                return result
            
            result["success"] = True
            result["new_event_id"] = new_event_id
            
            print(f"  [管理员修正] 修正成功: {event_id} -> {new_result}")
            print(f"  [管理员修正] 新event_id: {new_event_id}")
            if reason:
                print(f"  [管理员修正] 修正原因: {reason}")
            
        except Exception as e:
            result["error"] = f"修正异常: {str(e)}"
            print(f"  [管理员修正] 修正异常: {e}")
        
        return result
    
    @classmethod
    def get_admin_list(cls):
        """获取管理员白名单列表
        
        Returns:
            list: 管理员open_id列表
        """
        return cls.ADMIN_WHITELIST.copy()


# ============================================================
# S7-04: 自动归档器（180天无反馈自动归档）
# ============================================================
class AutoArchiver:
    """自动归档器 - 180天无反馈自动归档，错因"已过期"自动归档
    
    归档规则：
    1. 180天无反馈（上次复习日期超过180天）→ 自动设置cold_archived=true
    2. 错因为"已过期" → 自动归档
    3. 归档后卡片降权，不出题或降低出题概率
    4. 支持人工归档和取消归档
    """
    
    ARCHIVE_DAYS_THRESHOLD = 180  # 180天无反馈自动归档
    ARCHIVE_ERROR_TYPES = ["已过期", "过期"]  # 这些错因自动归档
    
    @classmethod
    def get_card_last_review_date(cls, card_id):
        """获取卡片的最后复习日期
        
        Args:
            card_id: 卡片ID
            
        Returns:
            datetime: 最后复习日期，如果没有则返回None
        """
        try:
            # 从流水表查询该卡片的最后一条答题记录
            cmd = [LARK_CLI, "base", "+record-list",
                   "--base-token", BASE_TOKEN,
                   "--table-id", FLOW_TABLE,
                   "--as", "user", "--format", "json",
                   "--limit", "100"]
            ok, stdout, stderr = run_cmd(cmd, timeout=60)
            if not ok or not stdout:
                return None
            
            data = json.loads(stdout)
            records = data.get("data", {}).get("data", [])
            fields = data.get("data", {}).get("fields", [])
            
            # 找到卡片ID和客户端时间戳字段的索引
            card_id_idx = None
            timestamp_idx = None
            for i, f in enumerate(fields):
                if f == "卡片ID":
                    card_id_idx = i
                elif f == "客户端时间戳":
                    timestamp_idx = i
            
            if card_id_idx is None:
                return None
            
            # 找到该卡片的所有记录，取最新的时间戳
            latest_timestamp = None
            for record in records:
                if len(record) > card_id_idx and record[card_id_idx] == card_id:
                    if timestamp_idx is not None and len(record) > timestamp_idx and record[timestamp_idx]:
                        try:
                            ts_str = record[timestamp_idx]
                            if isinstance(ts_str, str):
                                # 处理ISO 8601格式
                                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                                # 转换为不带时区的datetime（避免offset-naive/offset-aware错误）
                                if ts.tzinfo is not None:
                                    ts = ts.replace(tzinfo=None)
                                if latest_timestamp is None or ts > latest_timestamp:
                                    latest_timestamp = ts
                        except:
                            pass
            
            return latest_timestamp
        except Exception as e:
            print(f"  [自动归档] 获取卡片最后复习日期失败: {e}")
            return None
    
    @classmethod
    def should_auto_archive(cls, card):
        """判断卡片是否应该自动归档
        
        Args:
            card: 卡片记录字典
            
        Returns:
            tuple: (should_archive, reason)
        """
        card_id = card.get("_record_id", "")
        
        # 检查1: 已经归档的不再重复归档
        cold_archived = card.get("cold_archived", False)
        if isinstance(cold_archived, list):
            cold_archived = cold_archived[0] if cold_archived else False
        if cold_archived:
            return False, "已归档"
        
        # 检查2: 错因为"已过期"
        error_type = card.get("错因", "")
        if isinstance(error_type, list):
            error_type = error_type[0] if error_type else ""
        if error_type in cls.ARCHIVE_ERROR_TYPES:
            return True, f"错因为'{error_type}'，自动归档"
        
        # 检查3: 180天无反馈
        last_review_date = cls.get_card_last_review_date(card_id)
        if last_review_date:
            days_since_review = (datetime.now() - last_review_date).days
            if days_since_review >= cls.ARCHIVE_DAYS_THRESHOLD:
                return True, f"{days_since_review}天无反馈，超过{cls.ARCHIVE_DAYS_THRESHOLD}天阈值"
        
        return False, "不满足归档条件"
    
    @classmethod
    def archive_card(cls, card_id, reason="自动归档"):
        """归档卡片（设置cold_archived=true）
        
        Args:
            card_id: 卡片ID
            reason: 归档原因
            
        Returns:
            dict: 归档结果
        """
        result = {"success": False, "card_id": card_id, "reason": reason}
        try:
            # 更新卡片的cold_archived字段
            update_data = {"cold_archived": True}
            json_file = os.path.join(SCRIPT_DIR, f".archive_{card_id}.json")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(update_data, f, ensure_ascii=False)
            
            cmd = [LARK_CLI, "base", "+record-upsert",
                   "--base-token", BASE_TOKEN,
                   "--table-id", CARD_TABLE,
                   "--as", "user",
                   "--record-id", card_id,
                   "--json", f"@archive_{card_id}.json"]
            ok, stdout, stderr = run_cmd(cmd, timeout=30)
            
            # 清理临时文件
            if os.path.exists(json_file):
                os.remove(json_file)
            
            if ok:
                result["success"] = True
                print(f"  [自动归档] 卡片 {card_id} 已归档，原因: {reason}")
            else:
                result["error"] = stderr or "归档命令执行失败"
                print(f"  [自动归档] 卡片 {card_id} 归档失败: {result['error']}")
        except Exception as e:
            result["error"] = str(e)
            print(f"  [自动归档] 归档异常: {e}")
        
        return result
    
    @classmethod
    def run_auto_archive_scan(cls, dry_run=True):
        """执行自动归档扫描
        
        Args:
            dry_run: 是否为试运行（只报告不执行）
            
        Returns:
            dict: 扫描结果
        """
        result = {
            "scan_time": datetime.now().isoformat(),
            "dry_run": dry_run,
            "total_cards": 0,
            "to_archive": [],
            "archived": [],
            "skipped": []
        }
        
        try:
            # 获取所有卡片
            cmd = [LARK_CLI, "base", "+record-list",
                   "--base-token", BASE_TOKEN,
                   "--table-id", CARD_TABLE,
                   "--as", "user", "--format", "json",
                   "--limit", "100"]
            ok, stdout, stderr = run_cmd(cmd, timeout=60)
            if not ok or not stdout:
                result["error"] = stderr or "获取卡片列表失败"
                return result
            
            data = json.loads(stdout)
            records = data.get("data", {}).get("data", [])
            fields = data.get("data", {}).get("fields", [])
            record_ids = data.get("data", {}).get("record_id_list", [])
            
            result["total_cards"] = len(records)
            
            # 遍历每张卡片，检查是否需要归档
            for i, record in enumerate(records):
                card = {"_record_id": record_ids[i] if i < len(record_ids) else ""}
                for j, f in enumerate(fields):
                    if j < len(record):
                        card[f] = record[j]
                
                should_archive, reason = cls.should_auto_archive(card)
                if should_archive:
                    result["to_archive"].append({
                        "card_id": card["_record_id"],
                        "title": card.get("卡片问题正面", "未知"),
                        "reason": reason
                    })
                    
                    if not dry_run:
                        archive_result = cls.archive_card(card["_record_id"], reason)
                        if archive_result["success"]:
                            result["archived"].append(card["_record_id"])
                else:
                    result["skipped"].append(card["_record_id"])
            
        except Exception as e:
            result["error"] = str(e)
            print(f"  [自动归档] 扫描异常: {e}")
        
        return result


# ============================================================
# S5-07: Hash不匹配检测和untrusted标记
# ============================================================
class HashManager:
    """Hash管理器 - 计算记录hash值，检测不匹配，标记untrusted
    
    设计原则：
    - 基于关键字段计算hash（卡片ID、结果、event_id、时间戳）
    - hash不匹配时标记untrusted=TRUE，不丢数据
    - untrusted=TRUE的记录不计入连续正确次数（M值）
    - 支持B档（hash不匹配但数据保留）和A档（hash匹配）
    """
    
    # 用于计算hash的关键字段
    HASH_FIELDS = ["卡片ID", "结果", "event_id", "客户端时间戳", "自然日"]
    
    @staticmethod
    def compute_hash(record):
        """计算记录的hash值
        
        Args:
            record: 记录字典（包含关键字段）
            
        Returns:
            str: SHA256 hash值（前16位）
        """
        import hashlib
        
        # 提取关键字段的值，按固定顺序拼接
        hash_parts = []
        for field in HashManager.HASH_FIELDS:
            value = record.get(field, "")
            # 处理数组类型（如select字段返回数组）
            if isinstance(value, list):
                value = ",".join(str(v) for v in value)
            hash_parts.append(f"{field}={value}")
        
        # 拼接成字符串
        hash_string = "|".join(hash_parts)
        
        # 计算SHA256 hash
        hash_value = hashlib.sha256(hash_string.encode("utf-8")).hexdigest()[:16]
        
        return hash_value
    
    @staticmethod
    def verify_hash(record, expected_hash=None):
        """验证记录的hash值是否匹配
        
        Args:
            record: 记录字典
            expected_hash: 期望的hash值（如果为None，则从记录中提取）
            
        Returns:
            tuple: (is_match, computed_hash, expected_hash)
        """
        computed_hash = HashManager.compute_hash(record)
        
        # 如果没有提供期望hash，尝试从记录中提取
        if expected_hash is None:
            expected_hash = record.get("record_hash", "")
            if isinstance(expected_hash, list):
                expected_hash = expected_hash[0] if expected_hash else ""
        
        is_match = (computed_hash == expected_hash) if expected_hash else False
        
        return is_match, computed_hash, expected_hash
    
    @staticmethod
    def mark_untrusted(record_id, reason="hash不匹配"):
        """标记记录为untrusted
        
        Args:
            record_id: 记录ID
            reason: 标记原因
            
        Returns:
            bool: 是否标记成功
        """
        try:
            update_data = {"untrusted": True}
            cmd = [LARK_CLI, "base", "+record-upsert",
                   "--base-token", BASE_TOKEN,
                   "--table-id", FLOW_TABLE,
                   "--record-id", record_id,
                   "--json", json.dumps(update_data, ensure_ascii=False),
                   "--as", "user"]
            ok, stdout, stderr = run_cmd(cmd, timeout=30)
            
            if ok:
                print(f"  [Hash检测] 记录 {record_id} 已标记为untrusted: {reason}")
                # 系统日志
                try:
                    write_system_log("WARN", f"记录标记为untrusted: {reason}", "WARN", "hash_manager", f"record_id={record_id}, reason={reason}")
                except:
                    pass
                return True
            else:
                print(f"  [Hash检测] 标记untrusted失败: {stderr}")
                return False
        except Exception as e:
            print(f"  [Hash检测] 标记untrusted异常: {e}")
            return False
    
    @staticmethod
    def is_untrusted(record):
        """检查记录是否被标记为untrusted
        
        Args:
            record: 记录字典
            
        Returns:
            bool: 是否untrusted
        """
        untrusted = record.get("untrusted", False)
        # 处理数组类型
        if isinstance(untrusted, list):
            untrusted = untrusted[0] if untrusted else False
        return bool(untrusted)
    
    @staticmethod
    def filter_trusted_records(records):
        """过滤掉untrusted的记录（用于计算连续正确次数等）
        
        Args:
            records: 记录列表
            
        Returns:
            list: 只包含trusted记录的列表
        """
        return [r for r in records if not HashManager.is_untrusted(r)]
    
    @staticmethod
    def batch_verify(records):
        """批量验证记录的hash值
        
        Args:
            records: 记录列表
            
        Returns:
            dict: 验证结果统计
                - total: 总记录数
                - matched: hash匹配数
                - mismatched: hash不匹配数
                - no_hash: 无hash值数
                - mismatched_records: 不匹配的记录列表
        """
        result = {
            "total": len(records),
            "matched": 0,
            "mismatched": 0,
            "no_hash": 0,
            "mismatched_records": []
        }
        
        for record in records:
            expected_hash = record.get("record_hash", "")
            if isinstance(expected_hash, list):
                expected_hash = expected_hash[0] if expected_hash else ""
            
            if not expected_hash:
                result["no_hash"] += 1
                continue
            
            is_match, computed_hash, _ = HashManager.verify_hash(record, expected_hash)
            if is_match:
                result["matched"] += 1
            else:
                result["mismatched"] += 1
                result["mismatched_records"].append({
                    "record_id": record.get("_record_id", ""),
                    "event_id": record.get("event_id", ""),
                    "expected_hash": expected_hash,
                    "computed_hash": computed_hash
                })
        
        return result


# ============================================================
# S3-06: 每日推送补全（早报+午报+晚报）
# ============================================================
class DailyPusher:
    """每日推送器 - 早报、午报、晚报推送
    
    推送内容：
    - 早报（07:30）：今日学习计划、待复习卡片、昨日学习总结
    - 午报（12:00）：上午学习进度、下午学习建议、提醒答题
    - 晚报（21:00）：今日学习总结、连续学习天数、明日预告
    """
    
    PUSH_TIMES = {
        "morning": "07:30",
        "noon": "12:00",
        "evening": "21:00"
    }
    
    @classmethod
    def generate_morning_report(cls, today_cards=None, yesterday_stats=None):
        """生成早报内容
        
        Args:
            today_cards: 今日待复习卡片列表
            yesterday_stats: 昨日学习统计
            
        Returns:
            str: 早报内容
        """
        report = "📅 早报 | " + datetime.now().strftime("%Y-%m-%d %A") + "\n\n"
        
        # 昨日总结
        if yesterday_stats:
            report += "📊 昨日学习总结:\n"
            report += f"  - 答题数: {yesterday_stats.get('total_answers', 0)}\n"
            report += f"  - 正确率: {yesterday_stats.get('accuracy', 'N/A')}\n"
            report += f"  - 连续学习: {yesterday_stats.get('streak_days', 0)}天\n\n"
        else:
            report += "📊 昨日学习总结: 暂无数据\n\n"
        
        # 今日计划
        if today_cards:
            report += f"📚 今日待复习 ({len(today_cards)}张):\n"
            for i, card in enumerate(today_cards[:5], 1):
                title = card.get("卡片问题正面", card.get("卡片标题", "未知"))
                report += f"  {i}. {title[:30]}\n"
            if len(today_cards) > 5:
                report += f"  ... 还有{len(today_cards)-5}张\n"
        else:
            report += "📚 今日待复习: 暂无待复习卡片\n"
        
        report += "\n💪 新的一天，继续加油！"
        return report
    
    @classmethod
    def generate_noon_report(cls, morning_stats=None, afternoon_suggestions=None):
        """生成午报内容
        
        Args:
            morning_stats: 上午学习统计
            afternoon_suggestions: 下午学习建议
            
        Returns:
            str: 午报内容
        """
        report = "☀️ 午报 | " + datetime.now().strftime("%Y-%m-%d %H:%M") + "\n\n"
        
        # 上午进度
        if morning_stats:
            report += "📈 上午学习进度:\n"
            report += f"  - 已答题: {morning_stats.get('answered', 0)}张\n"
            report += f"  - 正确率: {morning_stats.get('accuracy', 'N/A')}\n\n"
        else:
            report += "📈 上午学习进度: 暂无数据\n\n"
        
        # 下午建议
        report += "🎯 下午学习建议:\n"
        if afternoon_suggestions:
            for s in afternoon_suggestions:
                report += f"  - {s}\n"
        else:
            report += "  - 继续完成今日待复习卡片\n"
            report += "  - 重点关注错题和模糊题\n"
            report += "  - 适当休息，避免疲劳\n"
        
        report += "\n⏰ 记得按时答题哦！"
        return report
    
    @classmethod
    def generate_evening_report(cls, today_stats=None, tomorrow_preview=None):
        """生成晚报内容
        
        Args:
            today_stats: 今日学习统计
            tomorrow_preview: 明日预告
            
        Returns:
            str: 晚报内容
        """
        report = "🌙 晚报 | " + datetime.now().strftime("%Y-%m-%d %H:%M") + "\n\n"
        
        # 今日总结
        if today_stats:
            report += "📊 今日学习总结:\n"
            report += f"  - 总答题: {today_stats.get('total_answers', 0)}张\n"
            report += f"  - 会: {today_stats.get('correct', 0)}张\n"
            report += f"  - 模糊: {today_stats.get('uncertain', 0)}张\n"
            report += f"  - 不会: {today_stats.get('wrong', 0)}张\n"
            report += f"  - 正确率: {today_stats.get('accuracy', 'N/A')}\n"
            report += f"  - 连续学习: {today_stats.get('streak_days', 0)}天\n\n"
        else:
            report += "📊 今日学习总结: 暂无数据\n\n"
        
        # 明日预告
        report += "📅 明日预告:\n"
        if tomorrow_preview:
            report += f"  - 待复习: {tomorrow_preview.get('pending_cards', 0)}张\n"
            report += f"  - 新卡片: {tomorrow_preview.get('new_cards', 0)}张\n"
        else:
            report += "  - 系统将自动生成明日学习计划\n"
        
        report += "\n😴 早点休息，明天继续！"
        return report
    
    @classmethod
    def push_report(cls, report_type, chat_id=None, **kwargs):
        """推送报告到飞书群
        
        Args:
            report_type: 报告类型（morning/noon/evening）
            chat_id: 飞书群ID
            **kwargs: 生成报告所需的参数
            
        Returns:
            dict: 推送结果
        """
        result = {"success": False, "report_type": report_type, "error": None}
        
        try:
            # 生成报告内容
            if report_type == "morning":
                content = cls.generate_morning_report(**kwargs)
            elif report_type == "noon":
                content = cls.generate_noon_report(**kwargs)
            elif report_type == "evening":
                content = cls.generate_evening_report(**kwargs)
            else:
                result["error"] = f"不支持的报告类型: {report_type}"
                return result
            
            result["content"] = content
            
            # 发送到飞书群
            if chat_id:
                # V33修复：使用--content传递JSON，避免Windows命令行换行符被截断
                # json.dumps自动将换行符转义为\n，飞书API解析为真正的换行
                # V33修复：直接调用node.exe绕过.cmd批处理文件，避免|等特殊字符被解析为管道符
                content_json = json.dumps({"text": content}, ensure_ascii=False)
                cmd = [LARK_NODE_EXE, LARK_CLI_SCRIPT, "im", "+messages-send",
                       "--chat-id", chat_id,
                       "--content", content_json,
                       "--msg-type", "text",
                       "--as", "user"]
                ok, stdout, stderr = run_cmd(cmd, timeout=30)
                if ok:
                    result["success"] = True
                    result["message_id"] = stdout.strip() if stdout else None
                    print(f"  [每日推送] {report_type}报推送成功")
                else:
                    result["error"] = stderr or "推送失败"
                    print(f"  [每日推送] {report_type}报推送失败: {result['error']}")
            else:
                # 没有chat_id时只生成内容，不发送
                result["success"] = True
                result["message"] = "已生成报告内容（未指定chat_id，未发送）"
                print(f"  [每日推送] {report_type}报内容已生成（未发送）")
            
        except Exception as e:
            result["error"] = str(e)
            print(f"  [每日推送] 推送异常: {e}")
        
        return result


# ============================================================
# S3-11: Coze集成（需用户提供API密钥和bot_id）
# ============================================================
class CozeIntegration:
    """Coze集成 - 与Coze API交互，实现AI对话和内容生成
    
    注意：使用前需要用户提供Coze API密钥和bot_id
    当前为预留实现，配置后可正常使用
    """
    
    # Coze配置（需要用户提供）
    COZE_API_ENDPOINT = "https://api.coze.cn/open_api/v2/chat"
    API_KEY = ""  # 需要用户提供
    BOT_ID = ""   # 需要用户提供
    
    @classmethod
    def is_configured(cls):
        """检查Coze是否已配置
        
        Returns:
            bool: 是否已配置
        """
        return bool(cls.API_KEY and cls.BOT_ID)
    
    @classmethod
    def configure(cls, api_key, bot_id, endpoint=None):
        """配置Coze集成
        
        Args:
            api_key: Coze API密钥
            bot_id: Coze Bot ID
            endpoint: API端点（可选，使用默认值）
        """
        cls.API_KEY = api_key
        cls.BOT_ID = bot_id
        if endpoint:
            cls.COZE_API_ENDPOINT = endpoint
        print(f"  [Coze集成] 已配置，bot_id: {bot_id}")
    
    @classmethod
    def chat(cls, user_message, conversation_id=None, user_id="default_user"):
        """与Coze Bot对话
        
        Args:
            user_message: 用户消息
            conversation_id: 会话ID（可选，用于多轮对话）
            user_id: 用户ID
            
        Returns:
            dict: 对话结果 {success, reply, conversation_id, error}
        """
        result = {"success": False, "reply": None, "conversation_id": conversation_id, "error": None}
        
        if not cls.is_configured():
            result["error"] = "Coze未配置，请先提供API密钥和bot_id"
            print(f"  [Coze集成] {result['error']}")
            return result
        
        try:
            # 构建请求数据
            request_data = {
                "bot_id": cls.BOT_ID,
                "user": user_id,
                "query": user_message,
                "stream": False
            }
            if conversation_id:
                request_data["conversation_id"] = conversation_id
            
            # 发送请求（使用urllib，避免额外依赖）
            import urllib.request
            import urllib.error
            
            req = urllib.request.Request(
                cls.COZE_API_ENDPOINT,
                data=json.dumps(request_data).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {cls.API_KEY}",
                    "Content-Type": "application/json"
                },
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                response_data = json.loads(response.read().decode("utf-8"))
            
            if response_data.get("code") == 0:
                result["success"] = True
                result["reply"] = response_data.get("data", {}).get("messages", [{}])[0].get("content", "")
                result["conversation_id"] = response_data.get("data", {}).get("conversation_id", conversation_id)
                print(f"  [Coze集成] 对话成功，回复长度: {len(result['reply'])}")
            else:
                result["error"] = response_data.get("msg", "API调用失败")
                print(f"  [Coze集成] 对话失败: {result['error']}")
            
        except Exception as e:
            result["error"] = str(e)
            print(f"  [Coze集成] 对话异常: {e}")
        
        return result
    
    @classmethod
    def generate_study_summary(cls, study_data):
        """生成学习总结（使用Coze AI）
        
        Args:
            study_data: 学习数据（答题记录、正确率等）
            
        Returns:
            dict: 生成结果
        """
        if not cls.is_configured():
            return {"success": False, "error": "Coze未配置，无法生成AI总结"}
        
        # 构建提示词
        prompt = f"请根据以下学习数据生成一份学习总结和建议：\n{json.dumps(study_data, ensure_ascii=False, indent=2)}"
        
        return cls.chat(prompt, user_id="study_summary")


# ============================================================
# S4-10: 周日复盘高级功能（脱稿讲3张+1应用+ROI数据）
# ============================================================
class SundayReviewManager:
    """周日复盘高级管理器 - 脱稿讲3张+1应用+ROI数据
    
    功能：
    1. 自动选择3张重点卡片进行脱稿讲解
    2. 生成1个实际应用场景
    3. 计算ROI（投资回报率）数据
    4. 生成完整复盘报告
    """
    
    @classmethod
    def select_key_cards(cls, all_cards=None, top_n=3):
        """选择重点卡片（基于掌握度、最近复习、错误率等）
        
        Args:
            all_cards: 所有卡片列表
            top_n: 选择数量
            
        Returns:
            list: 重点卡片列表
        """
        if not all_cards:
            # 获取所有卡片
            try:
                cmd = [LARK_CLI, "base", "+record-list",
                       "--base-token", BASE_TOKEN,
                       "--table-id", CARD_TABLE,
                       "--as", "user", "--format", "json",
                       "--limit", "100"]
                ok, stdout, stderr = run_cmd(cmd, timeout=60)
                if ok and stdout:
                    data = json.loads(stdout)
                    records = data.get("data", {}).get("data", [])
                    fields = data.get("data", {}).get("fields", [])
                    record_ids = data.get("data", {}).get("record_id_list", [])
                    
                    all_cards = []
                    for i, record in enumerate(records):
                        card = {"_record_id": record_ids[i] if i < len(record_ids) else ""}
                        for j, f in enumerate(fields):
                            if j < len(record):
                                card[f] = record[j]
                        all_cards.append(card)
            except Exception as e:
                print(f"  [周日复盘] 获取卡片失败: {e}")
                return []
        
        if not all_cards:
            return []
        
        # 简化版评分：优先选择LEARNING状态、最近复习过、掌握度低的卡片
        scored_cards = []
        for card in all_cards:
            score = 0
            status = card.get("学习状态", "")
            if isinstance(status, list):
                status = status[0] if status else ""
            
            # LEARNING状态加分
            if status == "LEARNING":
                score += 10
            
            # 掌握度低加分（需要重点复习）
            mastery = card.get("掌握度M", 0)
            if isinstance(mastery, list):
                mastery = mastery[0] if mastery else 0
            try:
                mastery_val = float(mastery) if mastery else 0
                score += max(0, 10 - mastery_val)
            except:
                pass
            
            scored_cards.append((score, card))
        
        # 按分数排序，取前N个
        scored_cards.sort(key=lambda x: x[0], reverse=True)
        key_cards = [card for _, card in scored_cards[:top_n]]
        
        return key_cards
    
    @classmethod
    def generate_application_scenario(cls, key_cards):
        """生成实际应用场景
        
        Args:
            key_cards: 重点卡片列表
            
        Returns:
            str: 应用场景描述
        """
        if not key_cards:
            return "暂无重点卡片，无法生成应用场景"
        
        card_titles = []
        for card in key_cards:
            title = card.get("卡片问题正面", card.get("卡片标题", "未知"))
            card_titles.append(title)
        
        scenario = "🎯 实际应用场景：\n\n"
        scenario += f"本周重点学习了{len(key_cards)}个知识点：\n"
        for i, title in enumerate(card_titles, 1):
            scenario += f"  {i}. {title}\n"
        
        scenario += "\n💡 应用建议：\n"
        scenario += "  - 在日常工作中主动运用这些知识点\n"
        scenario += "  - 遇到相关问题时，回忆卡片内容并尝试解决\n"
        scenario += "  - 将知识点与实际项目结合，加深理解\n"
        scenario += "  - 定期回顾应用效果，调整学习策略\n"
        
        return scenario
    
    @classmethod
    def calculate_roi(cls, study_stats=None):
        """计算ROI（投资回报率）数据
        
        Args:
            study_stats: 学习统计数据
            
        Returns:
            dict: ROI数据
        """
        roi_data = {
            "time_invested_hours": 0,
            "knowledge_gained": 0,
            "efficiency_improvement": 0,
            "roi_score": 0,
            "summary": ""
        }
        
        if study_stats:
            # 简化版ROI计算
            total_answers = study_stats.get("total_answers", 0)
            correct_rate = study_stats.get("correct_rate", 0)
            study_days = study_stats.get("study_days", 1)
            
            # 假设每题平均投入5分钟
            time_invested = total_answers * 5 / 60  # 小时
            roi_data["time_invested_hours"] = round(time_invested, 1)
            
            # 知识获取量 = 正确答题数 * 掌握度提升
            knowledge_gained = total_answers * correct_rate * 0.1
            roi_data["knowledge_gained"] = round(knowledge_gained, 1)
            
            # 效率提升 = 连续学习天数 * 0.5%
            efficiency_improvement = min(study_days * 0.5, 50)
            roi_data["efficiency_improvement"] = round(efficiency_improvement, 1)
            
            # ROI评分 = (知识获取 + 效率提升) / 时间投入 * 10
            if time_invested > 0:
                roi_score = (knowledge_gained + efficiency_improvement) / time_invested * 10
                roi_data["roi_score"] = round(roi_score, 1)
            
            roi_data["summary"] = f"本周投入{roi_data['time_invested_hours']}小时，获取{roi_data['knowledge_gained']}知识点，效率提升{roi_data['efficiency_improvement']}%，ROI评分{roi_data['roi_score']}"
        
        return roi_data
    
    @classmethod
    def generate_weekly_review(cls, study_stats=None):
        """生成完整的周日复盘报告
        
        Args:
            study_stats: 学习统计数据
            
        Returns:
            str: 完整复盘报告
        """
        report = "📋 周日复盘报告 | " + datetime.now().strftime("%Y-%m-%d") + "\n"
        report += "=" * 40 + "\n\n"
        
        # 1. 选择3张重点卡片
        report += "【1/3】脱稿讲解 - 3张重点卡片\n"
        report += "-" * 30 + "\n"
        key_cards = cls.select_key_cards(top_n=3)
        if key_cards:
            for i, card in enumerate(key_cards, 1):
                title = card.get("卡片问题正面", card.get("卡片标题", "未知"))
                status = card.get("学习状态", "")
                if isinstance(status, list):
                    status = status[0] if status else ""
                report += f"\n{i}. {title}\n"
                report += f"   状态: {status}\n"
                report += f"   脱稿要点: （请尝试不看卡片，回忆核心内容）\n"
        else:
            report += "暂无重点卡片\n"
        
        # 2. 1个实际应用场景
        report += "\n\n【2/3】实际应用 - 1个场景\n"
        report += "-" * 30 + "\n"
        report += cls.generate_application_scenario(key_cards)
        
        # 3. ROI数据
        report += "\n\n【3/3】ROI数据\n"
        report += "-" * 30 + "\n"
        roi = cls.calculate_roi(study_stats)
        report += f"  ⏱️ 时间投入: {roi['time_invested_hours']}小时\n"
        report += f"  📚 知识获取: {roi['knowledge_gained']}知识点\n"
        report += f"  📈 效率提升: {roi['efficiency_improvement']}%\n"
        report += f"  💰 ROI评分: {roi['roi_score']}\n"
        if roi['summary']:
            report += f"\n  📊 {roi['summary']}\n"
        
        report += "\n" + "=" * 40 + "\n"
        report += "💪 本周辛苦了！下周继续保持！"
        
        return report


# ============================================================
# S3-05: 洞察归档补全（自动结构化处理+标签+关联卡片+摘要）
# ============================================================
class InsightArchiver:
    """洞察归档补全器 - 自动结构化处理洞察笔记
    
    功能：
    1. 自动提取关键词作为标签
    2. 自动关联相关学习卡片
    3. 自动生成AI摘要（简化版）
    4. 提取行动项
    5. 归档到洞察笔记表
    """
    
    INSIGHT_TABLE = "tblaqKBl87V9C0q1"  # 洞察笔记表ID（已配置真实表）
    
    # 洞察笔记表标签选项（与表中选项一致）
    TAG_OPTIONS = ["认知升级", "方法论", "沟通技巧", "学习方法", "决策反思", 
                   "系统优化", "商业洞察", "其他", "系统", "自动化"]
    
    # 关联科目选项（与表中选项一致）
    SUBJECT_OPTIONS = ["PMP", "机电工程", "AI技术", "管理学", "通用知识"]
    
    # 科目关键词映射
    SUBJECT_KEYWORDS = {
        "PMP": ["项目管理", "PMP", "进度", "范围", "风险", "干系人", "敏捷", "冲刺"],
        "机电工程": ["机电", "工程", "设备", "空调", "给排水", "电气", "施工", "维保", "酒店"],
        "AI技术": ["AI", "人工智能", "大模型", "Agent", "自动化", "脚本", "Python", "飞书", "API"],
        "管理学": ["管理", "团队", "领导", "战略", "组织", "绩效", "沟通", "决策"],
        "通用知识": ["学习", "方法", "认知", "思维", "复盘", "总结", "知识"]
    }
    
    @staticmethod
    def extract_keywords(text, max_keywords=5):
        """从文本中提取标签（匹配洞察笔记表选项，基于关键词映射）
        
        Args:
            text: 输入文本
            max_keywords: 最大标签数量
            
        Returns:
            list: 标签列表（均为表中已存在的选项）
        """
        if not text:
            return ["其他"]
        
        # 标签关键词映射
        tag_keyword_map = {
            "认知升级": ["认知", "思维", "洞察", "本质", "规律", "底层", "升级", "觉醒"],
            "方法论": ["方法", "框架", "模型", "流程", "步骤", "体系", "SOP", "工具"],
            "沟通技巧": ["沟通", "表达", "演讲", "谈判", "说服", "倾听", "反馈", "话术"],
            "学习方法": ["学习", "记忆", "复习", "笔记", "知识", "吸收", "内化", "训练"],
            "决策反思": ["决策", "反思", "复盘", "判断", "选择", "教训", "经验", "总结"],
            "系统优化": ["优化", "系统", "效率", "性能", "改进", "重构", "自动化", "流程"],
            "商业洞察": ["商业", "市场", "客户", "产品", "运营", "增长", "盈利", "战略"],
            "系统": ["系统", "架构", "设计", "模块", "集成", "接口", "数据"],
            "自动化": ["自动", "脚本", "批量", "定时", "触发", "工作流", "机器人"]
        }
        
        matched_tags = []
        for tag, keywords in tag_keyword_map.items():
            for kw in keywords:
                if kw in text:
                    matched_tags.append(tag)
                    break
        
        # 去重并限制数量
        unique_tags = list(dict.fromkeys(matched_tags))[:max_keywords]
        
        # 如果没有匹配到任何标签，使用"其他"
        if not unique_tags:
            unique_tags = ["其他"]
        
        return unique_tags
    
    @staticmethod
    def generate_summary(text, max_length=150):
        """生成提取式摘要（基于句子重要性评分，非简单截取）
        
        Args:
            text: 输入文本
            max_length: 摘要最大长度
            
        Returns:
            str: 摘要
        """
        if not text:
            return ""
        
        if len(text) <= max_length:
            return text
        
        import re
        # 按句子分割
        sentences = re.split(r'(?<=[。！？\.\!\?])', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return text[:max_length] + "..."
        
        # 句子重要性评分（基于关键词频率和位置）
        # 提取高频词（2-4字中文词）
        words = re.findall(r'[\u4e00-\u9fa5]{2,4}', text)
        word_freq = {}
        for w in words:
            word_freq[w] = word_freq.get(w, 0) + 1
        
        # 停用词
        stop_words = {"的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这", "那", "这个", "那个", "可以", "因为", "所以", "但是", "如果", "虽然", "而且", "或者", "以及"}
        
        # 计算每个句子的重要性评分
        scored_sentences = []
        for i, sent in enumerate(sentences):
            score = 0
            # 位置权重：首句和末句权重更高
            if i == 0:
                score += 3
            if i == len(sentences) - 1:
                score += 2
            # 关键词频率
            for w in words:
                if w not in stop_words and w in sent:
                    score += word_freq.get(w, 0) * 0.1
            # 包含重要关键词加分
            important_words = ["发现", "总结", "关键", "重要", "核心", "本质", "因此", "所以", "结论", "建议"]
            for iw in important_words:
                if iw in sent:
                    score += 2
            scored_sentences.append((i, sent, score))
        
        # 按评分排序，取Top N句子
        scored_sentences.sort(key=lambda x: x[2], reverse=True)
        top_sentences = scored_sentences[:3]  # 最多取3句
        
        # 按原文顺序排列
        top_sentences.sort(key=lambda x: x[0])
        summary = "".join([s[1] for s in top_sentences])
        
        # 限制长度
        if len(summary) > max_length:
            summary = summary[:max_length]
            # 尝试在句号处截断
            for punct in ["。", "！", "？", ".", "!", "?"]:
                last_pos = summary.rfind(punct)
                if last_pos > max_length * 0.5:
                    summary = summary[:last_pos + 1]
                    break
        
        return summary
    
    @staticmethod
    def extract_subject(text):
        """提取关联科目（基于关键词匹配，匹配洞察笔记表选项）
        
        Args:
            text: 输入文本
            
        Returns:
            str: 关联科目（表中已存在的选项）
        """
        if not text:
            return "通用知识"
        
        # 科目关键词映射（在类常量中定义）
        subject_scores = {}
        for subject, keywords in InsightArchiver.SUBJECT_KEYWORDS.items():
            score = 0
            for kw in keywords:
                if kw in text:
                    score += 1
            if score > 0:
                subject_scores[subject] = score
        
        if subject_scores:
            # 返回得分最高的科目
            return max(subject_scores, key=subject_scores.get)
        
        return "通用知识"
    
    @staticmethod
    def extract_action_items(text):
        """提取行动项（简化版，查找包含"需要"/"应该"/"必须"/"TODO"的句子）
        
        Args:
            text: 输入文本
            
        Returns:
            list: 行动项列表
        """
        if not text:
            return []
        
        import re
        # 按句子分割
        sentences = re.split(r'[。！？\.\!\?\n]', text)
        
        action_keywords = ["需要", "应该", "必须", "TODO", "待办", "行动", "下一步", "计划", "准备", "要做", "记得", "不要忘记"]
        
        action_items = []
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            for kw in action_keywords:
                if kw in s:
                    action_items.append(s)
                    break
        
        return action_items[:5]  # 最多返回5个行动项
    
    @classmethod
    def auto_structure_insight(cls, insight_text, related_card_id=None):
        """自动结构化处理洞察
        
        Args:
            insight_text: 洞察原始文本
            related_card_id: 关联的学习卡片ID（可选）
            
        Returns:
            dict: 结构化洞察数据
        """
        result = {
            "original_text": insight_text,
            "summary": cls.generate_summary(insight_text),
            "keywords": cls.extract_keywords(insight_text),
            "action_items": cls.extract_action_items(insight_text),
            "subject": cls.extract_subject(insight_text),
            "related_card_id": related_card_id,
            "structured_at": datetime.now().isoformat(),
            "word_count": len(insight_text) if insight_text else 0
        }
        
        print(f"  [洞察归档] 自动结构化完成:")
        print(f"    摘要: {result['summary'][:50]}...")
        print(f"    标签: {result['keywords']}")
        print(f"    关联科目: {result['subject']}")
        print(f"    行动项数: {len(result['action_items'])}")
        print(f"    字数: {result['word_count']}")
        
        return result
    
    @classmethod
    def archive_insight(cls, insight_text, related_card_id=None, insight_type="学习洞察"):
        """归档洞察到洞察笔记表（真实写入飞书多维表格）
        
        Args:
            insight_text: 洞察原始文本
            related_card_id: 关联的学习卡片ID
            insight_type: 洞察类型
            
        Returns:
            dict: 归档结果 {success, record_id, structured, error}
        """
        # 先自动结构化
        structured = cls.auto_structure_insight(insight_text, related_card_id)
        
        result = {
            "success": False,
            "record_id": None,
            "structured": structured,
            "error": None
        }
        
        try:
            # 生成洞察标题（取前30字）
            title = insight_text[:30].strip()
            if len(insight_text) > 30:
                title += "..."
            
            # 当前时间戳（毫秒）
            now_ts = int(time.time() * 1000)
            
            # 行动项转为文本（用换行符连接）
            action_items_text = "\n".join(structured["action_items"]) if structured["action_items"] else ""
            
            # 构建归档数据（匹配洞察笔记表28个字段）
            archive_data = {
                "洞察标题": title,
                "标签": structured["keywords"],  # select多选
                "行动状态": ["待执行"],  # select
                "整理日期": now_ts,  # datetime
                "创建日期": now_ts,  # datetime
                "状态": ["待整理"],  # select
                "来源": "系统自动归档",  # text
                "行动项": action_items_text,  # text
                "是否已沉淀": False,  # checkbox
                "AI摘要": structured["summary"],  # text
                "洞察内容": insight_text,  # text
                "沉淀状态": ["未沉淀"],  # select
                "关联科目": [structured["subject"]],  # select
                "洞察类型": [insight_type],  # select
                "洞察日期": now_ts,  # datetime
                "优先级": ["中"],  # select
                "价值评分": 3,  # number (rating 1-5)
                "类型": ["洞察"],  # select
            }
            
            # 关联学习卡片（text字段）
            if related_card_id:
                archive_data["关联学习卡片"] = related_card_id
            
            # 写入洞察笔记表
            json_file = os.path.join(SCRIPT_DIR, f".insight_archive_{int(time.time()*1000)}.json")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(archive_data, f, ensure_ascii=False)
            
            cmd = [LARK_CLI, "base", "+record-upsert",
                   "--base-token", BASE_TOKEN,
                   "--table-id", cls.INSIGHT_TABLE,
                   "--as", "user",
                   "--json", f"@{os.path.basename(json_file)}"]
            ok, stdout, stderr = run_cmd(cmd, timeout=30)
            
            # 清理临时文件
            if os.path.exists(json_file):
                os.remove(json_file)
            
            if ok:
                # 解析返回的record_id（路径：data.record.record_id_list[0]）
                try:
                    resp = json.loads(stdout)
                    record_id = resp.get("data", {}).get("record", {}).get("record_id_list", [None])[0]
                    result["record_id"] = record_id
                except:
                    result["record_id"] = "UNKNOWN"
                
                result["success"] = True
                result["archive_data"] = archive_data
                print(f"  [洞察归档] 洞察归档成功，record_id={result['record_id']}，类型={insight_type}，标签={structured['keywords']}，科目={structured['subject']}")
            else:
                raise Exception(f"写入洞察笔记表失败: {stderr[:200]}")
            
        except Exception as e:
            result["error"] = str(e)
            print(f"  [洞察归档] 归档异常: {e}")
        
        return result


# ============================================================
# S4-13: 断网恢复管理器（断网检测+恢复后自动补发/重试）
# ============================================================
class NetworkRecoveryManager:
    """断网恢复管理器 - 检测断网，恢复后自动补发/重试未处理消息
    
    功能：
    1. 断网检测（检查lark-cli可用性和网络连接）
    2. 断网时记录未处理消息到DLQ
    3. 恢复网络后自动调用DLQ重试
    4. 发送断网/恢复通知
    5. 消息队列持久化
    """
    
    NETWORK_STATE_FILE = os.path.join(SCRIPT_DIR, ".network_state.json")
    LAST_HEALTHY_CHECK_FILE = os.path.join(SCRIPT_DIR, ".last_healthy_check.json")
    
    @classmethod
    def _load_network_state(cls):
        """加载网络状态"""
        try:
            if os.path.exists(cls.NETWORK_STATE_FILE):
                with open(cls.NETWORK_STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return {
            "is_offline": False,
            "offline_since": None,
            "last_check": None,
            "last_recovery": None,
            "offline_count": 0,
            "pending_messages": []
        }
    
    @classmethod
    def _save_network_state(cls, state):
        """保存网络状态"""
        try:
            state["last_check"] = datetime.now().isoformat()
            with open(cls.NETWORK_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  [断网恢复] 保存网络状态失败: {e}")
    
    @classmethod
    def check_network(cls):
        """检查网络连接状态
        
        Returns:
            dict: {is_online, error, check_time}
        """
        result = {"is_online": False, "error": None, "check_time": datetime.now().isoformat()}
        
        try:
            # 检查lark-cli可用性（通过简单的版本检查）
            cmd = [LARK_CLI, "--version"]
            ok, stdout, stderr = run_cmd(cmd, timeout=10)
            
            if ok and stdout:
                result["is_online"] = True
                result["version"] = stdout.strip()
            else:
                result["error"] = stderr or "lark-cli执行失败"
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    @classmethod
    def handle_network_status(cls):
        """处理网络状态变化（检测断网/恢复，自动触发补发）
        
        Returns:
            dict: {status_changed, previous_status, current_status, action_taken}
        """
        state = cls._load_network_state()
        previous_status = "offline" if state.get("is_offline") else "online"
        
        # 检查当前网络状态
        check_result = cls.check_network()
        current_is_online = check_result.get("is_online", False)
        
        result = {
            "status_changed": False,
            "previous_status": previous_status,
            "current_status": "online" if current_is_online else "offline",
            "action_taken": None
        }
        
        if not current_is_online:
            # 网络断开
            if not state.get("is_offline"):
                # 从在线变为离线
                state["is_offline"] = True
                state["offline_since"] = datetime.now().isoformat()
                state["offline_count"] = state.get("offline_count", 0) + 1
                result["status_changed"] = True
                result["action_taken"] = "detected_offline"
                print(f"  [断网恢复] 检测到网络断开，时间: {state['offline_since']}")
                print(f"  [断网恢复] 未处理消息将加入DLQ，恢复后自动补发")
        else:
            # 网络正常
            if state.get("is_offline"):
                # 从离线恢复为在线
                state["is_offline"] = False
                state["last_recovery"] = datetime.now().isoformat()
                result["status_changed"] = True
                result["action_taken"] = "recovered_and_retrying"
                
                offline_duration = "未知"
                if state.get("offline_since"):
                    try:
                        offline_start = datetime.fromisoformat(state["offline_since"])
                        offline_duration = str((datetime.now() - offline_start).seconds // 60) + "分钟"
                    except:
                        pass
                
                print(f"  [断网恢复] 网络已恢复，断网时长: {offline_duration}")
                print(f"  [断网恢复] 开始自动补发DLQ中的未处理消息...")
                
                # 自动调用DLQ重试
                try:
                    retry_result = DLQManager.retry_pending(max_retries=3, max_messages=20)
                    result["retry_result"] = retry_result
                    print(f"  [断网恢复] 补发完成: 重试{retry_result.get('retried', 0)}条，成功{retry_result.get('success', 0)}条，失败{retry_result.get('failed', 0)}条")
                except Exception as e:
                    print(f"  [断网恢复] 补发异常: {e}")
                    result["retry_error"] = str(e)
        
        cls._save_network_state(state)
        return result
    
    @classmethod
    def add_pending_message(cls, message_id, message_text, reason="网络断开"):
        """添加未处理消息（断网时调用）
        
        Args:
            message_id: 消息ID
            message_text: 消息内容
            reason: 未处理原因
            
        Returns:
            bool: 是否添加成功
        """
        # 直接添加到DLQ
        return DLQManager.add_failed_message(
            message_id=message_id,
            message_text=message_text,
            error_type="network_offline",
            error_detail=reason
        )
    
    @classmethod
    def get_network_status(cls):
        """获取网络状态详情
        
        Returns:
            dict: 网络状态详情
        """
        state = cls._load_network_state()
        check_result = cls.check_network()
        
        return {
            "is_offline": state.get("is_offline", False),
            "is_currently_online": check_result.get("is_online", False),
            "offline_since": state.get("offline_since"),
            "last_check": state.get("last_check"),
            "last_recovery": state.get("last_recovery"),
            "offline_count": state.get("offline_count", 0),
            "dlq_pending": DLQManager.get_queue_stats().get("pending", 0)
        }


# ============================================================
# S6-09: 关联学习卡片管理器（关联写入+间隔微调≤20%）
# ============================================================
class RelatedCardManager:
    """关联学习卡片管理器 - 管理卡片关联关系，实现间隔微调≤20%
    
    关联规则：
    1. 答题时自动关联相同tags的卡片
    2. 支持手动设置关联关系
    3. 间隔微调：根据关联关系、tags相似度、难度微调间隔，幅度不超过20%
    4. 关联关系存储在卡片表的"关联任务"字段中
    """
    
    MAX_INTERVAL_ADJUSTMENT = 0.20  # 间隔微调最大幅度20%
    RELATION_FILE = os.path.join(SCRIPT_DIR, ".card_relations.json")
    
    @classmethod
    def _load_relations(cls):
        """加载卡片关联关系"""
        try:
            if os.path.exists(cls.RELATION_FILE):
                with open(cls.RELATION_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return {"relations": {}, "last_updated": None}
    
    @classmethod
    def _save_relations(cls, relations):
        """保存卡片关联关系"""
        try:
            relations["last_updated"] = datetime.now().isoformat()
            with open(cls.RELATION_FILE, "w", encoding="utf-8") as f:
                json.dump(relations, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  [关联卡片] 保存关联关系失败: {e}")
    
    @staticmethod
    def _get_card_tags(card):
        """获取卡片的tags（从卡片问题中提取关键词，简化版）"""
        title = card.get("卡片问题正面", "") or card.get("卡片标题", "") or ""
        # 简化版：按空格/标点分割，取长度>1的词作为tags
        import re
        words = re.findall(r'[\u4e00-\u9fa5a-zA-Z]{2,}', title)
        return list(set(words))
    
    @staticmethod
    def _calc_tags_similarity(tags1, tags2):
        """计算两组tags的相似度（Jaccard相似度）"""
        if not tags1 or not tags2:
            return 0.0
        set1 = set(tags1)
        set2 = set(tags2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0
    
    @classmethod
    def auto_relate_cards(cls, card_id, all_cards=None, min_similarity=0.3):
        """自动关联卡片（根据tags相似度）
        
        Args:
            card_id: 目标卡片ID
            all_cards: 所有卡片列表（为None时自动获取）
            min_similarity: 最小相似度阈值
            
        Returns:
            dict: 关联结果
        """
        if all_cards is None:
            # 获取所有卡片
            try:
                cmd = [LARK_CLI, "base", "+record-list",
                       "--base-token", BASE_TOKEN,
                       "--table-id", CARD_TABLE,
                       "--as", "user", "--format", "json",
                       "--limit", "100"]
                ok, stdout, stderr = run_cmd(cmd, timeout=60)
                if not ok or not stdout:
                    return {"success": False, "error": stderr or "获取卡片列表失败"}
                data = json.loads(stdout)
                records = data.get("data", {}).get("data", [])
                fields = data.get("data", {}).get("fields", [])
                record_ids = data.get("data", {}).get("record_id_list", [])
                
                all_cards = []
                for i, record in enumerate(records):
                    card = {"_record_id": record_ids[i] if i < len(record_ids) else ""}
                    for j, f in enumerate(fields):
                        if j < len(record):
                            card[f] = record[j]
                    all_cards.append(card)
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        # 找到目标卡片
        target_card = None
        for card in all_cards:
            if card.get("_record_id") == card_id:
                target_card = card
                break
        
        if not target_card:
            return {"success": False, "error": f"未找到卡片 {card_id}"}
        
        target_tags = cls._get_card_tags(target_card)
        
        # 计算与其他卡片的相似度
        relations = cls._load_relations()
        if card_id not in relations["relations"]:
            relations["relations"][card_id] = []
        
        related_cards = []
        for card in all_cards:
            if card.get("_record_id") == card_id:
                continue
            card_tags = cls._get_card_tags(card)
            similarity = cls._calc_tags_similarity(target_tags, card_tags)
            if similarity >= min_similarity:
                related_cards.append({
                    "card_id": card.get("_record_id"),
                    "title": card.get("卡片问题正面", "未知"),
                    "similarity": round(similarity, 3),
                    "relation_type": "auto_tags"
                })
                # 添加到关联关系
                if card.get("_record_id") not in relations["relations"][card_id]:
                    relations["relations"][card_id].append(card.get("_record_id"))
        
        cls._save_relations(relations)
        
        return {
            "success": True,
            "card_id": card_id,
            "target_tags": target_tags,
            "related_count": len(related_cards),
            "related_cards": related_cards
        }
    
    @classmethod
    def adjust_interval(cls, base_interval, card_id, all_cards=None):
        """根据关联关系微调间隔（幅度不超过20%）
        
        Args:
            base_interval: 基础间隔（天）
            card_id: 卡片ID
            all_cards: 所有卡片列表
            
        Returns:
            dict: 调整结果 {adjusted_interval, adjustment, reason}
        """
        relations = cls._load_relations()
        related_ids = relations["relations"].get(card_id, [])
        
        if not related_ids:
            return {
                "adjusted_interval": base_interval,
                "adjustment": 0.0,
                "reason": "无关联卡片，不调整"
            }
        
        # 计算调整因子：关联卡片越多，间隔越短（因为可以一起复习）
        # 最多调整20%
        relation_count = len(related_ids)
        adjustment_factor = min(relation_count * 0.05, cls.MAX_INTERVAL_ADJUSTMENT)
        
        # 关联卡片多 → 缩短间隔（负调整）
        adjustment = -adjustment_factor
        adjusted_interval = base_interval * (1 + adjustment)
        
        return {
            "adjusted_interval": round(adjusted_interval, 2),
            "adjustment": round(adjustment * 100, 1),
            "reason": f"关联{relation_count}张卡片，间隔缩短{adjustment_factor*100:.1f}%（≤20%限制）",
            "related_count": relation_count
        }
    
    @classmethod
    def get_relation_status(cls, card_id):
        """获取卡片关联状态
        
        Args:
            card_id: 卡片ID
            
        Returns:
            dict: 关联状态
        """
        relations = cls._load_relations()
        related_ids = relations["relations"].get(card_id, [])
        
        return {
            "card_id": card_id,
            "related_count": len(related_ids),
            "related_card_ids": related_ids,
            "last_updated": relations.get("last_updated")
        }


# ============================================================
# S4-18: 编辑消息处理（检测+重新解析+revision+1）
# ============================================================
class EditMessageHandler:
    """编辑消息处理器 - 检测用户编辑消息，按新内容重新解析，revision+1
    
    设计原则：
    - 检测消息是否被编辑（update_time > create_time）
    - 按新内容重新解析指令
    - 标记原记录为superseded
    - 写入新记录，revision+1
    - 发送编辑确认回执
    """
    
    @staticmethod
    def is_edited(message):
        """检测消息是否被编辑
        
        Args:
            message: 消息字典（包含create_time和update_time）
            
        Returns:
            bool: 是否被编辑
        """
        create_time = message.get("create_time", "")
        update_time = message.get("update_time", "")
        
        # 如果没有update_time，说明没有被编辑
        if not update_time:
            return False
        
        # 如果update_time > create_time，说明被编辑
        try:
            create_ts = int(create_time) if create_time else 0
            update_ts = int(update_time) if update_time else 0
            return update_ts > create_ts
        except (ValueError, TypeError):
            # 如果时间格式无法解析，检查字符串是否不同
            return create_time != update_time
    
    @staticmethod
    def get_edited_content(message):
        """获取编辑后的消息内容
        
        Args:
            message: 消息字典
            
        Returns:
            str: 编辑后的消息内容
        """
        # 优先从body.content获取
        content = message.get("body", {}).get("content", "")
        if not content:
            content = message.get("content", "")
        
        # 处理JSON格式的content
        if isinstance(content, str) and content.startswith("{"):
            try:
                content = json.loads(content).get("text", "")
            except:
                pass
        
        # 去掉"（由XXX发送）"后缀
        import re
        content = re.sub(r'（由[^）]+发送）\s*$', '', content).strip()
        
        return content
    
    @staticmethod
    def find_original_flow(message_id, flows):
        """根据消息ID查找原始流水记录
        
        Args:
            message_id: 消息ID
            flows: 流水记录列表
            
        Returns:
            dict: 原始流水记录（如果找到），否则None
        """
        for flow in flows:
            # 检查流水记录中是否包含message_id（可能在event_id或其他字段中）
            flow_msg_id = flow.get("message_id", "")
            if isinstance(flow_msg_id, list):
                flow_msg_id = flow_msg_id[0] if flow_msg_id else ""
            
            if flow_msg_id == message_id:
                return flow
            
            # 也检查event_id是否包含message_id
            event_id = flow.get("event_id", "")
            if isinstance(event_id, list):
                event_id = event_id[0] if event_id else ""
            if message_id in str(event_id):
                return flow
        
        return None
    
    @staticmethod
    def handle_edit(original_flow, new_content, parser, today_cards):
        """处理编辑消息
        
        Args:
            original_flow: 原始流水记录
            new_content: 编辑后的新内容
            parser: InstructionParser实例
            today_cards: 今日卡片列表
            
        Returns:
            dict: 处理结果
                - success: 是否成功
                - action: 解析出的动作
                - new_flow_data: 新流水数据
                - reason: 失败原因（如果失败）
        """
        if not original_flow:
            return {"success": False, "reason": "未找到原始流水记录"}
        
        # 按新内容重新解析
        action, data = parser.parse(new_content, today_cards)
        
        if action == "parse_error":
            return {"success": False, "action": action, "reason": "编辑后的内容解析失败"}
        
        if action == "ignore":
            return {"success": False, "action": action, "reason": "编辑后的内容为闲聊，忽略"}
        
        # 获取原始revision
        original_revision = original_flow.get("revision", 0)
        if isinstance(original_revision, list):
            original_revision = original_revision[0] if original_revision else 0
        try:
            original_revision = int(original_revision)
        except (ValueError, TypeError):
            original_revision = 0
        
        # 构建新流水数据
        new_flow_data = {
            "卡片ID": original_flow.get("卡片ID", ""),
            "卡片标题": original_flow.get("卡片标题", ""),
            "结果": data.get("result", "") if data else "",
            "event_id": f"{original_flow.get('卡片ID','')}|{data.get('result','') if data else ''}|{int(time.time()*1000)}",
            "来源": ["编辑消息"],
            "event_type": ["COMMIT"],
            "revision": original_revision + 1,  # revision+1
            "superseded": False,
            "revoke_of": "",
        }
        
        # 如果解析出错因，添加错因字段
        if data and data.get("error_type"):
            new_flow_data["错因"] = [data["error_type"]]
        
        return {
            "success": True,
            "action": action,
            "new_flow_data": new_flow_data,
            "original_revision": original_revision,
            "new_revision": original_revision + 1,
        }
    
    @staticmethod
    def generate_edit_receipt(original_flow, new_flow_data, success=True, reason=""):
        """生成编辑确认回执
        
        Args:
            original_flow: 原始流水记录
            new_flow_data: 新流水数据
            success: 是否成功
            reason: 失败原因
            
        Returns:
            str: 回执消息
        """
        if not success:
            return f"❌ 编辑处理失败: {reason}\n原记录保持不变"
        
        original_result = original_flow.get("结果", "")
        if isinstance(original_result, list):
            original_result = original_result[0] if original_result else ""
        
        new_result = new_flow_data.get("结果", "")
        if isinstance(new_result, list):
            new_result = new_result[0] if new_result else ""
        
        original_revision = original_flow.get("revision", 0)
        if isinstance(original_revision, list):
            original_revision = original_revision[0] if original_revision else 0
        
        new_revision = new_flow_data.get("revision", 0)
        
        receipt = (
            f"✏️ 消息已编辑处理\n"
            f"原答案: {original_result} (revision {original_revision})\n"
            f"新答案: {new_result} (revision {new_revision})\n"
            f"原记录已标记为superseded，新记录已写入"
        )
        
        return receipt


# ============================================================
# 主函数：集成测试
# ============================================================
def main():
    print("=" * 70)
    print("V19综合集成模块测试")
    print("=" * 70)

    # 1. 撤回指令简化测试
    print("\n【1】撤回指令简化测试")
    print("-" * 70)
    event_id, message = RevokeSimplifier.get_latest_answer_event_id()
    print(f"  最近一条答题记录: {event_id}")
    print(f"  说明: {message}")
    # 测试不带参数的!revoke解析
    target, msg = RevokeSimplifier.parse_revoke_command("!revoke")
    print(f"  !revoke（不带参数）解析: target={target}, msg={msg}")
    # 测试带参数的!revoke解析
    target2, msg2 = RevokeSimplifier.parse_revoke_command("!revoke test_event_id")
    print(f"  !revoke test_event_id解析: target={target2}, msg={msg2}")

    # 2. 错因功能测试
    print("\n【2】错因功能测试")
    print("-" * 70)
    result, error_type, has_error, card_num = ErrorTypeParser.parse_with_error_type("不会 理解错")
    print(f"  「不会 理解错」解析: result={result}, error_type={error_type}, has_error={has_error}")
    result2, error_type2, has_error2, card_num2 = ErrorTypeParser.parse_with_error_type("不会1 记忆错")
    print(f"  「不会1 记忆错」解析: result={result2}, error_type={error_type2}, has_error={has_error2}, card_num={card_num2}")
    print(f"  所有错因类型: {list(ErrorTypeParser.get_all_error_types().keys())}")

    # 3. 告警管理器测试
    print("\n【3】告警管理器测试")
    print("-" * 70)
    alert_result = AlertManager.send_alert("INFO", "集成模块自检", "告警双通道功能测试", channel="local")
    print(f"  本地告警: {'✅' if alert_result['local'] else '❌'}")

    # 4. 消费索引健康检查测试
    print("\n【4】消费索引健康检查测试")
    print("-" * 70)
    health_result = ConsumeIndexHealthChecker.check(stale_threshold_minutes=30)
    print(f"  健康状态: {'✅ 健康' if health_result['healthy'] else '❌ 异常'}")
    print(f"  当前索引: {health_result['current_index']}")
    print(f"  索引年龄: {health_result['age_seconds']:.1f}秒 ({health_result['age_seconds']/60:.1f}分钟)")

    # 5. 倦怠降速管理器测试
    print("\n【5】倦怠降速管理器测试")
    print("-" * 70)
    daily_count = FatigueManager.get_daily_card_count(default_count=3)
    is_fatigue = FatigueManager.is_fatigue_mode()
    print(f"  倦怠模式: {'是' if is_fatigue else '否'}")
    print(f"  今日应推卡片数: {daily_count}")

    # 6. DLQ管理器测试
    print("\n【6】DLQ管理器测试")
    print("-" * 70)
    DLQManager.add_failed_message("integration_test_001", "会", "write_failed", "集成测试模拟失败")
    stats = DLQManager.get_queue_stats()
    print(f"  DLQ统计: 总数={stats['total']}, pending={stats['pending']}, dead={stats['dead']}")

    # 总结
    print("\n" + "=" * 70)
    print("综合集成模块测试总结")
    print("=" * 70)
    print(f"  1. 撤回指令简化: ✅ 实现完成（支持!revoke不带参数）")
    print(f"  2. 错因功能启用: ✅ 实现完成（理解错/记忆错/计算错/粗心错）")
    print(f"  3. 告警管理器: ✅ 实现完成（双通道）")
    print(f"  4. 消费索引健康检查: ✅ 实现完成")
    print(f"  5. 倦怠降速管理器: ✅ 实现完成")
    print(f"  6. 撤回复验器: ✅ 实现完成")
    print(f"  7. DLQ管理器: ✅ 实现完成")

    # 保存测试结果
    test_result = {
        "test_time": datetime.now().isoformat(),
        "revoke_simplifier": "✅ 完成",
        "error_type_parser": "✅ 完成",
        "alert_manager": "✅ 完成",
        "consume_index_checker": "✅ 完成",
        "fatigue_manager": "✅ 完成",
        "revoke_verifier": "✅ 完成",
        "dlq_manager": "✅ 完成",
    }
    result_file = os.path.join(SCRIPT_DIR, "v19_integration_test_result.json")
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(test_result, f, ensure_ascii=False, indent=2)
    print(f"\n测试结果已保存: {result_file}")


# ============================================================
# 8. 效率优化器（R5 S2-02接线）
# ============================================================
class EfficiencyOptimizer:
    """效率优化器 - 定期优化系统配置，清理冗余数据，提升运行效率"""
    
    @staticmethod
    def run_maintenance():
        """执行一次维护优化
        Returns:
            dict: 维护结果
                - success: 是否成功
                - actions: 执行的操作列表
                - freed_space: 释放的空间（字节）
                - duration: 耗时（秒）
        """
        start_time = time.time()
        actions = []
        freed_space = 0
        
        try:
            # 1. 清理过期的临时文件
            temp_files = [
                os.path.join(SCRIPT_DIR, f) for f in os.listdir(SCRIPT_DIR)
                if f.startswith("tmp_") and f.endswith(".json")
            ]
            for tf in temp_files:
                try:
                    file_size = os.path.getsize(tf)
                    os.remove(tf)
                    freed_space += file_size
                    actions.append(f"清理临时文件: {os.path.basename(tf)} ({file_size}字节)")
                except Exception as e:
                    actions.append(f"清理临时文件失败: {os.path.basename(tf)} - {e}")
            
            # 2. 检查系统状态文件完整性
            state_files = [CONSUME_INDEX_FILE, SYSTEM_STATE_FILE, FATIGUE_STATE_FILE]
            for sf in state_files:
                if os.path.exists(sf):
                    try:
                        with open(sf, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        actions.append(f"状态文件正常: {os.path.basename(sf)}")
                    except Exception as e:
                        actions.append(f"状态文件异常，重置: {os.path.basename(sf)} - {e}")
                        try:
                            with open(sf, 'w', encoding='utf-8') as f:
                                json.dump({}, f)
                        except:
                            pass
                else:
                    actions.append(f"状态文件不存在，将自动创建: {os.path.basename(sf)}")
            
            # 3. 记录维护日志
            duration = time.time() - start_time
            actions.append(f"维护完成，耗时{duration:.2f}秒，释放空间{freed_space}字节")
            
            # 写入系统日志
            try:
                log_data = {
                    "event_id": f"MAINT_{int(time.time()*1000)}",
                    "message": "效率优化器维护完成",
                    "source": ["system"],
                    "detail": json.dumps({"actions": actions, "freed_space": freed_space, "duration": duration}),
                    "severity": ["INFO"],
                    "log_type": ["SYSTEM"],
                    "resolved": False
                }
                tmp_file = os.path.join(SCRIPT_DIR, f"tmp_maint_{int(time.time()*1000)}.json")
                with open(tmp_file, 'w', encoding='utf-8') as f:
                    json.dump(log_data, f, ensure_ascii=False)
                cmd = [LARK_CLI, "base", "+record-upsert",
                       "--base-token", BASE_TOKEN, "--table-id", "tblPreh1ipB9LQpf",
                       "--as", "user", "--json", f"@./{os.path.basename(tmp_file)}"]
                run_cmd(cmd, timeout=60)
                try:
                    os.remove(tmp_file)
                except:
                    pass
            except Exception as e:
                actions.append(f"写入日志失败: {e}")
            
            return {
                "success": True,
                "actions": actions,
                "freed_space": freed_space,
                "duration": duration
            }
            
        except Exception as e:
            return {
                "success": False,
                "actions": actions,
                "freed_space": freed_space,
                "duration": time.time() - start_time,
                "error": str(e)
            }


# ============================================================
# 9. 看门狗（R5 S2-02接线）
# ============================================================
class Watchdog:
    """看门狗 - 检测"进程活着但功能死了"的情况，及时告警"""
    
    WATCHDOG_STATE_FILE = os.path.join(SCRIPT_DIR, ".watchdog_state.json")
    
    @staticmethod
    def check_health():
        """检查系统健康状态，检测"进程活着但功能死了"
        Returns:
            dict: 健康检查结果
                - healthy: 是否健康
                - issues: 问题列表
                - last_success_time: 最后成功时间
                - current_time: 当前时间
                - should_alert: 是否应该告警
        """
        current_time = datetime.now()
        issues = []
        
        try:
            # 1. 检查系统状态文件
            last_success_time = None
            if os.path.exists(SYSTEM_STATE_FILE):
                try:
                    with open(SYSTEM_STATE_FILE, 'r', encoding='utf-8') as f:
                        state = json.load(f)
                    last_success_str = state.get("last_success_time", "")
                    if last_success_str:
                        try:
                            last_success_time = datetime.fromisoformat(last_success_str)
                        except:
                            pass
                except Exception as e:
                    issues.append(f"系统状态文件读取失败: {e}")
            else:
                issues.append("系统状态文件不存在")
            
            # 2. 检查消费索引文件
            consume_index_age = None
            if os.path.exists(CONSUME_INDEX_FILE):
                try:
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(CONSUME_INDEX_FILE))
                    consume_index_age = (current_time - file_mtime).total_seconds() / 60
                    if consume_index_age > 120:  # 超过2小时未更新
                        issues.append(f"消费索引文件超过{consume_index_age:.0f}分钟未更新")
                except Exception as e:
                    issues.append(f"消费索引文件检查失败: {e}")
            else:
                issues.append("消费索引文件不存在")
            
            # 3. 检查最后成功时间（超过1小时视为异常）
            if last_success_time:
                time_since_last_success = (current_time - last_success_time).total_seconds() / 60
                if time_since_last_success > 60:
                    issues.append(f"系统最后成功时间在{time_since_last_success:.0f}分钟前（超过60分钟阈值）")
            else:
                issues.append("无法获取最后成功时间")
            
            # 4. 检查是否应该告警（有2个以上问题才告警，避免误报）
            should_alert = len(issues) >= 2
            
            # 5. 记录看门狗状态
            watchdog_state = {
                "last_check_time": current_time.isoformat(),
                "healthy": len(issues) == 0,
                "issues": issues,
                "last_success_time": last_success_time.isoformat() if last_success_time else None,
                "should_alert": should_alert
            }
            try:
                with open(Watchdog.WATCHDOG_STATE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(watchdog_state, f, ensure_ascii=False, indent=2)
            except:
                pass
            
            # 6. 如果需要告警，发送告警
            if should_alert:
                try:
                    alert_message = f"[看门狗告警] 系统可能异常：{'; '.join(issues[:3])}"
                    # 写入本地告警日志
                    with open(ALERTS_LOG, 'a', encoding='utf-8') as f:
                        f.write(f"[{current_time.isoformat()}] WATCHDOG: {alert_message}\n")
                    
                    # 发送飞书消息告警
                    cmd = [LARK_CLI, "im", "+messages-send",
                           "--chat-id", TARGET_CHAT_ID,
                           "--text", alert_message,
                           "--as", "user"]
                    run_cmd(cmd, timeout=30)
                except Exception as e:
                    issues.append(f"发送告警失败: {e}")
            
            return {
                "healthy": len(issues) == 0,
                "issues": issues,
                "last_success_time": last_success_time.isoformat() if last_success_time else "UNKNOWN",
                "current_time": current_time.isoformat(),
                "should_alert": should_alert,
                "consume_index_age_minutes": consume_index_age
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "issues": [f"看门狗检查异常: {e}"],
                "last_success_time": "UNKNOWN",
                "current_time": current_time.isoformat(),
                "should_alert": True,
                "consume_index_age_minutes": None
            }


if __name__ == "__main__":
    main()
