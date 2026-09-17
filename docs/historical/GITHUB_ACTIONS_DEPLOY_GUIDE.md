# GitHub Actions 关机永续部署指南

## 概述

本指南说明如何将V16学习系统从Windows任务计划迁移到GitHub Actions，实现真正的"关机永续"（不依赖电脑开机）。

### 工作流清单

| 工作流 | 触发时间 | 功能 | 文件 |
|--------|----------|------|------|
| 早报推送 | 每天07:30（北京时间） | 推送每日复习早报 | `.github/workflows/morning_report.yml` |
| 日常维护 | 每天03:00（北京时间） | derive全量重算 + 7轮滚动备份 + 系统状态更新 | `.github/workflows/daily_maintenance.yml` |
| 群消息轮询 | 每15分钟 | 轮询群消息，解析答题指令 | `.github/workflows/learning_poll.yml` |

---

## 部署步骤

### 第一步：创建GitHub仓库

1. 登录 https://github.com
2. 点击右上角 "+" → "New repository"
3. 仓库名称：`v16-learning-system`（或自定义）
4. 选择"Private"（私有仓库，保护凭据）
5. 点击"Create repository"

### 第二步：配置GitHub Secrets

在GitHub仓库页面：
1. 点击 "Settings" → "Secrets and variables" → "Actions"
2. 点击 "New repository secret"，依次添加以下Secrets：

| Secret名称 | 值 | 说明 |
|------------|-----|------|
| `BASE_TOKEN` | `X8N1bvN3na99dFsyu0gcU8zTnHf` | 飞书多维表格Base Token |
| `CHAT_ID` | `oc_1fe154e172ab04622b7ffa810ac172bc` | 飞书群Chat ID |
| `LARK_APP_ID` | 你的飞书应用App ID | 飞书自建应用App ID |
| `LARK_APP_SECRET` | 你的飞书应用App Secret | 飞书自建应用App Secret |

**重要**：Secrets添加后不可查看，只能修改或删除。

### 第三步：推送代码到GitHub

在本地项目目录（`D:\AI-Tools\feishu\V13方案增强`）执行：

```powershell
# 初始化git仓库
git init

# 添加所有文件
git add .

# 提交
git commit -m "V16学习系统 - GitHub Actions关机永续版"

# 添加远程仓库
git remote add origin https://github.com/你的用户名/v16-learning-system.git

# 推送到GitHub
git branch -M main
git push -u origin main
```

### 第四步：测试工作流

1. 在GitHub仓库页面，点击 "Actions"
2. 选择 "V16 早报推送"（或其他工作流）
3. 点击 "Run workflow" → "Run workflow" 手动触发
4. 等待工作流运行完成，查看日志

### 第五步：验证功能

1. 检查飞书群是否收到早报消息
2. 检查飞书多维表格数据是否正常
3. 检查GitHub Actions的Artifacts中的日志和备份文件

---

## 重要注意事项

### 1. 用户身份 vs 应用身份

**当前本地系统**：使用用户身份（`--as user`），需要用户授权token。

**GitHub Actions**：使用应用身份（bot），需要飞书自建应用的App ID和App Secret。

**差异**：
- 应用身份需要被添加到飞书群和多维表格的协作者中
- 应用身份的权限范围由应用的scopes决定
- 应用身份发送的消息显示为应用名称，不是用户名称

**配置方法**：
1. 在飞书开放平台（https://open.feishu.cn）创建自建应用
2. 开通以下权限：
   - `im:message`（读取群消息）
   - `im:message:send_as_bot`（发送消息）
   - `base:record:read`（读取多维表格记录）
   - `base:record:write`（写入多维表格记录）
3. 将应用添加到"个人总控群"
4. 将应用添加到"飞书智能助理系统"多维表格的协作者（可编辑权限）

### 2. 成本考虑

GitHub Actions免费额度：
- 私有仓库：每月2000分钟
- 每个工作流运行约1-2分钟（安装lark-cli+Python依赖）

**月度成本估算**：
- 早报推送：30次 × 2分钟 = 60分钟
- 日常维护：30次 × 2分钟 = 60分钟
- 群消息轮询：96次/天 × 30天 × 2分钟 = 5760分钟（超出免费额度！）

**建议**：
- 群消息轮询不建议在GitHub Actions中运行（成本太高）
- 可以将轮询间隔改为每小时（`0 * * * *`），降低成本
- 或者保留本地Windows任务计划运行轮询，只将早报和维护迁移到GitHub Actions

### 3. 延迟考虑

GitHub Actions的延迟：
- 定时触发可能有5-15分钟延迟（GitHub调度机制）
- 工作流冷启动需要1-2分钟（安装依赖）

**影响**：
- 早报推送可能在07:30-07:45之间到达
- 群消息轮询可能有15-20分钟延迟

### 4. 数据安全

- GitHub Secrets是加密存储的，只有仓库协作者可以访问
- 建议使用私有仓库
- 不要将凭据提交到代码中（使用Secrets）
- 定期轮换App Secret

---

## 混合部署方案（推荐）

考虑到成本和延迟，推荐使用混合部署方案：

| 功能 | 部署位置 | 原因 |
|------|----------|------|
| 早报推送 | GitHub Actions | 每天1次，成本低，可接受延迟 |
| 日常维护 | GitHub Actions | 每天1次，成本低，可接受延迟 |
| 群消息轮询 | 本地Windows任务计划 | 每5分钟，成本高，需要低延迟 |
| 备份存储 | GitHub Artifacts + 本地 | 双重备份，更安全 |

**优势**：
- 核心功能（早报、维护）实现关机永续
- 轮询功能保留本地，降低成本和延迟
- 备份双重存储，更安全

---

## 回滚方案

如果GitHub Actions出现问题，可以随时回滚到本地Windows任务计划：

1. 禁用GitHub Actions工作流（Settings → Actions → Disable Actions）
2. 确保本地Windows任务计划已启用
3. 检查本地系统是否正常运行

---

## 常见问题

### Q1：工作流运行失败，提示"lark-cli: command not found"

A：检查工作流中的安装步骤是否正确执行。可以在工作流日志中查看安装输出。

### Q2：工作流运行失败，提示"权限不足"

A：检查飞书应用的权限配置，确保已开通所需scopes，并将应用添加到群和多维表格的协作者中。

### Q3：群消息轮询成本太高怎么办？

A：可以将轮询间隔改为每小时（`0 * * * *`），或者保留本地Windows任务计划运行轮询。

### Q4：如何查看工作流运行日志？

A：在GitHub仓库页面，点击 "Actions" → 选择工作流 → 选择运行记录 → 查看日志。

### Q5：如何下载备份文件？

A：在工作流运行记录页面，点击 "Artifacts" → 下载 "daily-backup"。

---

## 部署检查清单

- [ ] 创建GitHub私有仓库
- [ ] 配置4个GitHub Secrets（BASE_TOKEN、CHAT_ID、LARK_APP_ID、LARK_APP_SECRET）
- [ ] 创建飞书自建应用，开通所需权限
- [ ] 将飞书应用添加到群和多维表格协作者
- [ ] 推送代码到GitHub
- [ ] 手动触发早报推送工作流，验证功能
- [ ] 手动触发日常维护工作流，验证功能
- [ ] 检查备份文件是否正常生成
- [ ] 决定群消息轮询的部署位置（GitHub或本地）
- [ ] 配置回滚方案

---

**文档版本**: V1.0
**创建时间**: 2026-09-11
**适用版本**: V16交付保障版
