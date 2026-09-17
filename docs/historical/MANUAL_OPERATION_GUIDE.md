# 手动操作步骤指南

## 概述

由于GitHub和飞书网页版访问不稳定，以下任务需要手动操作完成。本文档提供详细的步骤说明。

---

## 任务1：部署GitHub Actions修复文件

### 背景

GitHub仓库有14个工作流，其中3个因脚本文件不存在而失败：
- 04_review_derive.yml → 调用scripts/review_derive.py（不存在）
- 03_f11_insight.yml → 调用scripts/f11_insight.py（不存在）
- 02_dlq_consumer.yml → 调用scripts/dlq_consumer.py（不存在）

已创建修复后的工作流文件，保存在：
```
D:\AI-Tools\feishu\V13方案增强\github_fix\
├── 04_review_derive_fixed.yml
├── 03_f11_insight_fixed.yml
└── 02_dlq_consumer_fixed.yml
```

### 方法A：通过GitHub网页编辑（推荐，最简单）

#### 步骤1：打开GitHub仓库

1. 打开浏览器，访问：https://github.com/LIziqilin/feishu-automation
2. 确认已登录GitHub账号

#### 步骤2：编辑04_review_derive.yml

1. 访问：https://github.com/LIziqilin/feishu-automation/blob/main/.github/workflows/04_review_derive.yml
2. 点击右上角铅笔图标（Edit this file）
3. 全选现有内容（Ctrl+A），删除
4. 打开本地文件 `D:\AI-Tools\feishu\V13方案增强\github_fix\04_review_derive_fixed.yml`
5. 全选内容（Ctrl+A），复制（Ctrl+C）
6. 粘贴到GitHub编辑框（Ctrl+V）
7. 滚动到底部，在"Commit changes"区域：
   - Commit message：`fix: review_derive改用review_engine.py`
   - 选择"Commit directly to the main branch"
8. 点击"Commit changes"按钮

#### 步骤3：编辑03_f11_insight.yml

1. 访问：https://github.com/LIziqilin/feishu-automation/blob/main/.github/workflows/03_f11_insight.yml
2. 重复步骤2的操作，使用 `03_f11_insight_fixed.yml` 的内容
3. Commit message：`fix: f11_insight改用insight_link.py`

#### 步骤4：编辑02_dlq_consumer.yml

1. 访问：https://github.com/LIziqilin/feishu-automation/blob/main/.github/workflows/02_dlq_consumer.yml
2. 重复步骤2的操作，使用 `02_dlq_consumer_fixed.yml` 的内容
3. Commit message：`fix: 暂时禁用dlq_consumer自动运行（脚本缺失）`

#### 步骤5：验证修复

1. 访问：https://github.com/LIziqilin/feishu-automation/actions
2. 点击左侧"Review Derive (复习派生兜底)"
3. 点击"Run workflow" → 选择main分支 → 点击"Run workflow"
4. 等待工作流运行完成（约10-30秒）
5. 确认状态为 ✅ 成功（绿色勾）
6. 重复测试"F11 Insight Link (洞察关联)"

**预期结果**：
- Review Derive：✅ 成功（调用review_engine.py）
- F11 Insight Link：✅ 成功（调用insight_link.py）
- DLQ Consumer：⏸️ 已禁用自动运行（不会再失败）

---

### 方法B：通过git命令行

#### 步骤1：克隆仓库

```powershell
cd D:\AI-Tools\feishu
git clone https://github.com/LIziqilin/feishu-automation.git
cd feishu-automation
```

#### 步骤2：复制修复文件

```powershell
copy D:\AI-Tools\feishu\V13方案增强\github_fix\04_review_derive_fixed.yml .github\workflows\04_review_derive.yml
copy D:\AI-Tools\feishu\V13方案增强\github_fix\03_f11_insight_fixed.yml .github\workflows\03_f11_insight.yml
copy D:\AI-Tools\feishu\V13方案增强\github_fix\02_dlq_consumer_fixed.yml .github\workflows\02_dlq_consumer.yml
```

#### 步骤3：提交并推送

```powershell
git add .github/workflows/
git commit -m "fix: 修复3个工作流脚本不存在的问题

- 04_review_derive: 改用review_engine.py
- 03_f11_insight: 改用insight_link.py
- 02_dlq_consumer: 暂时禁用自动运行（脚本缺失）"
git push
```

#### 步骤4：验证

参考方法A的步骤5。

---

## 任务2：处理Coze工作流双跑问题

### 背景

Coze中转助手仍在运行，每天09:00发送督办提醒，与V16系统每天07:30早报功能重叠，存在双跑风险。

最新Coze消息（2026-09-11 09:00）：
```
📌 【每日督办提醒】2026-09-11
📚 学习监督：已连续 7 天未学习打卡，请补卡（防止学习链条断裂）
```

### 方案A：在飞书群屏蔽Coze中转助手（推荐，最简单）

#### 步骤1：打开飞书群设置

1. 打开飞书客户端或网页版
2. 进入"个人总控群"
3. 点击右上角"..."（更多）
4. 选择"设置"或"群设置"

#### 步骤2：找到群机器人

1. 在群设置中找到"群机器人"或"机器人"选项
2. 点击进入机器人列表
3. 找到"Coze中转助手"

#### 步骤3：屏蔽或移除机器人

**选项1：屏蔽消息（推荐，保留机器人但不接收消息）**
- 点击"Coze中转助手"
- 找到"消息免打扰"或"屏蔽"选项
- 开启屏蔽

**选项2：移除机器人（彻底移除）**
- 点击"Coze中转助手"
- 点击"移除"或"移出群聊"
- 确认移除

#### 步骤4：验证

1. 等待第二天09:00
2. 确认不再收到Coze的督办提醒
3. 确认V16系统的07:30早报正常推送

---

### 方案B：在Coze平台关闭定时任务

#### 步骤1：登录Coze平台

1. 访问：https://www.coze.cn/
2. 登录账号

#### 步骤2：找到定时任务

1. 进入对应的Bot/工作流
2. 找到"定时任务"或"触发器"设置
3. 找到每天09:00的督办提醒任务

#### 步骤3：关闭或修改定时任务

**选项1：关闭定时任务**
- 关闭定时任务开关
- 保存设置

**选项2：修改时间（避免与V16早报冲突）**
- 将时间从09:00改为其他时间（如12:00）
- 或修改内容，避免重复

#### 步骤4：验证

参考方案A的步骤4。

---

### 方案C：在飞书群设置消息免打扰（临时方案）

如果找不到机器人设置，可以临时设置群消息免打扰：

1. 进入"个人总控群"
2. 点击右上角"..."
3. 找到"消息免打扰"
4. 开启免打扰

**注意**：这会屏蔽群内所有消息，包括V16系统的早报，不推荐长期使用。

---

## 任务3：Phase5自运行3天验证

### 背景

Phase5自运行验证计划：2026-09-11 ~ 2026-09-14（连续3天）
- 第1天（09-11）：✅ 已完成，4/4通过
- 第2天（09-12）：⏳ 待执行
- 第3天（09-13）：⏳ 待执行
- 最终验收（09-14）：⏳ 待执行

### 每日操作步骤

#### 步骤1：运行日检脚本

每天（建议早上08:00后）运行：

```powershell
cd D:\AI-Tools\feishu\V13方案增强\scripts
python phase5_daily_check.py
```

#### 步骤2：检查输出

确认输出显示：
```
============================================================
检查结果汇总
============================================================
  自动化任务: ✅ PASS
  数据层:     ✅ PASS
  功能检查:   ✅ PASS
  系统状态:   ✅ PASS

  总体结果: 🎉 全部通过
```

#### 步骤3：真实交互验证（可选但推荐）

在飞书群中发送以下指令，验证系统响应：

1. **复习反馈**：发送「会」或「不会」
   - 预期：3秒内收到「✓ 已记录」回执，随后收到答案和下次复习日期

2. **知识检索**：发送「知识：间隔重复」
   - 预期：收到知识检索结果

3. **随手记**：发送「洞察：测试洞察」
   - 预期：收到洞察归档确认

4. **快速销项**：发送「完成 测试任务」
   - 预期：收到任务完成确认

#### 步骤4：记录结果

将每日检查结果记录在 `PHASE5_DAILY_CHECKLIST.md` 中，或简单记录日期和是否通过。

---

### 最终验收（09-14）

连续3天验证通过后，执行最终验收：

1. 运行最终系统健康检查：
```powershell
cd D:\AI-Tools\feishu\V13方案增强\scripts
python final_health_check.py
```

2. 确认6/6全部通过

3. 确认3天内无P0告警

4. 确认系统状态文件 `last_success_time` 每日更新

5. 标记Phase5验证完成

---

## 任务4：LLM配置（可选）

详细配置步骤请参考：`D:\AI-Tools\feishu\V13方案增强\LLM_CONFIG_GUIDE.md`

### 快速配置步骤

1. 打开配置文件：`D:\AI-Tools\feishu\V13方案增强\scripts\llm_config.json`
2. 获取DeepSeek API密钥：https://platform.deepseek.com/
3. 修改配置：
   - `"enabled": true`（总开关）
   - `secondary.api_key`: 填入你的API密钥
   - `secondary.enabled`: true
4. 验证配置：
```powershell
cd D:\AI-Tools\feishu\V13方案增强\scripts
python llm_fallback.py status
```
5. 测试：在飞书群发送「知识：你的问题」

---

## 任务优先级与时间估算

| 优先级 | 任务 | 预计耗时 | 难度 |
|--------|------|----------|------|
| 🔴 高 | 部署GitHub Actions修复 | 10分钟 | 简单 |
| 🔴 高 | 处理Coze双跑 | 5分钟 | 简单 |
| 🟡 中 | Phase5日检（每天） | 5分钟/天 | 简单 |
| 🟡 中 | LLM配置（可选） | 10分钟 | 中等 |

---

## 常见问题

### Q1：GitHub网页打不开？

A：
1. 检查网络连接
2. 尝试刷新页面
3. 尝试使用git命令行方法（方法B）
4. 如仍无法访问，可稍后再试

### Q2：找不到群机器人设置？

A：
1. 确保你是群主或管理员
2. 飞书客户端：群设置 → 群机器人
3. 飞书网页版：群设置 → 机器人
4. 如仍找不到，可使用方案C（消息免打扰）临时处理

### Q3：Phase5日检脚本运行失败？

A：
1. 检查Python环境：`python --version`
2. 检查脚本路径是否正确
3. 检查飞书授权是否有效：运行 `lark-cli auth status`
4. 如授权失效，重新授权：`lark-cli auth login`

### Q4：LLM配置后不生效？

A：
1. 参考 `LLM_CONFIG_GUIDE.md` 的"常见问题"部分
2. 运行 `python llm_fallback.py status` 检查状态
3. 确认总开关 `"enabled": true`
4. 确认对应顺位的 `"enabled": true`

---

## 完成标准

所有任务完成后，系统应达到以下状态：

- ✅ GitHub Actions：13个工作流正常运行（DLQ Consumer已禁用）
- ✅ Coze双跑：已处理，不再收到重复的督办提醒
- ✅ Phase5验证：连续3天日检通过，最终验收完成
- ✅ LLM配置（可选）：已配置并测试通过
- ✅ 系统健康：6/6全部通过，无P0告警

---

**如有任何问题，请参考各任务的详细步骤，或检查对应的日志文件。**
