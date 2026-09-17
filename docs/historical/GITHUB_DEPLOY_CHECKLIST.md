# GitHub部署检查清单与手动部署步骤

## 当前状态

### 已完成
- ✅ GitHub仓库已创建：`LIziqilin/feishu-automation`
- ✅ 已有早报工作流 `14_morning_brief.yml` 在运行（7次运行记录）
- ✅ 本地3个GitHub Actions工作流文件已创建
- ✅ 本地部署脚本已创建（PowerShell和批处理版本）
- ✅ 本地部署指南已创建
- ✅ 本地.gitignore文件已创建

### 待完成
- ⚠️ 确认我们的3个工作流文件是否已推送到GitHub
- ⚠️ 配置GitHub Secrets（4个）
- ⚠️ 检查是否有重复的工作流（避免双跑）
- ⚠️ 测试工作流运行
- ⚠️ 配置飞书自建应用（应用身份）

---

## 第一步：确认本地文件

在 `D:\AI-Tools\feishu\V13方案增强` 目录下，确认以下文件存在：

```
.github/
  workflows/
    morning_report.yml      # 早报推送（每天07:30北京时间）
    daily_maintenance.yml   # 日常维护（每天03:00北京时间）
    learning_poll.yml       # 群消息轮询（每15分钟）

deploy_to_github.ps1       # 一键部署脚本（PowerShell版本，推荐）
deploy_to_github.bat       # 一键部署脚本（批处理版本）
GITHUB_ACTIONS_DEPLOY_GUIDE.md  # 详细部署指南
.gitignore                 # git忽略文件
```

---

## 第二步：推送代码到GitHub

### 方法一：使用一键部署脚本（推荐）

1. 右键点击 `deploy_to_github.ps1`
2. 选择 "使用PowerShell运行"
3. 等待脚本自动完成git初始化、提交和推送

### 方法二：手动执行git命令

打开PowerShell或Git Bash，执行以下命令：

```powershell
cd D:\AI-Tools\feishu\V13方案增强

# 初始化git仓库（如果还没有）
git init

# 添加所有文件
git add .

# 提交
git commit -m "V16学习系统 - GitHub Actions关机永续版"

# 添加远程仓库
git remote add origin https://github.com/LIziqilin/feishu-automation.git

# 切换到main分支
git branch -M main

# 推送到GitHub
git push -u origin main --force
```

### 常见问题

**问题1：Permission denied（权限拒绝）**
- 解决：以管理员身份运行PowerShell或Git Bash
- 或者：检查 `.git` 目录的权限设置

**问题2：Authentication failed（认证失败）**
- 解决：配置git凭据管理器，或使用Personal Access Token
- 命令：`git config --global credential.helper manager`

**问题3：网络连接超时**
- 解决：检查网络连接，或配置代理
- 命令：`git config --global http.proxy http://proxy:port`

---

## 第三步：检查GitHub仓库文件

推送成功后，访问：
```
https://github.com/LIziqilin/feishu-automation
```

检查以下内容：
1. `.github/workflows/` 目录是否存在
2. 3个工作流文件是否都在仓库中
3. 其他文件是否正确推送

---

## 第四步：配置GitHub Secrets

访问：
```
https://github.com/LIziqilin/feishu-automation/settings/secrets/actions
```

点击 "New repository secret"，依次添加以下4个Secrets：

| Secret名称 | 值 | 说明 |
|------------|-----|------|
| `BASE_TOKEN` | `X8N1bvN3na99dFsyu0gcU8zTnHf` | 飞书多维表格Base Token |
| `CHAT_ID` | `oc_1fe154e172ab04622b7ffa810ac172bc` | 飞书群Chat ID |
| `LARK_APP_ID` | 你的飞书自建应用App ID | 飞书应用身份 |
| `LARK_APP_SECRET` | 你的飞书自建应用App Secret | 飞书应用密钥 |

**重要**：
- Secrets添加后不可查看，只能修改或删除
- `LARK_APP_ID` 和 `LARK_APP_SECRET` 需要在飞书开放平台创建自建应用后获取

---

## 第五步：检查重复工作流（重要！）

您的仓库已有一个早报工作流 `14_morning_brief.yml` 在运行。
我们创建的工作流是 `morning_report.yml`。

**这两个工作流可能会重复推送早报，导致双跑！**

### 检查步骤

1. 访问：`https://github.com/LIziqilin/feishu-automation/actions`
2. 查看左侧工作流列表
3. 如果有多个早报相关的工作流，需要决定保留哪一个

### 解决方案

**方案A：保留现有的 `14_morning_brief.yml`，删除我们的 `morning_report.yml`**
- 如果现有的工作流已经正常运行，建议保留
- 删除本地 `.github/workflows/morning_report.yml` 文件
- 重新推送代码

**方案B：使用我们的 `morning_report.yml`，禁用现有的 `14_morning_brief.yml`**
- 在GitHub Actions页面，选择 `14_morning_brief.yml`
- 点击 "..." → "Disable workflow"
- 保留我们的工作流

**方案C：合并两个工作流**
- 检查两个工作流的功能是否相同
- 如果功能相同，保留一个即可
- 如果功能不同，可以都保留，但需要确保不会重复推送

---

## 第六步：配置飞书自建应用

GitHub Actions使用**应用身份（bot）**，需要配置飞书自建应用。

### 创建飞书自建应用

1. 访问：https://open.feishu.cn
2. 登录后，点击 "创建应用" → "自建应用"
3. 填写应用名称（如 "V16学习系统"）
4. 点击 "创建"

### 开通权限

在应用详情页，点击 "权限管理"，开通以下权限：
- `im:message`（读取群消息）
- `im:message:send_as_bot`（发送消息）
- `base:record:read`（读取多维表格记录）
- `base:record:write`（写入多维表格记录）

### 获取App ID和App Secret

在应用详情页，点击 "凭证与基础信息"：
- 复制 `App ID`（如 `cli_xxxxxxxxxxxxxxxx`）
- 复制 `App Secret`（如 `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`）

将这两个值配置到GitHub Secrets的 `LARK_APP_ID` 和 `LARK_APP_SECRET`。

### 将应用添加到群和多维表格

1. **添加到群**：
   - 打开飞书群 "个人总控群"
   - 点击群设置 → "群机器人" → "添加机器人"
   - 搜索并添加您创建的应用

2. **添加到多维表格协作者**：
   - 打开多维表格 "飞书智能助理系统"
   - 点击 "分享" → "添加协作者"
   - 搜索并添加您创建的应用，设置为 "可编辑" 权限

---

## 第七步：测试工作流

### 测试早报推送

1. 访问：`https://github.com/LIziqilin/feishu-automation/actions`
2. 选择 "V16 早报推送"（或 `morning_report.yml`）
3. 点击 "Run workflow" → "Run workflow"
4. 等待工作流运行完成
5. 检查飞书群是否收到早报消息
6. 检查工作流日志是否有错误

### 测试日常维护

1. 选择 "V16 日常维护"（或 `daily_maintenance.yml`）
2. 点击 "Run workflow" → "Run workflow"
3. 等待工作流运行完成
4. 检查飞书多维表格数据是否正常
5. 检查Artifacts中的备份文件

### 测试群消息轮询

1. 选择 "V16 群消息轮询"（或 `learning_poll.yml`）
2. 点击 "Run workflow" → "Run workflow"
3. 在飞书群发送一条测试消息（如 "会"）
4. 等待工作流运行完成
5. 检查飞书群是否收到回执
6. 检查多维表格流水是否新增记录

---

## 第八步：监控工作流运行

### 查看工作流运行状态

访问：`https://github.com/LIziqilin/feishu-automation/actions`

可以看到：
- 所有工作流的运行状态
- 每次运行的耗时
- 成功/失败次数
- 运行日志

### 设置通知

如果工作流失败，GitHub会自动发送邮件通知。

也可以在工作流中配置Slack/飞书通知（需要额外配置）。

---

## 推荐混合部署方案

考虑到成本和延迟，推荐使用混合部署方案：

| 功能 | 部署位置 | 原因 |
|------|----------|------|
| 早报推送 | **GitHub Actions** | 每天1次，成本低，可接受延迟 |
| 日常维护 | **GitHub Actions** | 每天1次，成本低，可接受延迟 |
| 群消息轮询 | **本地Windows任务计划** | 每5分钟，GitHub成本太高（每月5760分钟，超出免费额度） |

### 配置方法

1. 在GitHub Actions中，只启用早报推送和日常维护工作流
2. 禁用群消息轮询工作流（`learning_poll.yml`）
3. 保留本地Windows任务计划的群消息轮询（V16_LearningPoll）

### 优势

- 核心功能（早报、维护）实现关机永续
- 轮询功能保留本地，降低成本和延迟
- 备份双重存储（GitHub Artifacts + 本地），更安全

---

## 常见问题排查

### Q1：工作流运行失败，提示 "lark-cli: command not found"

**原因**：工作流中安装lark-cli的步骤失败。

**解决**：
1. 检查工作流日志中的安装步骤
2. 确认npm安装是否成功
3. 可以尝试使用其他安装方式

### Q2：工作流运行失败，提示 "权限不足"

**原因**：飞书应用的权限配置不正确，或应用未添加到群/多维表格。

**解决**：
1. 检查飞书应用的权限是否已开通
2. 检查应用是否已添加到群
3. 检查应用是否已添加到多维表格协作者
4. 检查App ID和App Secret是否正确

### Q3：工作流运行成功，但飞书群没有收到消息

**原因**：可能是消息发送失败，或发送到了错误的群。

**解决**：
1. 检查工作流日志中的消息发送步骤
2. 确认CHAT_ID是否正确
3. 确认应用是否已添加到群
4. 检查飞书应用的 `im:message:send_as_bot` 权限是否已开通

### Q4：群消息轮询工作流成本太高

**原因**：每15分钟运行一次，每月约2880分钟，接近免费额度上限。

**解决**：
1. 改用混合部署方案，轮询保留本地
2. 或增加轮询间隔（如每30分钟或每小时）
3. 或升级GitHub Pro计划（每月3000分钟）

### Q5：如何回滚到本地Windows任务计划？

**解决**：
1. 在GitHub Actions页面，禁用所有工作流
2. 确保本地Windows任务计划已启用
3. 检查本地系统是否正常运行

---

## 部署完成检查清单

部署完成后，逐项检查：

- [ ] 代码已成功推送到GitHub
- [ ] 3个工作流文件都在仓库中
- [ ] 4个GitHub Secrets已配置
- [ ] 飞书自建应用已创建
- [ ] 飞书应用权限已开通
- [ ] 飞书应用已添加到群
- [ ] 飞书应用已添加到多维表格协作者
- [ ] 重复工作流已处理（避免双跑）
- [ ] 早报推送工作流测试通过
- [ ] 日常维护工作流测试通过
- [ ] 群消息轮询工作流测试通过（如果启用）
- [ ] 混合部署方案已配置（如果使用）
- [ ] 工作流运行监控已设置

---

**文档版本**: V1.0
**创建时间**: 2026-09-11
**适用版本**: V16交付保障版
