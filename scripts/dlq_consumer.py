#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
dlq_consumer.py
死信队列消费者 - 处理写入失败的消息，自动重试
用法：
  python dlq_consumer.py           # 处理待重试消息
  python dlq_consumer.py --status  # 查看队列状态
"""
import json
import os
import sys
import subprocess
import argparse
from datetime import datetime

BASE_TOKEN = "X8N1bvN3na99dFsyu0gcU8zTnHf"
FLOW_TABLE = "tblbznzCSpPhSz93"
DLQ_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".dlq_queue.json")
LARK_CLI = r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd"

def run_cmd(cmd, timeout=60):
    """执行命令"""
    try:
        if isinstance(cmd, list):
            cmd_str = " ".join(f'"{c}"' if (" " in c or "\\" in c) else c for c in cmd)
        else:
            cmd_str = cmd
        r = subprocess.run(cmd_str, capture_output=True, timeout=timeout, shell=True)
        stdout = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        stderr = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return r.returncode == 0, stdout, stderr
    except Exception as e:
        return False, "", str(e)

def load_dlq():
    """加载死信队列"""
    if not os.path.exists(DLQ_FILE):
        return {"messages": [], "stats": {"total": 0, "pending": 0, "retrying": 0, "dead": 0, "success": 0}}
    try:
        with open(DLQ_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"messages": [], "stats": {"total": 0, "pending": 0, "retrying": 0, "dead": 0, "success": 0}}

def save_dlq(data):
    """保存死信队列"""
    try:
        with open(DLQ_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存DLQ失败: {e}")
        return False

def write_flow(data):
    """写入流水记录"""
    import tempfile
    tmp_file = None
    try:
        tmp_filename = f"tmp_dlq_flow_{int(datetime.now().timestamp()*1000)}.json"
        tmp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), tmp_filename)
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        cmd = [LARK_CLI, "base", "+record-upsert",
               "--base-token", BASE_TOKEN, "--table-id", FLOW_TABLE,
               "--as", "user", "--json", f"@./{tmp_filename}"]
        ok, stdout, stderr = run_cmd(cmd, timeout=60)
        if not ok:
            print(f"  流水写入失败: {stderr[:100]}")
        return ok
    except Exception as e:
        print(f"  流水写入异常: {e}")
        return False
    finally:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except:
                pass

def process_pending():
    """处理待重试消息"""
    print("=" * 60)
    print("死信队列消费者 - 处理待重试消息")
    print("=" * 60)

    dlq = load_dlq()
    pending = [m for m in dlq["messages"] if m.get("status") == "pending"]
    print(f"\n待重试消息: {len(pending)} 条")

    if not pending:
        print("队列为空，无需处理")
        return 0

    success_count = 0
    fail_count = 0

    for msg in pending:
        msg_id = msg.get("message_id", "unknown")
        print(f"\n处理消息: {msg_id}")
        print(f"  原始内容: {msg.get('message_text', '')[:50]}")
        print(f"  错误类型: {msg.get('error_type', '')}")
        print(f"  重试次数: {msg.get('retry_count', 0)}")

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
            print(f"  ✅ 重试成功")
        else:
            msg["retry_count"] = msg.get("retry_count", 0) + 1
            if msg["retry_count"] >= 3:
                msg["status"] = "dead"
                dlq["stats"]["dead"] += 1
                dlq["stats"]["pending"] -= 1
                print(f"  ❌ 重试失败（已达最大次数，标记为dead）")
            else:
                print(f"  ❌ 重试失败（第{msg['retry_count']}次，将继续重试）")
            fail_count += 1

    save_dlq(dlq)

    print(f"\n处理完成: 成功{success_count}条, 失败{fail_count}条")
    return 0 if fail_count == 0 else 1

def show_status():
    """显示队列状态"""
    print("=" * 60)
    print("死信队列状态")
    print("=" * 60)

    dlq = load_dlq()
    stats = dlq.get("stats", {})
    print(f"\n总消息数: {stats.get('total', 0)}")
    print(f"待重试: {stats.get('pending', 0)}")
    print(f"重试中: {stats.get('retrying', 0)}")
    print(f"已成功: {stats.get('success', 0)}")
    print(f"已死亡: {stats.get('dead', 0)}")

    messages = dlq.get("messages", [])
    if messages:
        print(f"\n最近5条消息:")
        for msg in messages[-5:]:
            print(f"  [{msg.get('status','?')}] {msg.get('message_id','?')[:20]} - {msg.get('message_text','')[:30]}")

    return 0

def main():
    parser = argparse.ArgumentParser(description="死信队列消费者")
    parser.add_argument("--status", action="store_true", help="查看队列状态")
    args = parser.parse_args()

    if args.status:
        return show_status()
    else:
        return process_pending()

if __name__ == "__main__":
    sys.exit(main())
