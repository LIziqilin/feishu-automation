# AI系统综合方案（预验收版）
**版本**：V47 | **日期**：2026-09-19 | **定位**：个人效率 + 学习 + 运维一体化 AI 系统
**仓库**：D:\AI-Tools\feishu\V13方案增强 | **远端**：github.com/LIziqilin/feishu-automation（master/main）

---

## 第0章 文档说明
本方案是对系统全部既有文档（V15最终版方案、系统总体方案、系统维保资料、用户指导手册、备份恢复运维手册、Coze渠道融合分析、桥接稳定性评估报告等18份）的综合整合，作为预验收唯一总纲。既有文档作为分册保留，本方案不删除、不冲突。

---

## 第1章 系统定位与边界
- **用户**：单人个人系统，无外部 C 端用户、无多租户、无支付/订单。
- **三大目标域**：①个人效率（任务/洞察/早晚报）②深度学习（错题/复习/画像/掌握度）③工程运维（健康监控/备份/桥接巡检/告警）。
- **设计原则**：本地为主、云端备援；事实源唯一（飞书多维表格）；LLM 可降级；密钥不进前端；写操作可回读验收。

## 第2章 总体架构（五层）
```
入口层：飞书总控群机器人 / 企业微信群机器人 / GitHub Actions 定时 /
        多维表格字段捷径 / AnythingLLM 桌面端 / Windows 计划任务
          ↓
网关层：llm_router（Coze优先→DeepSeek fallback）/ v15_command_router（群指令）
        bridge_health_check（8桥接巡检，已纳入维护链开头）
          ↓
智能层：Coze Bot（复杂对话/工具编排）/ DeepSeek V4 flash（批量+兜底）
        AnythingLLM RAG（5工作区/1939文档/11997向量分片）/ system_rag（轻量自研问答）
          ↓
调度层：Windows 计划任务（18个，8个V16核心）/ GitHub Actions（4 workflow）
          ↓
数据层：飞书多维表格（14表，事实源）/ Obsidian（知识沉淀）/
        本地JSON备份（7轮+小时滚动）/ AnythingLLM SQLite / 系统事件日志
```

## 第3章 数据层：飞书多维表格14张表
BASE_TOKEN=`X8N1bvN3na99dFsyu0gcU8zTnHf`，总控群 CHAT_ID=`oc_1fe154e172ab04622b7ffa810ac172bc`。

| 表 | table_id | 记录数 | 职责 |
|---|---|---|---|
| 任务总表 | tblz3H4lV7PCrBrX | 76 | 任务创建/完成/归档 |
| 学习卡片表 | tblpLvxyYpDJgF92 | 29 | 错题本，含知识点分类_AI/标准答案_AI |
| 复习流水表 | tblbznzCSpPhSz93 | 1599 | 艾宾浩斯复习流水 |
| 用户画像表 | tbldjGffbuPKCe21 | 15 | 画像维度/值/置信度 |
| 系统健康表 | tblxJMndPNtZ7XyG | 1286 | 检查项/主用通道状态/处理状态 |
| 洞察笔记表 | tblaqKBl87V9C0q1 | 40 | 学习/决策洞察 |
| 决策日志表 | tblEA13tWW56lu3K | 3 | 决策复盘 |
| 知识索引表 | tbl0NiUFeQzH2r3n | 770 | 知识索引 |
| 模板与SOP表 | tblRGEeU9M3pPnjT | 22 | 模板/SOP |
| 自动化队列表 | tblOMd9Pfiju2tz0 | 5 | DLQ/异步队列 |
| 系统心跳 | tblJmm0ZIgqlYmyt | 1027 | 心跳记录 |
| 检索日志表 | tblCwZyAhZbmJra2 | 23 | RAG检索审计 |
| 系统事件日志表 | tblPreh1ipB9LQpf | 5846 | 全量事件审计 |
| TEST_结构探测 | tblMiPpkPsEzjTh1 | 0 | 测试空表（可删） |

## 第4章 智能层
### 4.1 LLM 统一网关（llm_router.py）
- 通道1 Coze Bot（bot_id=7678145027994550291，finished Brain个人AI助理，token有效至2026-10-10）。
- 通道2 DeepSeek V4 flash（model=deepseek-chat，OpenAI兼容，api.deepseek.com），Coze失败/额度耗尽自动切换。
- 实测：Coze ping ✅、DeepSeek ping ✅；健康诊断批量任务真实触发过 DeepSeek fallback。
- 成本：个人量级（日增约36条）月均约2~20元。
### 4.2 AnythingLLM（本地RAG）
- 5工作区：默认/Assistant Chats/学习助手Agent/知识库Agent/洞察Agent，模型 deepseek-v4-flash，历史20轮，相似度0.25，topN=4。
- 1939文档/11997向量分片/78聊天/18 Agent调用。
- MCP双通道：Feishu 15工具 + Filesystem 14工具，全部 enabled。
- Agent Flow：learning-pipeline active；STT=local whisper；TTS=native+Piper；9个内置Agent Skill全On；memories表结构就绪（0行，对话后自动写入）。
### 4.3 自研轻量RAG（system_rag.py）
群指令「问系统：xxx」直接检索本地方案/手册，实测问"备份策略"返回准确（7轮滚动/每日03:00/8张表）。

## 第5章 调度层
### 5.1 Windows计划任务（18个，8个V16核心 LastTaskResult=0）
V16_MorningReport(07:30)/NoonReport/EveningReport(20:00)/LearningPoll(轮询)/DailyMaintenance(03:00) + FeishuAssistant-Heartbeat系列；均完整路径、StartWhenAvailable=✓。
### 5.2 GitHub Actions（4 workflow）
| workflow | 触发 | 状态 |
|---|---|---|
| fetch_external_data.yml | cron 北京8/20点 | 唯一真定时，三察推送，失败 alert_fail 报总控群 |
| daily_maintenance/learning_poll/morning_report | workflow_dispatch | 手动备援（wrapper为Windows路径，云端不自动跑，有意为之） |

## 第6章 功能域与脚本封装（165脚本，核心88 + 临时77）
| 域 | 数量 | 代表脚本 |
|---|---|---|
| 核心网关/LLM | 8 | llm_router, coze_gateway, deepseek_gateway, llm_fallback, llm_guard, system_rag, rag_guard, coze_batch_tasks |
| 群指令/路由 | 5 | v15_command_router, v15_features, task_insight_extension, task_ops_cli, task_selfheal |
| 学习系统 | 20 | learning_system, feynman_workflow/verify, wrong_book, mastery_recalc, weekly_learning_report, profile_evolve, knowledge_*, personalized_recommender, pomodoro, memory_hierarchy, cold_archive_auto |
| 三察/推送 | 9 | insight_daily, fetch_external_data, alert_fail, wecom_push, run_morning/noon/evening/poll/maintenance_wrapper |
| 健康/监控/运维 | 14 | bridge_health_check, system_health_check, dashboard_health_check, heartbeat, service_watchdog, slo_monitor, uptime_monitor, dlq_consumer, idempotency, auto_restart, boot_recover |
| 备份/灾备 | 6 | backup_with_rotation, hourly_backup, offsite_replicate, recovery_drill, restore_drill, rollback |
| Obsidian同步 | 3 | obsidian_sync, obsidian_reverse_archive, feishu_obsidian_reconcile |
| 数据/审计/测试 | 17 | data_audit, data_consistency_check, security_audit, cost_audit, invariant_assertions, golden_e2e/write_e2e, redteam_suite, chaos_drill, regression_baseline, acceptance_run, eval_build/run |
| MCP/桥接 | 2 | anyllm_bridge, feishu_mcp_cli |
| 导入/导出/语音 | 4 | import_knowledge, v36_export_tables, todo_export_docx, voice_io |
| 临时调试/一次性修复 | 77 | fix_*/check_*/ops_*/dulwich_*/optimize_*/p0/p1等，建议归档 scripts/archive/ |

## 第7章 群指令契约（飞书总控群）
新建任务：xxx / 搞定了：xxx / 归档 xxx / 洞察：xxx / 智能：xxx（Coze）/ 问系统：xxx（本地RAG）/ 开始闪卡复习 / 系统体检 / 学知识：xxx。

## 第8章 备份与灾备
- backup_with_rotation：每日03:00，7轮滚动，覆盖8张表；hourly_backup每小时（实测最新 hourly_20260919_101540.json）。
- offsite_replicate异地复制；recovery_drill/restore_drill恢复演练；rollback回滚。
- 异地备份目标：飞书云盘 feishuAI 文件夹（folder token TCwefoc9blKcGidfNwrcb60Xnve）。

## 第9章 安全与成本
- 密钥统一存 D:\AI-Tools\shared\coze_config.json（coze token + deepseek_api_key），不进前端、不进git。
- DeepSeek按Token计费，个人量级月2~20元；飞书AI点数耗尽后由DeepSeek兜底，Coze积分同理。
- security_audit/data_consistency_check/invariant_assertions 提供安全与一致性审计。

## 第10章 验收基线（本版实测，详见问题清单）
14个端到端场景全部执行，结果见《预验收问题清单》。
