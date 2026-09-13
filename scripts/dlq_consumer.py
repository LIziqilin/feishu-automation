#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
dlq_consumer.py
死信队列消费者 - 处理写入失败的消息，自动重试
用法：
  python dlq_consumer.py           # 处理待重试消息
  python dlq_consumer.py --status  # 查看队列状态

【日志规范】
- 日志格式：[时间戳] [级别] [模块] 消息
- 日志级别：DEBUG/INFO/WARN/ERROR/CRITICAL
- 所有错误记录完整的错误堆栈（traceback）
- 日志中不包含敏感信息（密钥、令牌等）
"""
from v19_integration import BASE_TOKEN
import json
import os
import sys
import subprocess
import argparse
import traceback
from datetime import datetime

# ============================================================
# 日志工具函数
# ============================================================

def log(level, module, message):
    """统一日志输出
    格式：[时间戳] [级别] [模块] 消息
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] [{module}] {message}")

def log_error(module, message, exception=None):
    """错误日志，包含完整错误堆栈"""
    log("ERROR", module, message)
    if exception:
        log("ERROR", module, f"异常类型: {type(exception).__name__}")
        log("ERROR", module, f"异常信息: {str(exception)}")
        log("ERROR", module, f"错误堆栈:\n{traceback.format_exc()}")

def log_start(module, params=None):
    """记录开始执行日志"""
    log("INFO", module, "=" * 60)
    log("INFO", module, f"开始执行 - {module}")
    if params:
        log("INFO", module, f"执行参数: {params}")
    log("INFO", module, "=" * 60)

def log_complete(module, success_count, fail_count, duration_seconds):
    """记录执行完成日志"""
    log("INFO", module, "=" * 60)
    log("INFO", module, f"执行完成 - {module}")
    log("INFO", module, f"成功: {success_count}条, 失败: {fail_count}条")
    log("INFO", module, f"总耗时: {duration_seconds:.2f}秒")
    if fail_count > 0:
        log("WARN", module, f"存在{fail_count}条失败消息，请关注")
    log("INFO", module, "=" * 60)


FLOW_TABLE = "tblbznzCSpPhSz93"
DLQ_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".dlq_queue.json")
LARK_CLI = r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd"

def run_cmd(cmd, timeout=60):
    """执行命令（含详细日志）"""
    cmd_str = cmd if isinstance(cmd, str) else " ".join(str(c) for c in cmd)
    log("DEBUG", "run_cmd", f"执行命令: {cmd_str[:100]}...")
    try:
        if isinstance(cmd, list):
            cmd_str = " ".join(f'"{c}"' if (" " in c or "\\" in c) else c for c in cmd)
        else:
            cmd_str = cmd
        r = subprocess.run(cmd_str, capture_output=True, timeout=timeout, shell=True)
        stdout = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        stderr = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        if r.returncode == 0:
            log("DEBUG", "run_cmd", f"命令执行成功 (exit code: {r.returncode})")
        else:
            log("WARN", "run_cmd", f"命令执行失败 (exit code: {r.returncode})")
            if stderr:
                log("WARN", "run_cmd", f"错误输出: {stderr[:200]}")
        return r.returncode == 0, stdout, stderr
    except subprocess.TimeoutExpired as e:
        log_error("run_cmd", f"命令执行超时 ({timeout}秒)", e)
        return False, "", str(e)
    except Exception as e:
        log_error("run_cmd", "命令执行异常", e)
        return False, "", str(e)

def load_dlq():
    """加载死信队列（含详细日志）"""
    log("DEBUG", "load_dlq", f"加载DLQ文件: {DLQ_FILE}")
    if not os.path.exists(DLQ_FILE):
        log("INFO", "load_dlq", "DLQ文件不存在，返回空队列")
        return {"messages": [], "stats": {"total": 0, "pending": 0, "retrying": 0, "dead": 0, "success": 0}}
    try:
        with open(DLQ_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        stats = data.get("stats", {})
        log("INFO", "load_dlq", f"DLQ加载成功 - 总消息: {stats.get('total', 0)}, 待重试: {stats.get('pending', 0)}, 已死亡: {stats.get('dead', 0)}, 已成功: {stats.get('success', 0)}")
        return data
    except Exception as e:
        log_error("load_dlq", "DLQ文件加载失败，返回空队列", e)
        return {"messages": [], "stats": {"total": 0, "pending": 0, "retrying": 0, "dead": 0, "success": 0}}

def save_dlq(data):
    """保存死信队列（含详细日志）"""
    log("DEBUG", "save_dlq", f"保存DLQ文件: {DLQ_FILE}")
    try:
        with open(DLQ_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        stats = data.get("stats", {})
        log("INFO", "save_dlq", f"DLQ保存成功 - 总消息: {stats.get('total', 0)}, 待重试: {stats.get('pending', 0)}, 已死亡: {stats.get('dead', 0)}, 已成功: {stats.get('success', 0)}")
        return True
    except Exception as e:
        log_error("save_dlq", "DLQ文件保存失败", e)
        return False

def write_flow(data):
    """写入流水记录（含详细日志）"""
    log("INFO", "write_flow", f"开始写入流水记录 - 卡片ID: {data.get('卡片ID', 'unknown')}, 结果: {data.get('结果', 'unknown')}")
    import tempfile
    tmp_file = None
    try:
        tmp_filename = f"tmp_dlq_flow_{int(datetime.now().timestamp()*1000)}.json"
        tmp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), tmp_filename)
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        log("DEBUG", "write_flow", f"临时文件已创建: {tmp_filename}")

        cmd = [LARK_CLI, "base", "+record-upsert",
               "--base-token", BASE_TOKEN, "--table-id", FLOW_TABLE,
               "--as", "user", "--json", f"@./{tmp_filename}"]
        ok, stdout, stderr = run_cmd(cmd, timeout=60)
        if ok:
            log("INFO", "write_flow", "流水记录写入成功")
            return True
        else:
            log("ERROR", "write_flow", f"流水记录写入失败 - 错误: {stderr[:200]}")
            return False
    except Exception as e:
        log_error("write_flow", "流水记录写入异常", e)
        return False
    finally:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
                log("DEBUG", "write_flow", f"临时文件已清理: {tmp_filename}")
            except Exception as e:
                log("WARN", "write_flow", f"临时文件清理失败: {e}")

def process_pending():
    """处理待重试消息（含详细日志）"""
    start_time = datetime.now()
    log_start("process_pending", {"action": "process_pending"})

    dlq = load_dlq()
    pending = [m for m in dlq["messages"] if m.get("status") == "pending"]
    log("INFO", "process_pending", f"待重试消息: {len(pending)} 条")

    if not pending:
        log("INFO", "process_pending", "队列为空，无需处理")
        duration = (datetime.now() - start_time).total_seconds()
        log_complete("process_pending", 0, 0, duration)
        return 0

    success_count = 0
    fail_count = 0

    for idx, msg in enumerate(pending, 1):
        msg_id = msg.get("message_id", "unknown")
        log("INFO", "process_pending", f"处理消息 [{idx}/{len(pending)}]: {msg_id}")
        log("DEBUG", "process_pending", f"  原始内容: {msg.get('message_text', '')[:50]}")
        log("DEBUG", "process_pending", f"  错误类型: {msg.get('error_type', '')}")
        log("DEBUG", "process_pending", f"  重试次数: {msg.get('retry_count', 0)}")

        # 构造流水数据（简化版，实际应从原始消息解析）
        flow_data = {
            "卡片ID": msg.get("card_id", ""),
            "卡片标题": msg.get("card_title", "DLQ重试"),
            "结果": [msg.get("result", "会")],
            "event_id": f"{msg.get('card_id','')}|{msg.get('result','会')}|{int(datetime.now().timestamp()*1000)}",
            "来源": ["DLQ重试"],
            "event_type": ["COMMIT"],
        }

        # 尝试写入
        ok = write_flow(flow_data)
        if ok:
            msg["status"] = "success"
            msg["retry_count"] = msg.get("retry_count", 0) + 1
            msg["success_time"] = datetime.now().isoformat()
            dlq["stats"]["success"] += 1
            dlq["stats"]["pending"] -= 1
            success_count += 1
            log("INFO", "process_pending", f"  ✅ 消息 {msg_id} 重试成功")
        else:
            msg["retry_count"] = msg.get("retry_count", 0) + 1
            if msg["retry_count"] >= 3:
                msg["status"] = "dead"
                dlq["stats"]["dead"] += 1
                dlq["stats"]["pending"] -= 1
                log("ERROR", "process_pending", f"  ❌ 消息 {msg_id} 重试失败（已达最大次数{msg['retry_count']}，标记为dead）")
            else:
                log("WARN", "process_pending", f"  ❌ 消息 {msg_id} 重试失败（第{msg['retry_count']}次，将继续重试）")
            fail_count += 1

    save_dlq(dlq)

    duration = (datetime.now() - start_time).total_seconds()
    log_complete("process_pending", success_count, fail_count, duration)
    return 0 if fail_count == 0 else 1

def show_status():
    """显示队列状态（含详细日志）"""
    log_start("show_status", {"action": "show_status"})

    dlq = load_dlq()
    stats = dlq.get("stats", {})
    log("INFO", "show_status", f"总消息数: {stats.get('total', 0)}")
    log("INFO", "show_status", f"待重试: {stats.get('pending', 0)}")
    log("INFO", "show_status", f"重试中: {stats.get('retrying', 0)}")
    log("INFO", "show_status", f"已成功: {stats.get('success', 0)}")
    log("INFO", "show_status", f"已死亡: {stats.get('dead', 0)}")

    messages = dlq.get("messages", [])
    if messages:
        log("INFO", "show_status", f"最近5条消息:")
        for msg in messages[-5:]:
            log("INFO", "show_status", f"  [{msg.get('status','?')}] {msg.get('message_id','?')[:20]} - {msg.get('message_text','')[:30]}")
    else:
        log("INFO", "show_status", "队列为空")

    log("INFO", "show_status", "状态查询完成")
    return 0

def main():
    """主函数（含详细日志）"""
    parser = argparse.ArgumentParser(description="死信队列消费者")
    parser.add_argument("--status", action="store_true", help="查看队列状态")
    args = parser.parse_args()

    log("INFO", "main", "=" * 60)
    log("INFO", "main", "DLQ消费者启动")
    log("INFO", "main", f"执行模式: {'状态查询' if args.status else '消息处理'}")
    log("INFO", "main", "=" * 60)

    try:
        if args.status:
            result = show_status()
        else:
            result = process_pending()
        log("INFO", "main", f"DLQ消费者正常结束，退出码: {result}")
        return result
    except Exception as e:
        log_error("main", "DLQ消费者执行异常", e)
        return 1

if __name__ == "__main__":
    sys.exit(main())
