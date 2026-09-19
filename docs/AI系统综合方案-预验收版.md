# AI系统综合方案（预验收版）
**版本**：V46.1 | **日期**：2026-09-19 | **定位**：个人效率+学习+运维一体化系统

---

## 一、系统定位
个人AI助理系统，服务单人（无外部C端用户），整合：
- **飞书多维表格**（数据事实源，14张表）
- **Obsidian**（知识沉淀）
- **GitHub Actions**（云端定时三察推送）
- **AnythingLLM**（深度RAG问答，5工作区）
- **Coze Bot**（智能对话，群指令「智能：」）
- **DeepSeek V4 flash**（LLM fallback，成本兜底）
- **企业微信**（运维告警）

## 二、核心架构

```
┌─ 入口层 ────────────────────────────────────────┐
│ 飞书总控群(群机器人) / 企微告警 / GitHub定时    │
│ 多维表格字段捷径 / AnythingLLM GUI             │
└──────────────────┬─────────────────────────────┘
                   ↓
┌─ 网关层 ────────────────────────────────────────┐
│ llm_router.py（Coze优先 → DeepSeek fallback）  │
│ bridge_health_check.py（8桥接巡检）            │
└──────────────────┬─────────────────────────────┘
                   ↓
┌─ 服务层 ────────────────────────────────────────┐
│ Coze Bot(复杂对话) / DeepSeek(批量任务)        │
│ AnythingLLM(RAG) / GitHub Actions(三察推送)    │
└──────────────────┬─────────────────────────────┘
                   ↓
┌─ 数据层 ────────────────────────────────────────┐
│ 飞书多维表格(14表) / Obsidian笔记 / SQLite日志  │
└─────────────────────────────────────────────────┘
```

## 三、14张多维表格

| 表 | ID | 用途 | 记录数 |
|---|---|---|---|
| 任务总表 | tblz3H4lV7PCrBrX | 任务管理 | 76 |
| 学习卡片表 | tblpLvxyYpDJgF92 | 错题本 | 29 |
| 复习流水表 | tblbznzCSpPhSz93 | 艾宾浩斯复习 | 1599 |
| 用户画像表 | tbldjGffbuPKCe21 | 个人画像 | 15 |
| 系统健康表 | tblxJMndPNtZ7XyG | 健康监控 | 1286 |
| 洞察笔记表 | tblaqKBl87V9C0q1 | 学习洞察 | 40 |
| 决策日志表 | tblEA13tWW56lu3K | 决策记录 | 3 |
| 知识索引表 | tbl0NiUFeQzH2r3n | 知识索引 | 770 |
| 系统事件日志表 | tblPreh1ipB9LQpf | 事件审计 | 5846 |
| 其余5张 | — | 模板/心跳/检索/自动化/测试 | — |

## 四、脚本体系（140个Python脚本，按用途分）

| 类别 | 核心脚本 | 用途 |
|---|---|---|
| **LLM网关** | llm_router.py / coze_gateway.py / deepseek_gateway.py | 统一LLM调用+fallback |
| **批量任务** | coze_batch_tasks.py / wrong_book.py / weekly_learning_report.py | 错题/周报/画像/健康 |
| **桥接巡检** | bridge_health_check.py / dashboard_health_check.py | 8桥接自检 |
| **三察推送** | insight_daily.py / alert_fail.py | 西安天气+三察洞察 |
| **维护链** | run_maintenance_wrapper.py / backup_with_rotation.py | 每日维护+备份 |
| **学习系统** | learning_system.py / feynman_workflow.py / mastery_recalc.py | 学习闭环 |
| **运维** | service_watchdog.py / health_monitor.py / wecom_push.py | 监控+告警 |
| **文档同步** | obsidian_sync.py / feishu_obsidian_reconcile.py | 飞书↔Obsidian |

## 五、4个GitHub Actions

| Workflow | 触发 | 用途 |
|---|---|---|
| fetch_external_data.yml | 定时(北京8/20点) | 三察推送(唯一真定时) |
| daily_maintenance.yml | 手动备援 | 云端维护 |
| learning_poll.yml | 手动备援 | 群消息轮询 |
| morning_report.yml | 手动备援 | 早报备援 |

## 六、LLM策略
- **主通道**：Coze Bot（finished Brain个人AI助理，复杂对话）
- **Fallback**：DeepSeek V4 flash（Coze失败/额度耗尽自动切）
- **成本**：个人系统量级，月均2~20元

## 七、已验收能力（预验收范围）
- ✅ LLM双通（Coze + DeepSeek）
- ✅ 8桥接全绿
- ✅ 三察推送（GitHub定时）
- ✅ 批量任务（4类）
- ✅ 飞书↔Obsidian同步
- ✅ 企业微信告警
