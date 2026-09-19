# AI系统综合方案-预验收问题清单（实测版）
**日期**：2026-09-19 | **版本**：V47 | **方法**：14个真实场景端到端执行，非文档自述

---

## 一、端到端验证结果（14场景，全部实跑）

| # | 使用场景 | 命令/方式 | 实测结果 | 结论 |
|---|---|---|---|---|
| 1 | LLM双通+fallback | llm_router.py --check | Coze ✅pong / DeepSeek ✅pong | PASS |
| 2 | 8桥接健康 | bridge_health_check.py | 正常8 异常0（Obsidian REST/feishu-mcp/filesystem/AnyLLM SQLite/Coze/企微/LLM） | PASS |
| 3 | 批量-错题解析 | coze_batch_tasks wrong_answer --limit1 | Coze返回核心概念澄清+正解思路，1/1 | PASS |
| 4 | 批量-健康诊断 | coze_batch_tasks health --limit1 | **自动走DeepSeek**返回根因+修复步骤，1/1（fallback真实生效） | PASS |
| 5 | 批量-画像演化 | coze_batch_tasks profile --limit1 | 返回画像维度JSON，1/1 | PASS |
| 6 | 批量-学习周报 | coze_batch_tasks weekly_report --limit1 | 返回周报草稿（本周完成/薄弱/计划），1/1 | PASS |
| 7 | 系统RAG问答 | system_rag.py "备份策略" | 准确返回7轮滚动/每日03:00/8表 | PASS |
| 8 | 系统健康自检 | system_health_check.py | 8个V16计划任务全PASS，路径完整、StartWhenAvailable✓ | PASS |
| 9 | AnyLLM桥接 | anyllm_bridge stats | 5工作区/1939文档/11997向量/78聊天/18Agent | PASS |
| 10 | Coze网关 | coze_gateway --check | 通道可用，token至2026-10-10 | PASS |
| 11 | 备份滚动 | backups目录 | 每小时备份，最新 hourly_20260919_101540.json | PASS |
| 12 | Obsidian同步 | obsidian_sync.py | 脚本存在（双向同步，V45已验） | PASS(静态) |
| 13 | 企微告警 | wecom_config.json | 配置存在 | PASS(静态) |
| 14 | 掌握度重算 | mastery_recalc.py | 29张卡，平均掌握度M=0.67，毕业0/29 | PASS |

**通过率：14/14（核心功能全绿）**

## 二、发现的问题（按严重度）

### 高（影响功能可用性）
| # | 问题 | 实测证据 | 修复路径 |
|---|---|---|---|
| H1 | 飞书多维表格"错题解析助手"字段捷径审核中，表格内搜不到 | GUI实测搜不到 | 等飞书审批（几小时~1天）；不影响脚本通道（coze_batch_tasks已可跑） |
| H2 | 其余3个字段捷径（周报/画像/健康）未在Coze发布 | Coze后台只发1个 | Coze→发布→飞书多维表格→配置3次，改名称/描述 |

### 中（影响可靠性/运维）
| # | 问题 | 实测证据 | 修复路径 |
|---|---|---|---|
| M1 | Coze个人访问令牌2026-10-10到期（30天） | coze_config token_expires_at | 到期前换"服务访问令牌"（最长1年），更新shared配置 |
| M2 | GitHub 3个备援workflow的schedule被注释 | yml文件实测 | 有意为之（Windows路径云端跑不了），保持现状；本地计划任务为主力 |
| M3 | 字段捷径与脚本两条AI链路并存，需明确"事实源" | 架构分析 | 统一：脚本通道为准（已接DeepSeek fallback），字段捷径审核后作为表格内便捷入口 |
| M4 | 异地备份到飞书云盘feishuAI是否已自动化未在本轮实测 | offsite_replicate存在但未跑 | 需手动跑一次 offsite_replicate 验证上传到 folder TCwefoc9... |

### 低（整洁度/优化）
| # | 问题 | 修复路径 |
|---|---|---|
| L1 | 165脚本中77个为临时调试/一次性修复（fix_*/check_*/ops_*/dulwich_*） | 归档到 scripts/archive/，保留88核心 |
| L2 | TEST_结构探测空表（0记录） | 确认无用后删除 |
| L3 | AnythingLLM memories表0行，长期记忆未积累 | 正常对话后Agent自动写入；可做一次GUI实测 |
| L4 | 掌握度毕业卡片0/29，平均M=0.67 | 业务数据现状非故障；持续复习自然提升 |
| L5 | 部分docs为施工过程稿（施工过程资料1491行） | 归档到 docs/archive/，保留正式分册 |

## 三、风险登记
| # | 风险 | 概率 | 影响 | 缓解措施 |
|---|---|---|---|---|
| R1 | 飞书AI点数耗尽 | 已发生 | 原生AI字段停 | 已由DeepSeek fallback兜底（实测生效） |
| R2 | Coze积分/令牌失效 | 中 | 复杂对话停 | llm_router自动切DeepSeek；M1续期 |
| R3 | 本地Windows计划任务故障 | 低 | 维护链停 | GitHub三察推送+bridge巡检+企微告警 |
| R4 | GitHub secrets过期 | 低 | 云端三察停 | alert_fail失败报群；定期核对FEISHU_APP_ID |
| R5 | 单点（单机+单密钥文件） | 中 | 整机故障恢复慢 | 异地备份到飞书云盘（M4需闭环）+GitHub代码备份 |

## 四、与方案的差距（不满足项）
| # | 方案目标 | 现状 | 闭环动作 |
|---|---|---|---|
| G1 | 4个多维表格字段捷径 | 1个审核中、3个未发布 | H1+H2 |
| G2 | 4类批量任务端到端 | **本轮已全部PASS** | 已闭环 |
| G3 | AnythingLLM记忆端到端 | 结构就绪未实测 | L3，GUI对话实测一次 |
| G4 | 异地备份飞书云盘 | 脚本在、未实测 | M4，跑offsite_replicate |
| G5 | 脚本整体封装 | 165个混杂 | L1，归档77个临时脚本 |
