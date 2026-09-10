# -*- coding: utf-8 -*-
"""
morning_brief.py — V13 云端早报兜底（GitHub Actions运行，07:53北京=23:53UTC）
幂等：检查系统健康表今日是否已有早报记录，有则跳过，避免本地/云端双份
兼容：云端运行，使用相对路径，不依赖D:\AI-Tools\shared
"""
import sys
import os
import json
from datetime import datetime, timedelta, timezone

# 云端兼容：使用脚本所在目录作为模块路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from feishu_sdk import FeishuClient, TABLES, get_bot_config

CST = timezone(timedelta(hours=8))


def check_idempotent(c, today_str):
    """幂等检查：今日是否已有早报推送记录。有则返回True(跳过)。"""
    try:
        health = c.read_records(TABLES['系统健康表'], page_size=100)
        for record in health:
            f = record.get('fields', {})
            check_item = str(f.get('检查项', ''))
            if '早报' in check_item or 'morning' in check_item.lower():
                # 检查时间是否是今天
                t = f.get('最近检查时间') or f.get('检查时间')
                if t:
                    try:
                        dt = datetime.fromtimestamp(int(t) / 1000, tz=CST)
                        if dt.strftime('%Y-%m-%d') == today_str:
                            return True  # 今日已有早报，跳过
                    except Exception:
                        pass
        return False
    except Exception as e:
        print(f'[幂等检查异常] {e}，继续执行')
        return False


def record_push(c, today_str):
    """记录早报推送成功到系统健康表。"""
    try:
        now_ms = int(datetime.now(tz=CST).timestamp() * 1000)
        c.create_record(TABLES['系统健康表'], {
            '检查项': f'早报推送-{today_str}',
            '状态': '正常',
            '最近检查时间': now_ms,
            '检查结果': '云端早报推送成功',
        })
        print(f'[记录] 早报推送已记录到健康表')
    except Exception as e:
        print(f'[记录异常] {e}')


def build_brief(c, today):
    """构建早报内容（简化版：今日复习队列+到期任务+日期）。"""
    lines = []
    lines.append(f'📅 {today.strftime("%Y-%m-%d %A")} 早报')
    lines.append('')

    # 1. 今日复习队列
    try:
        cards = c.read_records(TABLES['学习卡片表'], page_size=100)
        due_cards = []
        for card in cards:
            f = card.get('fields', {})
            status = str(f.get('卡片状态', ''))
            if status in ('LEARNING', 'REVIEWING'):
                due_cards.append(card)
        lines.append(f'📚 今日复习: {len(due_cards)}张待复习')
        for i, card in enumerate(due_cards[:3], 1):
            f = card.get('fields', {})
            title = str(f.get('卡片问题正面', f.get('卡片名称', '无标题')))[:25]
            lines.append(f'  {i}. {title}')
        if len(due_cards) > 3:
            lines.append(f'  ...还有{len(due_cards)-3}张')
    except Exception as e:
        lines.append(f'📚 复习队列: 读取异常({e})')

    lines.append('')

    # 2. 今日到期任务
    try:
        tasks = c.read_records(TABLES['任务总表'], page_size=100)
        today_str = today.strftime('%Y-%m-%d')
        due_tasks = []
        for task in tasks:
            f = task.get('fields', {})
            status = str(f.get('状态', ''))
            if status in ('已完成', '已取消'):
                continue
            deadline = f.get('截止日期', '')
            if deadline and today_str in str(deadline):
                due_tasks.append(task)
        lines.append(f'✅ 今日到期: {len(due_tasks)}个任务')
        for i, task in enumerate(due_tasks[:3], 1):
            f = task.get('fields', {})
            title = str(f.get('任务名称', f.get('标题', '无标题')))[:25]
            lines.append(f'  {i}. {title}')
    except Exception as e:
        lines.append(f'✅ 到期任务: 读取异常({e})')

    lines.append('')
    lines.append('💡 回复"会 N"标记第N张卡已掌握')
    lines.append('💡 回复"不会 N"标记第N张卡需复习')

    return '\n'.join(lines)


def main():
    now = datetime.now(tz=CST)
    today_str = now.strftime('%Y-%m-%d')
    print(f'[V13云端早报] {now.strftime("%Y-%m-%d %H:%M:%S")} CST')

    c = FeishuClient()

    # 幂等检查
    if check_idempotent(c, today_str):
        print(f'[幂等] 今日({today_str})已有早报记录，跳过推送')
        return

    # 构建早报
    brief = build_brief(c, now)
    print(f'[内容] 早报长度: {len(brief)}字符')

    # 推送
    try:
        bot = get_bot_config()
        result = c.send_message(bot['webhook'], bot['secret'], brief)
        code = result.get('code', result.get('StatusCode', -1))
        msg = result.get('msg', result.get('StatusMessage', ''))
        print(f'[推送] code={code}, msg={msg}')

        if code == 0:
            record_push(c, today_str)
            print(f'[完成] 云端早报推送成功')
        else:
            print(f'[失败] 推送失败 code={code}')
            sys.exit(1)
    except Exception as e:
        print(f'[推送异常] {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
