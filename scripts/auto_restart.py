#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""服务自动重启脚本（V15新增）
监控关键服务状态，连续3次失败自动重启
"""
import datetime
import json
import os
import subprocess
import time
import urllib.request
import urllib.error

# 监控服务列表
SERVICES = [
    {
        "name": "Ollama",
        "check_url": "http://localhost:11434/api/tags",
        "restart_cmd": ["C:\\Users\\Administrator\\AppData\\Local\\Programs\\Ollama\\ollama app.exe"],
        "restart_delay": 5,
    },
]

# 失败次数记录文件
FAIL_COUNT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".restart_state.json")
FAIL_THRESHOLD = 3  # 连续3次失败触发重启


def load_fail_counts():
    """加载失败计数"""
    if os.path.exists(FAIL_COUNT_FILE):
        try:
            with open(FAIL_COUNT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}


def save_fail_counts(counts):
    """保存失败计数"""
    with open(FAIL_COUNT_FILE, "w", encoding="utf-8") as f:
        json.dump(counts, f, ensure_ascii=False, indent=2)


def check_service(url, timeout=5):
    """检查服务是否正常"""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True
    except:
        return False


def restart_service(service):
    """重启服务"""
    name = service["name"]
    cmd = service["restart_cmd"]
    try:
        print(f"  正在重启 {name}...")
        subprocess.Popen(cmd, shell=False)
        time.sleep(service["restart_delay"])
        # 重启后再检查一次
        if check_service(service["check_url"]):
            print(f"  ✅ {name} 重启成功")
            return True
        else:
            print(f"  ❌ {name} 重启后仍未恢复")
            return False
    except Exception as e:
        print(f"  ❌ {name} 重启失败: {e}")
        return False


def main():
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"=== 服务自动重启检查 {now_str} ===")

    fail_counts = load_fail_counts()
    restarted = []

    for service in SERVICES:
        name = service["name"]
        ok = check_service(service["check_url"])

        if ok:
            # 服务正常，重置失败计数
            if fail_counts.get(name, 0) > 0:
                print(f"✅ {name} 已恢复正常，重置失败计数")
            fail_counts[name] = 0
            print(f"✅ {name} 正常")
        else:
            # 服务异常，增加失败计数
            fail_counts[name] = fail_counts.get(name, 0) + 1
            count = fail_counts[name]
            print(f"⚠️ {name} 异常（连续{count}次）")

            # 连续3次失败，自动重启
            if count >= FAIL_THRESHOLD:
                print(f"🔄 {name} 连续{count}次失败，触发自动重启")
                if restart_service(service):
                    restarted.append(name)
                    fail_counts[name] = 0  # 重启成功后重置计数

    save_fail_counts(fail_counts)

    if restarted:
        print(f"\n🔧 已重启服务：{', '.join(restarted)}")
    else:
        print(f"\n✅ 无需重启")

    print(f"=== 检查完成 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    return 0


if __name__ == "__main__":
    exit(main())
