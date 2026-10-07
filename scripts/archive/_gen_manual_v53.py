# -*- coding: utf-8 -*-
"""生成《客户使用指导手册-指令版》Word文档"""
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

doc = Document()

# 全局中文字体
style = doc.styles['Normal']
style.font.name = 'Microsoft YaHei'
style.font.size = Pt(10.5)
style._element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')

def set_cn(run, name='Microsoft YaHei'):
    run.font.name = name
    run._element.rPr.rFonts.set(qn('w:eastAsia'), name)

def h(text, level=1):
    p = doc.add_heading(text, level=level)
    for r in p.runs:
        set_cn(r)
        r.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
    return p

def para(text, bold=False, size=10.5, italic=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    set_cn(r); r.bold = bold; r.italic = italic; r.font.size = Pt(size)
    return p

def example(text):
    """预期返回示例，灰色缩进块"""
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.25)
    r = p.add_run(text)
    set_cn(r)
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    return p

# ===== 封面 =====
title = doc.add_heading('', level=0)
tr = title.add_run('AI 个人助理系统\n客户使用指导手册（指令版）')
set_cn(tr); tr.font.size = Pt(26); tr.bold = True
tr.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_paragraph()
sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
sr = sub.add_run('适用对象：飞书总控群「我的助手」机器人\n版本：V53  |  更新日期：2026-10-07')
set_cn(sr); sr.font.size = Pt(12); sr.font.color.rgb = RGBColor(0x66,0x66,0x66)

doc.add_page_break()

# ===== 使用前提 =====
h('一、怎么用（30秒上手）', 1)
para('1. 打开飞书，进入「总控群」。', bold=True)
para('2. 输入 @我的助手，后面紧跟你要发的指令（也可以不@，机器人会自动识别）。')
para('3. 回车发送，几秒到几十秒内机器人会在群里回复。')
para('4. 所有指令大小写、全角/半角冒号均可，例如「新建任务：写报告」和「新建任务:写报告」都可以。')
para('提示：斜杠斜杠“/”、引号等符号不要加，直接按表格里的写法发即可。', italic=True, size=9.5)

# ===== 通用命令表生成函数 =====
def make_table(rows):
    """rows: list of (指令, 功能, 预期返回示例)"""
    t = doc.add_table(rows=1, cols=3)
    t.style = 'Light Grid Accent 1'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, txt in enumerate(['指令（照抄发送）', '功能', '机器人会怎么回（预期示例）']):
        hdr[i].text = ''
        r = hdr[i].paragraphs[0].add_run(txt)
        set_cn(r); r.bold = True; r.font.size = Pt(10)
    widths = [Inches(2.0), Inches(1.6), Inches(3.0)]
    for cmd, func, ex in rows:
        cells = t.add_row().cells
        for i, txt in enumerate([cmd, func, ex]):
            cells[i].text = ''
            r = cells[i].paragraphs[0].add_run(txt)
            set_cn(r); r.font.size = Pt(9)
            if i == 2:
                r.font.color.rgb = RGBColor(0x44,0x44,0x44)
    for row in t.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = w
    return t

# ===== 二、学习类 =====
h('二、学习类指令（闪卡复习 / 费曼 / 错题）', 1)
make_table([
    ('闪卡\n闪卡复习\n今日卡片\n复习', '开始今日待复习卡片',
     '📇 今日复习 1/3\nQ：酒店给排水系统维保一般按什么周期执行？\n（答完后我会告诉你答案和下次复习时间）\n直接回复：会 / 不会 / 模糊'),
    ('会\n不会\n模糊', '逐张回答（按顺序）',
     '💡 答案：给排水维保通常按季度执行\n📅 下次复习：2026-10-10（3天后）'),
    ('会2\n不会3\n模糊1', '指定第几张回答',
     '💡 答案：复利终值=本金×(1+r)^n\n📅 下次复习：2026-10-12（5天后）'),
    ('会1会2会3', '一次批量答多张',
     '✅ 批量答题完成：成功3张，失败0张\n💡 已自动排好下次复习日期'),
    ('不会 记不清\n不会 理解错\n不会 题目歧义\n不会 已过期', '带错因回答',
     '已记录错因「记不清」，该卡将缩短间隔重点复习。'),
    ('费曼\n费曼 复利', '抽一道题让你讲解',
     '🎤 请用自己的话讲清楚「复利」，越长越好。'),
    ('讲解：你的讲解内容', 'AI对你的讲解打分',
     '✅ 讲解评分：80分\n优点：抓住了本金×利率的核心\n建议：补充一个真实例子'),
    ('错题本', '查看当前错题清单',
     '📕 当前错题共3张：\n1. 复利公式漏乘本金\n2. 给排水维保周期记错\n…'),
    ('记录错题：复利公式我记成(1+r)^n，忘了乘本金P',
     '记错题→自动建学习卡→DeepSeek解析',
     '✅ 已记录错题并AI解析\n📝 错题：复利公式漏乘本金P\n🏷️ 知识点：金融数学-复利\n💡 解析：终值=本金×(1+r)^n，不能只算增长倍数'),
    ('学知识：什么是飞轮效应\n知识：xxx\n搜索：xxx\n查：xxx', '检索并学习新知识',
     '📚 知识检索\n飞轮效应：指一个系统的各个部分像齿轮一样互相推动，越转越快…\n（已沉淀到知识表）'),
])

# ===== 三、任务类 =====
h('三、任务管理指令（建任务 / 销项 / 归档）', 1)
make_table([
    ('新建任务：跟踪室外热力施工\n创建任务：xxx\n记录任务：xxx', '建一个待办任务',
     '✅ 已创建任务：跟踪室外热力施工\n🆔 已加入待办列表'),
    ('批量新建：A；B；C', '一次建多个任务',
     '✅ 批量新建完成：共3个，成功3个'),
    ('查看待办任务\n列出所有待办\n待办有哪些', '列出未完成任务',
     '📋 待办任务 5 项：\n1. 跟踪室外热力施工\n2. 写周报告\n…'),
    ('查看已完成任务', '列出已完成任务',
     '✅ 已完成任务 3 项：\n1. 销项最终确认单任务｜2026-09-20'),
    ('完成：任务名\n完成 任务名\n搞定xxx\n做完了xxx', '把任务标记为完成',
     '✅ 任务已完成\n📋 销项最终确认单任务\n🕐 完成时间：2026-09-20 11:08\n💡 3天后可自动归档'),
    ('归档：任务名\n收起来xxx\n存档xxx', '把任务归档隐藏',
     '📦 任务已归档\n📋 销项最终确认单任务\n📝 已从日常待办隐藏，历史保留'),
    ('!revoke\n!撤销', '撤回上一步操作',
     '↩️ 已撤销上一步操作'),
])

# ===== 四、提醒/洞察 =====
h('四、提醒与洞察指令', 1)
make_table([
    ('提醒我1分钟后 测试提醒\n提醒我X小时后 内容', '倒计时即时提醒',
     '✅ 提醒已设置\n⏰ 时间：2026-10-07 21:40\n📝 内容：测试提醒\n到点我会自动提醒你！\n\n（到点自动推卡片：带「✅完成任务」「📦归档」按钮）'),
    ('提醒我明天下午3点开会', '定时提醒',
     '✅ 提醒已设置 ⏰ 2026-10-08 15:00 📝 开会'),
    ('洞察：xxx\n写洞察：xxx\n记录洞察：xxx', '把感悟结构化归档',
     '✅ 洞察已记录（结构化归档）\n🏷️ 标签：其他\n📚 关联科目：通用知识\n📋 AI摘要：…\n🆔 记录ID：recxxxx'),
    ('沉淀洞察\n洞察转卡片', '高价值洞察转成复习卡',
     '🧩 洞察沉淀完成，3条高价值洞察已转为知识卡进入复习循环'),
])

# ===== 五、AI能力/分析 =====
h('五、AI 分析与知识指令', 1)
make_table([
    ('问系统：什么是复利效应', '轻量知识问答（带引用）',
     '复利效应指资金通过持续增长、收益再投入而加速增长的现象。\n📄 引用：用户指导手册 / 系统总体方案'),
    ('智能：帮我写一段周报', 'Coze复杂任务',
     '（根据任务返回结果，可能需要等待较长时间）'),
    ('导知识：一段文字…', '文本直接沉淀为知识',
     '📥 已沉淀为知识（洞察表）\n🆔 recxxxx'),
    ('生成学习周报', '生成本周学习周报',
     '✅ 学习周报已生成并写入洞察笔记表\n本周共学习29张卡片，掌握0张…'),
    ('更新用户画像', '重新计算用户画像',
     '✅ 画像演化3条已写入用户画像表'),
    ('系统健康诊断', '诊断系统健康',
     '✅ 健康诊断已写入系统健康表：正常'),
    ('今日推荐\n个性化推荐', '个性化学习队列',
     '🎯 今日为你推荐8张卡\n1. 复利公式（遗忘提醒+高优先级）'),
    ('知识演进\n演进图', '生成知识体系图',
     '🗺 知识体系演进图已更新（见Obsidian）'),
    ('知识缺口\n盲点', '分析知识盲区',
     '🔍 知识缺口分析完成，建议优先补：财务/考证类'),
    ('三察\n今日洞察', '天气+社会/自然/人性日报',
     '🔍 今日三察已生成并推送'),
    ('记忆分层', '生成系统记忆结构',
     '🧠 记忆分层已生成'),
    ('时间块', '重排今日时间块',
     '⏰ 今日时间块已重排（见Obsidian时间块规划.md）'),
    ('番茄\n番茄25 写报告', '番茄钟统计/记录',
     '🍅 今日番茄3个/专注75分钟\n距8个目标还差5个'),
])

# ===== 六、系统控制 =====
h('六、系统控制指令', 1)
make_table([
    ('系统体检\n体检', '跑25项健康自检',
     '🩺 系统体检完成：25项通过，0项异常'),
    ('暂停\n暂停3天', '暂停推送N天',
     '⏸ 已暂停推送2天，到期自动恢复'),
    ('恢复\n继续', '恢复推送',
     '▶️ 已恢复推送'),
])

# ===== 七、后台自动功能 =====
h('七、无需发指令的自动功能', 1)
para('以下功能由系统定时/自动完成，你不需要发任何指令：', bold=True)
for t in [
    '早/中/晚报自动推送：每天定时汇总学习与任务情况。',
    '每小时自动备份：数据自动轮转备份，保留近32份。',
    '看门狗自愈：webapi、Ollama、卡片回调等服务掉线后30分钟内自动重启。',
    '任务到期提醒：到点自动推送带按钮的卡片，点按钮即可完成/归档。',
    '云端问答（关机可用）：通过 GitHub Actions 外部触发，电脑关机也能问。',
    '卡片交互按钮：提醒卡片上的「✅完成任务」「📦归档」按钮，点击即操作。',
]:
    p = doc.add_paragraph(t, style='List Bullet')
    for r in p.runs: set_cn(r); r.font.size = Pt(10)

# ===== 八、常见问题 =====
h('八、常见问题（FAQ）', 1)
faqs = [
    ('发了指令没反应？', '先等1分钟（轮询周期约1-5分钟）；仍无反应时发「体检」查看系统状态，或联系运维。'),
    ('提醒到点没推送？', '确认电脑开机且「我的助手」长连接在线；系统关机时提醒不触发。'),
    ('答题后不知道对不对？', '答完会自动返回「💡答案」和「📅下次复习日期」。'),
    ('想暂停几天不被打扰？', '发「暂停3天」即可，到期自动恢复。'),
]
for q, a in faqs:
    para('问：' + q, bold=True)
    para('答：' + a, size=10)

out = r'D:\AI-Tools\feishu\V13方案增强\docs\客户使用指导手册-指令版-V53.docx'
doc.save(out)
print('SAVED:', out)
