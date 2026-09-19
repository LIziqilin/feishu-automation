# -*- coding: utf-8 -*-
"""生成《AI个人效率系统-用户使用指导手册.docx》"""
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

OUT = r"D:\AI-Tools\feishu\V13方案增强\docs\AI个人效率系统-用户使用指导手册.docx"

doc = Document()

# 中文字体默认
style = doc.styles['Normal']
style.font.name = 'Microsoft YaHei'
style.font.size = Pt(10.5)
style._element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')

def set_cn(run, size=10.5, bold=False, color=None):
    run.font.name = 'Microsoft YaHei'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)

def h1(text):
    p = doc.add_heading(level=1)
    r = p.add_run(text); set_cn(r, 16, True, (0x1F,0x3A,0x5F))

def h2(text):
    p = doc.add_heading(level=2)
    r = p.add_run(text); set_cn(r, 13, True, (0x2E,0x5C,0x8A))

def body(text, bold=False):
    p = doc.add_paragraph()
    r = p.add_run(text); set_cn(r, 10.5, bold)
    return p

def bullet(text):
    p = doc.add_paragraph(style='List Bullet')
    r = p.add_run(text); set_cn(r, 10.5)

def table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = 'Light Grid Accent 1'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, hh in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ''
        r = c.paragraphs[0].add_run(hh); set_cn(r, 10, True)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ''
            r = cells[i].paragraphs[0].add_run(str(v)); set_cn(r, 9.5)
    doc.add_paragraph()

# ===== 封面 =====
tp = doc.add_paragraph(); tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = tp.add_run('AI 个人效率系统'); set_cn(r, 26, True, (0x1F,0x3A,0x5F))
sp = doc.add_paragraph(); sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sp.add_run('用户使用指导手册'); set_cn(r, 18, True, (0x2E,0x5C,0x8A))
mp = doc.add_paragraph(); mp.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = mp.add_run('\n版本 V48  |  2026-09-19\n飞书多维表格 · Obsidian · GitHub · Coze · DeepSeek · AnythingLLM'); set_cn(r, 11, False, (0x66,0x66,0x66))
doc.add_paragraph()

# ===== 1 系统速览 =====
h1('一、系统能帮你做什么（30秒速览）')
body('这是一套跑在你电脑上的个人效率+学习+运维系统。你主要通过两个入口使用它：飞书总控群里的 AI 助手，和每天自动收到的早/午/晚报。系统在后台自动同步飞书多维表格、Obsidian 笔记、做备份、跑健康监控，不需要你天天管。')
table(['入口','你能得到什么'],
      [['飞书总控群 @助手','下任务、销项、归档、记洞察、问系统、闪卡复习、系统体检'],
       ['每天自动推送','早报/午报/晚报：西安天气 + 社会/自然/人性三察洞察'],
       ['多维表格批量AI','错题解析、学习周报、画像演化、健康诊断（额度耗尽自动转DeepSeek）'],
       ['AnythingLLM','把方案/手册/学习资料灌进知识库，自然语言深度问答'],
       ['后台自动化','每日03:00维护+备份、每小时备份、8桥接巡检、故障自动告警']])

# ===== 2 飞书总控群场景 =====
h1('二、场景一：飞书总控群 @助手（最常用）')
body('在总控群里直接 @你的 AI 助手，发送下面这些话即可，它会自动识别意图并操作多维表格。', True)
h2('2.1 任务管理')
table(['你想做的事','直接发送（示例）'],
      [['新建一个任务','新建任务：落实泛光照明验收节奏'],
       ['标记任务完成','搞定了：【P3】GitHub抓外部数据'],
       ['完成后归档','归档 【P3】GitHub抓外部数据'],
       ['查任务/问系统','问系统：我本周还有哪些待办']])
h2('2.2 学习与记录')
table(['你想做的事','直接发送（示例）'],
      [['记一条洞察','洞察：事情落实清楚后再找对策'],
       ['让AI做复杂事','智能：帮我把这条任务拆成3步'],
       ['开始复习','开始闪卡复习'],
       ['系统健康检查','系统体检'],
       ['学一个知识点','学知识：工程总监']])
h2('2.3 怎么验证它真的做对了')
bullet('下任务后：打开飞书多维表格“任务总表”，应能看到这条新记录，状态=进行中。')
bullet('发“搞定了”后：对应任务状态应变为“已完成”，完成时间自动写入。')
bullet('发“归档”后：该任务应从待办视图移到已归档。')
bullet('发“洞察”后：洞察笔记表应新增一条，并带标签、关联科目、AI摘要。')
bullet('如果 @ 了没反应：先跑第四节的故障自查第一步——桥接巡检。')

# ===== 3 自动推送 =====
h1('三、场景二：每天自动收到的三报')
table(['报','时间','内容'],
      [['早报','约07:30','今日计划 + 西安天气 + 三察洞察'],
       ['午报','约12:00','上午完成情况 + 天气'],
       ['晚报','约20:00','全天完成率 + 完成总结 + 矩阵面板 + 天气与洞察']])
h2('怎么验证推送正常')
bullet('每天 07:30 / 12:00 / 20:00 三个时间点看总控群是否收到消息。')
bullet('若某天没收到：打开 GitHub Actions（github.com/LIziqilin/feishu-automation/actions），看 fetch_external_data 运行记录；失败时系统会自动在群里发告警。')

# ===== 4 多维表格批量AI =====
h1('四、场景三：多维表格批量 AI（4类）')
body('当飞书自带 AI 额度用完，系统会自动走 DeepSeek，不影响使用。')
table(['任务','输入','输出','怎么触发'],
      [['错题解析','原题/错因','AI解析+复习建议','学习卡片表逐行点字段捷径，或脚本'],
       ['学习周报','周次','周报草稿','脚本 coze_batch_tasks.py weekly_report'],
       ['画像演化','行为记录','画像标签建议','脚本 coze_batch_tasks.py profile'],
       ['健康诊断','监控指标','修复建议','脚本 coze_batch_tasks.py health']])
h2('脚本方式（稳定，推荐先用这个）')
body('打开 PowerShell，进入项目目录后运行：', True)
bullet('错题解析：python scripts\\coze_batch_tasks.py wrong_answer --limit 3')
bullet('学习周报：python scripts\\coze_batch_tasks.py weekly_report')
bullet('画像演化：python scripts\\coze_batch_tasks.py profile --limit 5')
bullet('健康诊断：python scripts\\coze_batch_tasks.py health --limit 5')
h2('怎么验证')
bullet('脚本跑完最后一行应打印每类任务 1/1 成功，结果已回写多维表格对应行。')
bullet('表格内字段捷径方式：等“错题解析助手”等4个捷径在飞书审批上线后，新建一列选该捷径，点单元格即生成。')

# ===== 5 AnythingLLM =====
h1('五、场景四：AnythingLLM 深度问答')
bullet('打开 AnythingLLM 桌面端，左侧选工作区（学习助手/知识库/洞察 Agent）。')
bullet('直接用自然语言提问，例如“根据最终版方案，备份策略是什么”。')
bullet('@agent 可调用飞书文档工具、或直接读写本机文件。')
bullet('系统已灌入 1939 篇文档、约 1.2 万条向量，5 个工作区。')
h2('怎么验证')
bullet('问一个方案里有答案的问题（如备份策略），回答应能说出每日03:00、8张表、7轮滚动。')

# ===== 6 故障自查 =====
h1('六、场景五：遇到问题怎么自查与验证')
table(['现象','第一步做什么','预期看到'],
      [['群@助手没反应','跑桥接巡检','8个桥接全部“正常”，红项即故障点'],
       ['早/晚报没收到','看GitHub Actions日志','失败会在群里红色告警'],
       ['AI回答异常/超时','跑LLM双通道自检','Coze 和 DeepSeek 都应 pong'],
       ['想全面体检','跑系统健康自检','计划任务/心跳/备份/DLQ 全 PASS'],
       ['担心备份','看 backups 目录','最新应为每小时的 hourly_*.json']])

# ===== 7 常用命令 =====
h1('七、常用命令速查（PowerShell）')
body('统一先执行：cd D:\\AI-Tools\\feishu\\V13方案增强', True)
table(['命令','作用'],
      [['python scripts\\llm_router.py 你的问题','统一问AI（Coze优先，自动切DeepSeek）'],
       ['python scripts\\llm_router.py --check','LLM 双通道自检'],
       ['python scripts\\bridge_health_check.py','8 个桥接巡检'],
       ['python scripts\\system_health_check.py','计划任务+心跳+备份全面体检'],
       ['python scripts\\coze_gateway.py --check','Coze 通道连通性'],
       ['python scripts\\mastery_recalc.py','重算学习掌握度']])

# ===== 8 维护节奏 =====
h1('八、日常维护节奏（你几乎不用管）')
table(['频率','系统自动做什么'],
      [['每小时','hourly_backup 滚动备份；桥接巡检看门狗'],
       ['每日03:00','维护链：备份、一致性、安全审计、演进推荐等27步'],
       ['每天','早/午/晚三报推送；学习轮询'],
       ['你要做的','每天看一眼总控群有无红色告警；每周跑一次 system_health_check']])

# ===== 9 密钥与安全 =====
h1('九、密钥与安全')
bullet('Coze + DeepSeek 密钥：D:\\AI-Tools\\shared\\coze_config.json（已升级为永久服务令牌）。')
bullet('企业微信告警配置：scripts\\wecom_config.json。')
bullet('旧个人令牌 pat_ 已备份在 coze_config.json.bak_20260919，观察期满后到 Coze 后台删除。')
bullet('切勿把密钥发到群里或截图外发；新令牌异常时可用备份文件一键回滚。')

doc.save(OUT)
print('SAVED:', OUT)
