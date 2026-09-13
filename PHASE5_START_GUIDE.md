# V16交付保障版 · Phase5 自运行启动手册

**版本**: v1.0
**生成时间**: 2026-09-11 07:55
**适用对象**: 系统使用者（无需编程知识）

---

## 一、系统当前状态

| 项 | 状态 |
|----|------|
| 施工完成度 | ✅ 100%（Phase 0-4全部完成） |
| 自动化调度 | ✅ 3个Windows任务计划已配置并运行 |
| 飞书Base | ✅ 14张表，学习卡40字段（0公式），流水13字段（0公式） |
| E2E全链路验证 | ✅ 通过（发「会」→解析→流水→回执<5秒） |
| 漏洞扫描复检 | ✅ 6/6通过，无未修复漏洞 |
| 备份 | ✅ 已备份（backups/目录） |
| 系统监控 | ✅ last_success_time正常，双通道告警就绪 |

---

## 二、日常使用方式（极简）

### 每天早上（自动）
- **07:30** 系统自动推送早报到「个人总控群」
- 早报内容：今日复习卡片（只显示问题，不显示答案）

### 你只需要做一件事
在群里直接回复：
- `会` → 这张卡我会了
- `不会` → 这张卡我不会（间隔缩短，更早复习）
- `模糊` → 有点印象但不确定（间隔不变）

### 系统自动完成（5分钟内）
1. 解析你的回复
2. 写入复习流水
3. 发送即时回执：`✓ 已记录：会/不会/模糊`
4. 发送延迟回执：`💡 答案：...` + `📅 下次复习：X月X日`
5. 自动重算间隔重复算法，决定下次出现时间

### 其他指令
- `今日卡片` → 重新推送今日卡片
- `暂停` → 暂停推送2天
- `恢复` → 恢复推送
- `会 2` → 跳答第2张（可选，默认按顺序答）

---

## 三、每日检查清单（5分钟，可选）

如果想确认系统正常运行，每天花5分钟检查：

```powershell
# 1. 检查自动化任务状态
Get-ScheduledTask -TaskName 'V16_*' | Select-Object TaskName, State

# 2. 检查系统监控状态
type D:\AI-Tools\feishu\V13方案增强\scripts\.system_state.json

# 3. 检查最近流水（可选，系统自动处理）
# 打开飞书Base → 复习流水表 → 看最新记录
```

**正常状态**：
- 3个任务都是 Ready
- last_success_time 在最近24小时内
- 流水表每天有新记录（你答题后）

---

## 四、3天验收标准（Phase5通过条件）

连续3天（09-11 ~ 09-14）满足以下条件，即视为系统稳定可用：

| # | 验收项 | 标准 | 检查方式 |
|---|--------|------|----------|
| 1 | 早报推送 | 每天07:30收到早报 | 看群消息 |
| 2 | 答题解析 | 回复「会/不会/模糊」后5分钟内收到回执 | 看群消息 |
| 3 | 流水记录 | 每次答题都有对应流水记录 | 看Base流水表 |
| 4 | 无P0告警 | 无系统崩溃/权限失效告警 | 看群消息/alerts.log |
| 5 | 数据一致性 | derive重算与线上状态一致 | 运行data_audit.py |
| 6 | 自动化正常 | 3个任务计划持续运行 | Get-ScheduledTask |

**通过后**：系统进入长期稳定运行状态，无需额外维护。

---

## 五、常见问题处理

### Q1: 没收到早报怎么办？
```powershell
# 手动触发一次早报推送
python D:\AI-Tools\feishu\V13方案增强\scripts\learning_system.py --select
```

### Q2: 回复后没收到回执怎么办？
```powershell
# 手动触发一次消息轮询解析
python D:\AI-Tools\feishu\V13方案增强\scripts\learning_system.py --poll
```

### Q3: 想查看学习进度怎么办？
打开飞书Base → 学习卡片表 → 按"卡片状态"筛选：
- NOT_STARTED: 还没开始学
- LEARNING: 学习中
- REVIEWING: 复习中
- MASTERED: 已掌握

### Q4: 想暂停几天怎么办？
在群里发 `暂停`（默认暂停2天），恢复时发 `恢复`。

### Q5: 系统报错怎么办？
1. 看群里是否有告警消息
2. 看本地告警日志：`type D:\AI-Tools\feishu\V13方案增强\scripts\alerts.log`
3. 手动运行一次维护：`python D:\AI-Tools\feishu\V13方案增强\scripts\review_derive.py --all`

---

## 六、管理命令速查

```powershell
# 查看自动化任务
Get-ScheduledTask -TaskName 'V16_*'

# 手动运行早报推送
Start-ScheduledTask -TaskName 'V16_MorningReport'

# 手动运行消息轮询
Start-ScheduledTask -TaskName 'V16_LearningPoll'

# 手动运行每日维护
Start-ScheduledTask -TaskName 'V16_DailyMaintenance'

# 查看系统状态
type D:\AI-Tools\feishu\V13方案增强\scripts\.system_state.json

# 查看告警日志
type D:\AI-Tools\feishu\V13方案增强\scripts\alerts.log

# 运行数据审计
python D:\AI-Tools\feishu\V13方案增强\scripts\data_audit.py

# 运行单元测试
python D:\AI-Tools\feishu\V13方案增强\scripts\unit_tests.py
```

---

## 七、系统架构速览

```
用户（在群里回复会/不会/模糊）
    ↓
V16_LearningPoll（每5分钟自动轮询）
    ↓
InstructionParser（顺序消费制解析）
    ↓
复习流水表（只追加，事件溯源）
    ↓
review_derive.py（派生值重算）
    ↓
学习卡片表（状态/间隔/下次复习日期）
    ↓
ReceiptSender（两段式回执：即时确认+延迟答案）
    ↓
用户收到回执（✓已记录 + 💡答案 + 📅下次日期）
```

---

## 八、重要链接

- **飞书Base**: https://acn8z05ycj5w.feishu.cn/base/X8N1bvN3na99dFsyu0gcU8zTnHf
- **工作目录**: D:\AI-Tools\feishu\V13方案增强\
- **脚本目录**: D:\AI-Tools\feishu\V13方案增强\scripts\
- **备份目录**: D:\AI-Tools\feishu\V13方案增强\backups\

---

**一句话**: 系统已经全自动运行，你每天只需在群里回复「会/不会/模糊」，其他全部自动处理。连续用3天，系统就稳定了。
