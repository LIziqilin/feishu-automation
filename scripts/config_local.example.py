#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本地敏感配置文件示例模板
使用方法：复制本文件为 config_local.py，填入真实配置值
注意：config_local.py 已加入 .gitignore，不会提交到GitHub
"""
import os

# 飞书多维表格配置
BASE_TOKEN = "你的Base Token"
TARGET_CHAT_ID = "你的目标群聊ID"

# 表ID配置
FLOW_TABLE = "复习流水表ID"
CARD_TABLE = "学习卡片表ID"
EVENT_LOG_TABLE = "系统事件日志表ID"
TASK_TABLE = "任务总表ID"
KNOWLEDGE_INDEX_TABLE = "知识索引表ID"
SYSTEM_HEALTH_TABLE = "系统健康表ID"
HEARTBEAT_TABLE = "系统心跳表ID"
INSIGHT_TABLE = "洞察笔记表ID"
QUEUE_TABLE = "自动化队列表ID"

# lark-cli路径
LARK_CLI = r"lark-cli.cmd的完整路径"
LARK_NODE_EXE = r"node.exe的完整路径"
LARK_CLI_SCRIPT = r"lark-cli run.js的完整路径"

# 管理员白名单（飞书用户ID或姓名）
ADMIN_WHITELIST = [
    "管理员用户ID",
]

# API密钥（如需要，建议使用环境变量）
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
COZE_API_KEY = os.environ.get("COZE_API_KEY", "")
COZE_BOT_ID = os.environ.get("COZE_BOT_ID", "")
