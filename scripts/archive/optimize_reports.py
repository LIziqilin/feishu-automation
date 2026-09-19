#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""优化午报和晚报"""

with open('v19_integration.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 优化午报：增加任务进度提醒
old_noon = '''        # V39增强：合并今日待办+已完成事项
        try:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from task_insight_extension import get_tasks_summary
            tasks = get_tasks_summary(days_ahead=3)
            if tasks["today_pending"]:
                report += "\\n📋 今日待办:\\n"
                for t in tasks["today_pending"][:5]:
                    report += f"  ⏰ {t['name']}\\n"
            if tasks["today_completed"]:
                report += f"\\n✅ 今日已完成 ({len(tasks['today_completed'])}项):\\n"
                for t in tasks["today_completed"][:5]:
                    report += f"  ✓ {t['name']}\\n"
            if tasks["upcoming"]:
                report += f"\\n📅 即将到期 ({len(tasks['upcoming'])}项):\\n"
                for t in tasks["upcoming"][:3]:
                    days = (t["due_date"] - datetime.now().date()).days if t["due_date"] else "?"
                    report += f"  • {t['name']} ({days}天后)\\n"
        except Exception as e:
            report += f"\\n📋 待办加载异常: {str(e)[:30]}\\n"'''

new_noon = '''        # V39增强：合并今日待办+已完成事项
        try:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from task_insight_extension import get_tasks_summary
            tasks = get_tasks_summary(days_ahead=3)
            # V15增强：任务进度提醒
            total_today = len(tasks["today_pending"]) + len(tasks["today_completed"])
            if total_today > 0:
                progress = int(len(tasks["today_completed"]) / total_today * 100)
                report += f"\\n📊 今日任务进度: {progress}% ({len(tasks['today_completed'])}/{total_today})\\n"
            if tasks["today_pending"]:
                report += "\\n📋 今日待办:\\n"
                for t in tasks["today_pending"][:5]:
                    report += f"  ⏰ {t['name']}\\n"
            if tasks["today_completed"]:
                report += f"\\n✅ 今日已完成 ({len(tasks['today_completed'])}项):\\n"
                for t in tasks["today_completed"][:5]:
                    report += f"  ✓ {t['name']}\\n"
            if tasks["upcoming"]:
                report += f"\\n📅 即将到期 ({len(tasks['upcoming'])}项):\\n"
                for t in tasks["upcoming"][:3]:
                    days = (t["due_date"] - datetime.now().date()).days if t["due_date"] else "?"
                    report += f"  • {t['name']} ({days}天后)\\n"
        except Exception as e:
            report += f"\\n📋 待办加载异常: {str(e)[:30]}\\n"'''

content = content.replace(old_noon, new_noon)

# 优化晚报：增加今日完成总结
old_evening = '''        # V39增强：合并今日已完成+明日待办
        try:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from task_insight_extension import get_tasks_summary
            tasks = get_tasks_summary(days_ahead=7)
            if tasks["today_completed"]:
                report += f"\\n✅ 今日已完成 ({len(tasks['today_completed'])}项):\\n"
                for t in tasks["today_completed"][:8]:
                    report += f"  ✓ {t['name']}\\n"
            else:
                report += "\\n✅ 今日已完成: 暂无记录\\n"
            if tasks["today_pending"]:
                report += f"\\n⚠️ 今日未完成 ({len(tasks['today_pending'])}项):\\n"
                for t in tasks["today_pending"][:5]:
                    report += f"  ⏰ {t['name']}\\n"
            if tasks["upcoming"]:
                report += f"\\n📅 明日及未来待办 ({len(tasks['upcoming'])}项):\\n"
                for t in tasks["upcoming"][:5]:
                    days = (t["due_date"] - datetime.now().date()).days if t["due_date"] else "?"
                    report += f"  • {t['name']} ({days}天后)\\n"
        except Exception as e:
            report += f"\\n📋 待办加载异常: {str(e)[:30]}\\n"'''

new_evening = '''        # V39增强：合并今日已完成+明日待办
        try:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from task_insight_extension import get_tasks_summary
            tasks = get_tasks_summary(days_ahead=7)
            # V15增强：今日完成总结
            total_today = len(tasks["today_pending"]) + len(tasks["today_completed"])
            if total_today > 0:
                completion_rate = int(len(tasks["today_completed"]) / total_today * 100)
                report += f"\\n📈 今日完成率: {completion_rate}% ({len(tasks['today_completed'])}/{total_today})\\n"
            if tasks["today_completed"]:
                report += f"\\n✅ 今日完成总结 ({len(tasks['today_completed'])}项):\\n"
                for t in tasks["today_completed"][:8]:
                    report += f"  ✓ {t['name']}\\n"
            else:
                report += "\\n✅ 今日完成总结: 暂无记录\\n"
            if tasks["today_pending"]:
                report += f"\\n⚠️ 未完成事项 ({len(tasks['today_pending'])}项):\\n"
                for t in tasks["today_pending"][:5]:
                    report += f"  ⏰ {t['name']}\\n"
            if tasks["upcoming"]:
                report += f"\\n📅 明日待办 ({len(tasks['upcoming'])}项):\\n"
                for t in tasks["upcoming"][:5]:
                    days = (t["due_date"] - datetime.now().date()).days if t["due_date"] else "?"
                    report += f"  • {t['name']} ({days}天后)\\n"
        except Exception as e:
            report += f"\\n📋 待办加载异常: {str(e)[:30]}\\n"'''

content = content.replace(old_evening, new_evening)

with open('v19_integration.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('✅ 午报已优化：增加任务进度提醒')
print('✅ 晚报已优化：增加今日完成总结')
