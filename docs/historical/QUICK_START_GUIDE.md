# 一键操作指南（15 分钟完成所有待办）

## 概述

当前系统核心功能已全部可用，剩余 4 项待办需要手动操作（主要是网页交互）。本指南提供最简洁的操作步骤，预计 15 分钟内全部完成。



***

## 任务 1：部署 GitHub Actions 修复（5 分钟）

### 背景

GitHub 仓库有 3 个工作流因脚本不存在而失败，修复文件已创建在本地。

### 操作步骤

#### 步骤 1：打开 GitHub 仓库



1. 访问：[https://github.com/LIziqilin/feishu-automation](https://github.com/LIziqilin/feishu-automation)

2. 确认已登录

#### 步骤 2：编辑 04\_review\_derive.yml



1. 访问：[https://github.com/LIziqilin/feishu-automation/blob/main/.github/workflows/04\_review\_derive.yml](https://github.com/LIziqilin/feishu-automation/blob/main/.github/workflows/04_review_derive.yml)

2. 点击右上角铅笔图标（Edit this file）

3. 全选现有内容（Ctrl+A），删除

4. 打开本地文件：`D:\AI-Tools\feishu\V13方案增强\github_fix\04_review_derive_fixed.yml`

5. 全选（Ctrl+A）→ 复制（Ctrl+C）→ 粘贴到 GitHub（Ctrl+V）

6. 滚动到底部，Commit message 填：`fix: review_derive改用review_engine.py`

7. 点击 "Commit changes"

#### 步骤 3：编辑 03\_f11\_insight.yml



1. 访问：[https://github.com/LIziqilin/feishu-automation/blob/main/.github/workflows/03\_f11\_insight.yml](https://github.com/LIziqilin/feishu-automation/blob/main/.github/workflows/03_f11_insight.yml)

2. 重复步骤 2，使用 `03_f11_insight_fixed.yml` 的内容

3. Commit message：`fix: f11_insight改用insight_link.py`

#### 步骤 4：编辑 02\_dlq\_consumer.yml



1. 访问：[https://github.com/LIziqilin/feishu-automation/blob/main/.github/workflows/02\_dlq\_consumer.yml](https://github.com/LIziqilin/feishu-automation/blob/main/.github/workflows/02_dlq_consumer.yml)

2. 重复步骤 2，使用 `02_dlq_consumer_fixed.yml` 的内容

3. Commit message：`fix: 暂时禁用dlq_consumer自动运行（脚本缺失）`

#### 步骤 5：验证（可选）



1. 访问：[https://github.com/LIziqilin/feishu-automation/actions](https://github.com/LIziqilin/feishu-automation/actions)

2. 点击 "Review Derive (复习派生兜底)"

3. 点击 "Run workflow" → 选择 main → 点击 "Run workflow"

4. 等待 10-30 秒，确认状态为 ✅ 成功

**预期结果**：13 个工作流正常运行（DLQ Consumer 已禁用）



***

## 任务 2：处理 Coze 双跑（3 分钟）

### 背景

Coze 中转助手每天 09:00 发送督办提醒，与 V16 系统 07:30 早报功能重叠。

### 推荐方案：在飞书群屏蔽 Coze 中转助手

#### 步骤 1：打开飞书群



1. 打开飞书客户端或网页版

2. 进入 "个人总控群"

#### 步骤 2：打开群设置



1. 点击右上角 "..."（更多）

2. 选择 "设置" 或 "群设置"

#### 步骤 3：找到群机器人



1. 在群设置中找到 "群机器人" 或 "机器人"

2. 点击进入机器人列表

#### 步骤 4：屏蔽 Coze 中转助手



1. 找到 "Coze 中转助手"

2. 点击进入

3. 开启 "消息免打扰" 或 "屏蔽"

* 或点击 "移除"（彻底移除，不推荐，可能影响其他功能）

**预期结果**：不再收到 Coze 的 09:00 督办提醒，V16 系统 07:30 早报正常推送



***

## 任务 3：Phase5 自运行 3 天验证（每天 1 分钟）

### 背景

Phase5 验证周期：2026-09-11 \~ 2026-09-14



* 第 1 天（09-11）：✅ 已完成，4/4 通过

* 第 2 天（09-12）：⏳ 待执行

* 第 3 天（09-13）：⏳ 待执行

### 每日操作步骤

#### 每天早上运行日检脚本



```
cd D:\AI-Tools\feishu\V13方案增强\scripts

python phase5\_daily\_check.py
```

#### 确认输出

看到以下内容即表示通过：



```
\============================================================

检查结果汇总

\============================================================

&#x20; 自动化任务: ✅ PASS

&#x20; 数据层:     ✅ PASS

&#x20; 功能检查:   ✅ PASS

&#x20; 系统状态:   ✅ PASS

&#x20; 总体结果: 🎉 全部通过
```

#### 可选：真实交互验证

在飞书群发送以下指令，确认系统响应：



1. 发送「会」→ 确认收到「✓ 已记录」回执

2. 发送「知识：测试」→ 确认收到知识检索结果



***

## 任务 4：LLM 配置（可选，5 分钟）

### 背景

如需使用 LLM 问答功能（ALLM→DeepSeek→Coze 三顺位降级），需配置 API 密钥。当前默认禁用，使用纯飞书表格检索。

### 推荐方案：配置 DeepSeek API（月成本约 6 元）

#### 步骤 1：获取 API 密钥



1. 访问：[https://platform.deepseek.com/](https://platform.deepseek.com/)

2. 注册 / 登录

3. 进入 "API Keys" 页面

4. 点击 "Create API Key"，复制密钥（sk-xxx）

5. 充值（最低 10 元，约可用 50 天）

**注意**：从飞书群告警看到当前余额 0.00 元，需先充值。

#### 步骤 2：编辑配置文件



1. 打开：`D:\AI-Tools\feishu\V13方案增强\scripts\llm_config.json`

2. 修改以下内容：

* `"enabled": true`（总开关）

* `secondary.api_key`: 填入你的 API 密钥

* `secondary.enabled`: true

1. 保存文件

#### 步骤 3：验证配置



```
cd D:\AI-Tools\feishu\V13方案增强\scripts

python llm\_fallback.py status
```

确认输出显示：



```
总开关: ✅ 启用

第二顺位: DeepSeek API

&#x20; 状态: ✅ 启用

&#x20; 配置: ✅ 已配置API密钥
```

#### 步骤 4：测试

在飞书群发送：



```
知识：间隔重复学习的原理是什么？
```

确认收到 LLM 生成的回答（而不只是表格检索结果）。



***

## 完成标准

所有任务完成后，系统应达到以下状态：



* ✅ GitHub Actions：13 个工作流正常运行（DLQ Consumer 已禁用）

* ✅ Coze 双跑：已处理，不再收到重复的督办提醒

* ✅ Phase5 验证：连续 3 天日检通过，最终验收完成

* ✅ LLM 配置（可选）：已配置并测试通过

* ✅ 系统健康：6/6 全部通过，无 P0 告警



***

## 快速参考

### 常用命令



```
\# 系统健康检查

cd D:\AI-Tools\feishu\V13方案增强\scripts

python final\_health\_check.py

\# Phase5日检

python phase5\_daily\_check.py

\# LLM状态检查

python llm\_fallback.py status

\# 手动运行poll轮询

python run\_poll\_wrapper.py

\# 手动运行早报

python run\_morning\_wrapper.py

\# 手动运行维护

python run\_maintenance\_wrapper.py
```

### 关键文件路径



| 文件          | 路径                                                             |
| ----------- | -------------------------------------------------------------- |
| GitHub 修复文件 | `D:\AI-Tools\feishu\V13方案增强\github_fix\`                       |
| LLM 配置      | `D:\AI-Tools\feishu\V13方案增强\scripts\llm_config.json`           |
| LLM 配置指南    | `D:\AI-Tools\feishu\V13方案增强\LLM_CONFIG_GUIDE.md`               |
| 手动操作指南      | `D:\AI-Tools\feishu\V13方案增强\MANUAL_OPERATION_GUIDE.md`         |
| 施工完成报告      | `D:\AI-Tools\feishu\V13方案增强\CONSTRUCTION_COMPLETION_REPORT.md` |



***

**如有任何问题，请参考各任务的详细步骤，或检查对应的日志文件。**