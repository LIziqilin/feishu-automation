# -*- coding: utf-8 -*-
"""
card_event_handler.py — 飞书交互式卡片按钮事件长连接处理（V51.8）
通过 lark-cli event consume card.action.trigger 长连接接收按钮点击，
无需公网URL、无需内网穿透。
"""
import subprocess, json, sys, os, time, re
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
os.chdir(HERE)

LARK_CLI = r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd"
BASE_TOKEN = "X8N1bvN3na99dFsyu0gcU8zTnHf"
TASK_TABLE = "tblz3H4lV7PCrBrX"

LOG_FILE = r"D:\AI-Tools\feishu\V13方案增强\logs\card_event.log"
Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except: pass

def send_group(text):
    try:
        from v15_features import send_chat
        send_chat(text)
    except Exception as e:
        log(f"send_group error: {e}")

def update_task_status(record_id, status, task_name=""):
    """更新多维表格任务状态（使用--record-id + 字段值格式）"""
    fields = {"状态": [status]}
    if status == "已完成":
        fields["实际完成日期"] = time.strftime("%Y-%m-%d %H:%M")
    tmp = HERE / f"tmp_card_{int(time.time()*1000)}.json"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(fields, f, ensure_ascii=False)
        cmd = [LARK_CLI, "base", "+record-upsert",
               "--base-token", BASE_TOKEN, "--table-id", TASK_TABLE,
               "--as", "user", "--record-id", record_id,
               "--json", f"@./{tmp.name}"]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=30)
        if r.returncode == 0:
            log(f"任务状态已更新: {task_name} -> {status}")
            send_group(f"✅ 任务已{status}：{task_name}")
            return True
        else:
            log(f"更新失败: {(r.stderr or r.stdout)[:200]}")
            return False
    except Exception as e:
        log(f"update error: {e}")
        return False
    finally:
        if tmp.exists():
            try: tmp.unlink()
            except: pass

def handle_event(event):
    """处理卡片按钮事件"""
    action_value_str = event.get("action_value", "{}")
    try:
        value = json.loads(action_value_str)
    except:
        value = {}

    action_type = value.get("action", "")
    task_name = value.get("task_name", "")
    record_id = value.get("record_id", "")
    chat_id = event.get("chat_id", "")

    log(f"按钮点击: action={action_type}, task={task_name}, record={record_id}")

    if action_type == "complete_task" and record_id:
        update_task_status(record_id, "已完成", task_name)
    elif action_type == "archive_task" and record_id:
        update_task_status(record_id, "已归档", task_name)
    else:
        log(f"未知动作: {action_type}")

def main():
    log("卡片事件长连接处理器启动")
    cmd = [LARK_CLI, "event", "consume", "card.action.trigger", "--as", "bot"]
    log(f"启动: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           stdin=subprocess.PIPE,
                           text=True, encoding="utf-8", errors="replace",
                           bufsize=1)
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                handle_event(event)
            except json.JSONDecodeError:
                log(f"非JSON输出: {line[:100]}")
    except KeyboardInterrupt:
        log("收到中断信号，退出")
    finally:
        proc.terminate()

if __name__ == "__main__":
    main()
