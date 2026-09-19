# AI系统综合方案-客户使用指导手册
**版本**：V46.1 | **日期**：2026-09-19 | **适用**：个人日常使用

---

## 一、日常使用场景

### 场景1：群里@机器人下指令
打开飞书总控群，直接@你的助手：
- `新建任务：落实泛光照明验收节奏` → 创建任务
- `搞定了：【P3】GitHub抓外部数据` → 标记完成
- `归档 【P3】GitHub` → 归档
- `洞察：事情落实清楚再想办法` → 记录洞察
- `智能：帮我分析一下这个错题` → 调Coze复杂对话
- `开始闪卡复习` → 开始学习
- `系统体检` → 健康检查

### 场景2：多维表格批量AI处理
打开多维表格学习卡片表：
1. 找到 `AI解析_错题` 列（等字段捷径审核通过后）
2. 点某行单元格 → 自动调Coze/DeepSeek → 结果写入
3. 无飞书AI点数时自动切DeepSeek，不中断

### 场景3：早晚推送
- **早报**：每天早7:30本地推送（西安天气+三察洞察）
- **晚报**：每天晚8:00 GitHub云端推送
- 无需操作，自动收到

### 场景4：深度问答（AnythingLLM）
打开AnythingLLM桌面端：
- 学习助手Agent → 问学习问题
- 知识库Agent → 查方案/手册
- 洞察Agent → 问决策复盘

---

## 二、脚本手动用法

```bash
# 切到项目目录
cd D:\AI-Tools\feishu\V13方案增强

# LLM网关（Coze优先，失败自动切DeepSeek）
python scripts\llm_router.py "你的问题"
python scripts\llm_router.py --check

# 批量任务
python scripts\coze_batch_tasks.py wrong_answer --limit 3
python scripts\coze_batch_tasks.py weekly_report
python scripts\coze_batch_tasks.py profile
python scripts\coze_batch_tasks.py health

# 桥接自检
python scripts\bridge_health_check.py
```

---

## 三、故障排查

| 现象 | 处理 |
|---|---|
| 群里@机器人没反应 | 跑 `python scripts\bridge_health_check.py` 看哪个桥接红 |
| 早报没收到 | 去GitHub Actions看fetch_external_data.yml日志 |
| 多维表格AI字段不工作 | 已自动切DeepSeek，等字段捷径审核通过 |
| Coze调用失败 | llm_router自动切DeepSeek，无需干预 |

---

## 四、日常维护

| 频率 | 操作 |
|---|---|
| 每天 | 看早报/晚报是否收到 |
| 每周 | 跑 `python scripts\bridge_health_check.py` |
| 每月 | 检查Coze token是否快过期（当前到10-10） |
| 每季度 | git push 确认GitHub有最新备份 |
