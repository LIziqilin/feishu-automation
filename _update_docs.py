import re

with open('docs/最终版方案-V49.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 更新版本历史
old_version = """| V49 | 2026-09-21 | 最终版交付，修复学知识/问系统指令，DeepSeek V4 flash 路由 |"""

new_version = """| V49.1 | 2026-09-22 | 修复洞察指令被自然语态销项误判、到期提醒每日去重、学知识指令无反应 |
| V49 | 2026-09-21 | 最终版交付，修复学知识/问系统指令，DeepSeek V4 flash 路由 |"""

content = content.replace(old_version, new_version)

# 在版本历史后面加V49.1修复记录
old_end = "| V33 | 2026-09-15 | 结构化洞察归档、去重 |"

new_end = """| V33 | 2026-09-15 | 结构化洞察归档、去重 |

---

## 八、V49.1 修复记录（2026-09-22）

### 8.1 群指令无反应问题修复

| 问题 | 根因 | 修复方案 | 验证 |
|------|------|----------|------|
| 洞察指令被误判为完成任务 | "洞察：...归档"包含"归档"关键词，被自然语态销项逻辑误判 | 自然语态销项前先检查是否洞察指令，是则跳过 | ✅ 实测通过 |
| 学知识指令无反应 | is_task_instruction把"学知识"当任务指令跳过knowledge_extension | 移除"学知识"判断，knowledge_extension改用llm_router.chat() | ✅ 实测通过 |
| 待办任务每5分钟重复推送 | 每次轮询都调send_due_reminder(3)，无去重 | 加.due_reminder_state.json每日去重 | ✅ 实测通过 |
| "完成：写洞察：xxx"被当完成任务 | is_complete_command先匹配"完成："前缀 | handle_extension_command先剥离"完成："前缀再判断洞察 | ✅ 实测通过 |

### 8.2 轮询任务停摆修复

| 问题 | 根因 | 修复方案 |
|------|------|----------|
| V16_LearningPoll轮询停摆 | 触发器Repetition.Duration=P1D（只持续1天） | 改为无限重复（Duration=$null, StopAtDurationEnd=$false） |

### 8.3 运维告警修复

| 问题 | 根因 | 修复方案 |
|------|------|----------|
| Ollama连接被拒绝告警 | health_monitor把Ollama当必需服务 | Ollama和AnythingLLM标记为optional=True |"""

content = content.replace(old_end, new_end)

with open('docs/最终版方案-V49.md', 'w', encoding='utf-8') as f:
    f.write(content)

print('OK: 最终版方案已更新')
