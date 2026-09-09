# -*- coding: utf-8 -*-
"""
chat_command.py — V13 波次2 群内文字指令复习路径（P0 并行底座，零自动化次数/零AI点）
定稿（仲裁2）：表内按钮为 P0 首选；文字指令核权限后并行。已验证：自建应用A具备 im:message 读取权限。

指令格式（用户发到群内）：
  "会 1" / "会1" / "不会 2" / "模糊 3" / "会 N"（N=今日队列序号） 或
  "会 recxxx"（卡片ID直指）
轮询：拉群历史消息 → 跳过应用自身消息 → 解析最新未处理指令 → 写流水 → 回执
"""
import re, json
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))

# 结果映射
CMD_MAP = {
    '会': '会', '对': '会', 'yes': '会', 'y': '会', '知道': '会', '记住了': '会',
    '不会': '不会', '错': '不会', 'no': '不会', 'n': '不会', '忘了': '不会',
    '模糊': '模糊', '?': '模糊', '？': '模糊', '不确定': '模糊', 'fuzzy': '模糊',
}
# 归一化指令：去掉空白和常见标点
_NORM = re.compile(r'[\s，。、,.!！?？]+')


def parse_command(text):
    """解析群消息文本 → (result, target) 或 None
    target 可能是序号(int) 或 rec开头卡片ID（保留原大小写）。"""
    if not text:
        return None
    raw = str(text).strip()
    t = _NORM.sub('', raw).lower()
    if not t:
        # 纯标点（如"？"）也算模糊指令
        if raw in ('?', '？'):
            return '模糊', None
        return None
    # 匹配：动作[序号|recid]
    m = re.match(r'^(会|不会|模糊|对|错|忘了|记住了|不确定|yes|no|y|n|\?|？)([0-9]+|rec[a-z0-9A-Z]+)?$', t)
    if not m:
        return None
    verb = m.group(1)
    result = CMD_MAP.get(verb)
    if not result:
        return None
    target = m.group(2)
    if target:
        if target.startswith('rec'):
            # 从原文取 recid（保留大小写）
            m2 = re.search(r'rec[a-zA-Z0-9]+', raw)
            return result, (m2.group(0) if m2 else target)
        return result, int(target)
    return result, None


def is_app_message(msg):
    """跳过应用自身消息（sender_type=app）。"""
    s = msg.get('sender') or {}
    return s.get('sender_type') == 'app'


def extract_text(msg):
    """从消息体提取文本内容。"""
    body = msg.get('body') or {}
    content = body.get('content') or ''
    if msg.get('msg_type') == 'text':
        try:
            d = json.loads(content) if isinstance(content, str) else content
            return d.get('text', '')
        except Exception:
            return content
    return ''


def map_to_cards(plan, target):
    """把指令 target 映射到今日队列卡片ID：
    target=序号(1-based, due优先) / target=recid直接返回(须在队列中)。"""
    seq = plan['due'] + plan['new']
    if isinstance(target, str) and target.startswith('rec'):
        return target if target in seq else None
    if isinstance(target, int):
        if 1 <= target <= len(seq):
            return seq[target - 1]
    return None
