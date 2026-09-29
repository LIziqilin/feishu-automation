#!/usr/bin/env python
"""
feishu_cards.py - 飞书交互式消息卡片
V50新增：将纯文本回复升级为带按钮的交互式卡片
支持：任务完成按钮、归档按钮、延迟提醒按钮
"""
import json
import os
import sys

# 导入基础配置
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v19_integration import LARK_NODE_EXE, LARK_CLI_SCRIPT, BASE_TOKEN
import subprocess

CHAT_ID = "oc_1fe154e172ab04622b7ffa810ac172bc"


def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, shell=True)
        stdout = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        stderr = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return r.returncode == 0, stdout, stderr
    except Exception as e:
        return False, "", str(e)


def send_card(card_content):
    """发送交互式卡片到群聊"""
    try:
        cmd = [
            LARK_NODE_EXE, LARK_CLI_SCRIPT, "im", "+messages-send",
            "--chat-id", CHAT_ID,
            "--as", "bot",
            "--msg-type", "interactive",
            "--content", json.dumps(card_content, ensure_ascii=False)
        ]
        ok, stdout, stderr = run_cmd(cmd, timeout=30)
        if ok:
            print(f"  ✅ 卡片发送成功")
            return True, "卡片已发送"
        else:
            print(f"  ❌ 卡片发送失败: {stderr[:100]}")
            return False, stderr[:100]
    except Exception as e:
        return False, str(e)


def build_task_card(task_name, record_id, due_date=None, status="待办"):
    """构建任务卡片（带完成、归档按钮）"""
    card = {
        "config": {
            "wide_screen_mode": True
        },
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "📋 任务详情"
            },
            "template": "blue"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**任务名称：** {task_name}\n**状态：** {status}" + 
                               (f"\n**截止日期：** {due_date}" if due_date else "")
                }
            },
            {
                "tag": "hr"
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "✅ 完成任务"
                        },
                        "type": "primary",
                        "value": {
                            "action": "complete_task",
                            "record_id": record_id,
                            "task_name": task_name
                        }
                    },
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "⏰ 延迟1天"
                        },
                        "type": "default",
                        "value": {
                            "action": "delay_task",
                            "record_id": record_id,
                            "task_name": task_name,
                            "days": 1
                        }
                    },
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "📦 归档"
                        },
                        "type": "default",
                        "value": {
                            "action": "archive_task",
                            "record_id": record_id,
                            "task_name": task_name
                        }
                    }
                ]
            }
        ]
    }
    return card


def build_remind_card(remind_content, remind_time, record_id):
    """构建提醒卡片（带完成、稍后提醒按钮）"""
    card = {
        "config": {
            "wide_screen_mode": True
        },
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "⏰ 提醒到点了"
            },
            "template": "orange"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**提醒内容：** {remind_content}\n**提醒时间：** {remind_time}"
                }
            },
            {
                "tag": "hr"
            },
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": "点击按钮快速处理"
                    }
                ]
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "✅ 已完成"
                        },
                        "type": "primary",
                        "value": {
                            "action": "complete_remind",
                            "record_id": record_id,
                            "remind_content": remind_content
                        }
                    },
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "⏰ 10分钟后再提醒"
                        },
                        "type": "default",
                        "value": {
                            "action": "snooze_remind",
                            "record_id": record_id,
                            "remind_content": remind_content,
                            "minutes": 10
                        }
                    }
                ]
            }
        ]
    }
    return card


def build_insight_card(insight_content, tags=None, record_id=None):
    """构建洞察卡片（带关联任务按钮）"""
    card = {
        "config": {
            "wide_screen_mode": True
        },
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "💡 已记录洞察"
            },
            "template": "green"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**内容：** {insight_content[:100]}{'...' if len(insight_content)>100 else ''}" +
                               (f"\n**标签：** {', '.join(tags)}" if tags else "")
                }
            },
            {
                "tag": "hr"
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "📝 转为待办"
                        },
                        "type": "primary",
                        "value": {
                            "action": "insight_to_task",
                            "insight_content": insight_content,
                            "record_id": record_id
                        }
                    },
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "🔍 查看详情"
                        },
                        "type": "default",
                        "value": {
                            "action": "view_insight",
                            "record_id": record_id
                        }
                    }
                ]
            }
        ]
    }
    return card


def build_health_alert_card(alert_type, alert_message, suggest_action=""):
    """构建系统告警卡片"""
    card = {
        "config": {
            "wide_screen_mode": True
        },
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "⚠️ 系统健康告警"
            },
            "template": "red"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**告警类型：** {alert_type}\n**详情：** {alert_message}" +
                               (f"\n**建议操作：** {suggest_action}" if suggest_action else "")
                }
            },
            {
                "tag": "hr"
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "🔧 立即处理"
                        },
                        "type": "primary",
                        "value": {
                            "action": "handle_alert",
                            "alert_type": alert_type
                        }
                    },
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "✅ 已知晓"
                        },
                        "type": "default",
                        "value": {
                            "action": "ack_alert",
                            "alert_type": alert_type
                        }
                    }
                ]
            }
        ]
    }
    return card


if __name__ == "__main__":
    # 测试卡片
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "test_task":
            card = build_task_card("测试任务", "rec_test123", "2026-09-30", "待办")
            send_card(card)
        elif cmd == "test_remind":
            card = build_remind_card("测试提醒内容", "2026-09-29 16:00", "rec_test456")
            send_card(card)
        elif cmd == "test_insight":
            card = build_insight_card("这是一条测试洞察内容", ["测试", "标签"], "rec_test789")
            send_card(card)
        elif cmd == "test_alert":
            card = build_health_alert_card("Ollama连接失败", "目标计算机积极拒绝", "检查Ollama服务是否启动")
            send_card(card)
    else:
        print("用法: python feishu_cards.py [test_task|test_remind|test_insight|test_alert]")
