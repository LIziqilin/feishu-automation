---
name: feishu-task-ops
description: "飞书任务总表的快速销项、归档、新建与查询：把『完成/归档/新建任务』等自然语言指令落到飞书多维表格，并回读确认。"
version: 1.0.0
author: 紫麒麟智能系统
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [Feishu, Task, 销项, 归档, Productivity, 多维表格]
    related_skills: [obsidian, note-taking]
prerequisites:
  commands: [python]
  files: ["D:\\AI-Tools\\feishu\\V13方案增强\\scripts\\task_ops_cli.py", "v15_features.py"]
---

# 飞书任务快速销项 / 归档（feishu-task-ops）

把用户的自然语言任务操作，确定性地落到飞书多维表格「任务总表」，并**回读确认**，不凭接口返回声称成功。

## When to Use

- 用户说「完成：xxx / 搞定 xxx / 销项 xxx / done xxx」→ 把任务置为「已完成」并填实际完成日期
- 用户说「归档：xxx」→ 把任务置为「已归档」
- 用户说「新建/创建/记录任务：xxx」→ 在任务总表新建一条待办
- 用户问「我还有哪些待办 / xxx 任务在哪 / 进度」→ 查询任务

## When NOT to Use

- 学习卡片答题（会/不会/模糊）、错题本、费曼打分 → 走 learning_system / wrong_book / feynman_verify
- 洞察记录（洞察：xxx）→ 走 task_insight_extension
- 一次性、无需落表的口头提醒 → 不必调用

## 环境（固定，不要改）

- Python：`C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe`
- 工作目录：`D:\AI-Tools\feishu\V13方案增强\scripts`
- 所有命令先 `chcp 65001` 防中文乱码；PowerShell 用 `;` 不用 `&&`
- 凭证由 v15_features 自动从 feishu_insight_link.env 读取，无需手填 token

## Quick Reference（统一 CLI）

> 每条命令最后一行都打印 JSON 结果，**以 `"ok": true` 为成功唯一标准**。

### 1. 销项（完成）
```powershell
python task_ops_cli.py complete "任务关键词"
```
- 自动只匹配「待办/进行中/待开始」的活跃任务，置「已完成」+ 填实际完成日期
- 关键词用任务名中**最独特的连续片段**，避免一次匹配多条

### 2. 归档
```powershell
python task_ops_cli.py archive "任务关键词"
```

### 3. 新建任务
```powershell
python task_ops_cli.py create "任务名称" --p 中 --cat 工作
```
- 优先级 `--p`：高/中/低（默认中）；类别 `--cat`：工作/学习/生活/系统运维 等（默认工作）

### 4. 查询
```powershell
python task_ops_cli.py list 待办 进行中      # 按状态列出
python task_ops_cli.py find "关键词"          # 模糊查找（含 record_id）
```

## 执行规程（必须遵守）

1. **抽取意图**：从用户原话得到「动作 + 任务关键词」；任务名缺失时先问，不要猜。
2. **先定位再写**：complete/archive 前若不确定唯一，先 `find "关键词"` 看有几条。
3. **歧义 fail-closed**：CLI 返回 `"reason":"ambiguous"` 时，把候选列给用户二次确认，**不要擅自选第一条**。
4. **写后必回读**：操作成功后用 `find` 或 `list` 回读，确认状态字段确实变成目标值，再向用户报告。
5. **没找到不编造**：`"reason":"not_found"` 时如实说没找到，并给出最接近的候选，不要新建重复任务。
6. **批量要克制**：一次只操作用户点名的任务，不扩大范围；删除类操作不在本 Skill 范围。

## 自然语言 → 命令映射

| 用户说 | 命令 |
|---|---|
| 完成：收集机电培训素材 | `python task_ops_cli.py complete "收集机电培训素材"` |
| 搞定供电验收 | `python task_ops_cli.py complete "供电验收"` |
| 归档：配置熔断规则 | `python task_ops_cli.py archive "配置熔断规则"` |
| 新建任务：明天联系设计院 | `python task_ops_cli.py create "联系设计院" --p 中` |
| 我还有啥没做 | `python task_ops_cli.py list 待办 进行中 待开始` |

## 故障处理

| 现象 | 处理 |
|---|---|
| HTTP 400 / 分页报错 | 多为瞬时，重跑一次；连续两次失败检查网络与飞书凭证 env |
| token 失效 | 删除缓存由 v15_features 重新获取；确认 feishu_insight_link.env 存在 |
| 中文乱码 | 命令前先执行 `chcp 65001` |
| 匹配到多条 | 让用户给出更完整任务名，或用 find 拿到 record_id 后精确处理 |
| 写成功但回读没变 | 以回读为准，视为未完成；检查该字段是否为只读/选项值是否合法 |

## 与其他系统协同

- 任务状态变更后，Obsidian 侧由「正向/反向同步」在下个周期对齐，无需手工改本地笔记
- 早/午/晚三报会读取任务总表，销项后下一份报自动体现
- 学习类任务（复习、费曼）不在此表操作，避免污染任务总表
