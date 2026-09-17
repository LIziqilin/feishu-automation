# LLM三顺位降级配置指南

## 配置文件位置

```
D:\AI-Tools\feishu\V13方案增强\scripts\llm_config.json
```

## 当前配置状态

| 顺位 | 名称 | 状态 | 说明 |
|------|------|------|------|
| 第一顺位 | ALLM本地模型 | ❌ 禁用 | 需本地运行ALLM服务 |
| 第二顺位 | DeepSeek API | ❌ 禁用 | 需配置API密钥 |
| 第三顺位 | Coze | ✅ 启用 | 通过飞书群消息与Coze中转助手交互 |
| 最终兜底 | 飞书表格知识索引检索 | ✅ 启用 | 基于知识索引表（200条记录）检索 |

**当前总开关：禁用**（`"enabled": false`），使用纯飞书表格知识索引检索。

---

## 配置步骤

### 步骤1：获取API密钥

#### 选项A：DeepSeek API（推荐，成本低）

1. 访问 https://platform.deepseek.com/
2. 注册/登录账号
3. 进入"API Keys"页面
4. 点击"Create API Key"，复制生成的密钥（sk-xxx）
5. 充值（最低10元，约可使用500万token）

**注意**：从飞书群消息看到DeepSeek余额告警：当前余额0.00元，需先充值。

#### 选项B：ALLM本地模型（免费，需本地运行）

1. 确保本地已安装ALLM（AnythingLLM）服务
2. 确认服务运行在 `http://localhost:8080`
3. 配置模型名称（默认qwen，可根据实际安装的模型修改）
4. 本地模型无需API密钥

#### 选项C：Coze（已启用，无需配置）

Coze已在运行（Coze中转助手），通过飞书群消息交互即可使用，无需额外配置。

---

### 步骤2：编辑配置文件

打开 `D:\AI-Tools\feishu\V13方案增强\scripts\llm_config.json`，根据需要修改：

#### 启用DeepSeek API（示例）

```json
{
  "enabled": true,
  "primary": {
    "name": "ALLM本地模型",
    "type": "local",
    "endpoint": "http://localhost:8080/v1/chat/completions",
    "api_key": "",
    "model": "qwen",
    "timeout": 30,
    "enabled": false
  },
  "secondary": {
    "name": "DeepSeek API",
    "type": "api",
    "endpoint": "https://api.deepseek.com/v1/chat/completions",
    "api_key": "sk-你的DeepSeek API密钥",
    "model": "deepseek-chat",
    "timeout": 30,
    "enabled": true
  },
  "tertiary": {
    "name": "Coze",
    "type": "coze",
    "endpoint": "",
    "api_key": "",
    "bot_id": "",
    "timeout": 30,
    "enabled": true,
    "note": "通过飞书群消息与Coze中转助手交互"
  },
  "fallback": {
    "name": "飞书表格知识索引检索",
    "type": "local_search",
    "enabled": true
  }
}
```

#### 启用ALLM本地模型（示例）

```json
{
  "enabled": true,
  "primary": {
    "name": "ALLM本地模型",
    "type": "local",
    "endpoint": "http://localhost:8080/v1/chat/completions",
    "api_key": "",
    "model": "qwen",
    "timeout": 30,
    "enabled": true
  },
  ...
}
```

---

### 步骤3：验证配置

运行以下命令查看配置状态：

```powershell
cd D:\AI-Tools\feishu\V13方案增强\scripts
python llm_fallback.py status
```

预期输出：

```
============================================================
LLM三顺位降级配置状态
============================================================
总开关: ✅ 启用

第一顺位: ALLM本地模型
  状态: ❌ 禁用
  配置: ❌ 未配置API密钥

第二顺位: DeepSeek API
  状态: ✅ 启用
  配置: ✅ 已配置API密钥

第三顺位: Coze
  状态: ✅ 启用
  说明: 通过飞书群消息与Coze中转助手交互

最终兜底: 飞书表格知识索引检索
  状态: ✅ 启用

✅ LLM降级已启用，将按顺位尝试调用
============================================================
```

---

### 步骤4：测试LLM问答

在飞书群中发送：

```
知识：间隔重复学习的原理是什么？
```

系统将按以下顺序尝试：
1. 第一顺位（如启用）：ALLM本地模型
2. 第二顺位（如启用）：DeepSeek API
3. 第三顺位：Coze（提示在群中@Coze中转助手）
4. 最终兜底：飞书表格知识索引检索

---

## 配置项说明

### 顶层配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `enabled` | boolean | 总开关，true=启用LLM降级，false=纯飞书表格检索 |

### 每个顺位的配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 显示名称 |
| `type` | string | 类型：local/api/coze/local_search |
| `endpoint` | string | API端点URL |
| `api_key` | string | API密钥（sk-xxx） |
| `model` | string | 模型名称 |
| `timeout` | number | 超时时间（秒） |
| `enabled` | boolean | 是否启用该顺位 |

---

## 降级逻辑

```
用户提问
    ↓
第一顺位（ALLM本地模型）
    ├─ 成功 → 返回答案
    └─ 失败/禁用 → 降级
         ↓
第二顺位（DeepSeek API）
    ├─ 成功 → 返回答案
    └─ 失败/禁用 → 降级
         ↓
第三顺位（Coze）
    ├─ 成功 → 返回答案（提示在群中@Coze）
    └─ 失败/禁用 → 降级
         ↓
最终兜底（飞书表格知识索引检索）
    └─ 返回检索结果
```

---

## 成本估算

### DeepSeek API

- 价格：输入约1元/百万token，输出约2元/百万token
- 日均消耗：约0.20元/天（从飞书群告警看到）
- 月成本：约6元/月
- 最低充值：10元（约可用50天）

### ALLM本地模型

- 成本：免费（使用本地CPU/GPU）
- 要求：本地运行ALLM服务，需足够内存（建议16G+）
- 速度：取决于本地硬件，可能比API慢

### Coze

- 成本：免费（Coze免费额度）
- 限制：需在飞书群中@Coze中转助手，非自动调用

---

## 常见问题

### Q1：配置后不生效？

A：检查以下几点：
1. 总开关 `"enabled": true`
2. 对应顺位的 `"enabled": true`
3. API密钥正确（sk-xxx格式）
4. 运行 `python llm_fallback.py status` 确认状态

### Q2：DeepSeek API调用失败？

A：检查以下几点：
1. API密钥是否正确
2. 账户是否有余额（从飞书群告警看到当前余额0.00元，需充值）
3. 网络是否能访问 api.deepseek.com

### Q3：ALLM本地模型调用失败？

A：检查以下几点：
1. ALLM服务是否运行（访问 http://localhost:8080 确认）
2. 模型名称是否正确（默认qwen，根据实际安装修改）
3. 端口是否正确（默认8080）

### Q4：如何临时禁用LLM降级？

A：将总开关改为 `"enabled": false`，系统将使用纯飞书表格检索。

### Q5：如何只启用某一个顺位？

A：将其他顺位的 `"enabled": false`，只保留需要的顺位为 `true`。

---

## 推荐配置

### 方案A：低成本（推荐）

- 总开关：启用
- 第一顺位：禁用（ALLM本地模型）
- 第二顺位：启用（DeepSeek API，充值10元）
- 第三顺位：启用（Coze）
- 最终兜底：启用（飞书表格检索）

**月成本**：约6元/月
**优点**：成本低，响应快，有多重降级
**缺点**：需充值DeepSeek

### 方案B：免费

- 总开关：启用
- 第一顺位：启用（ALLM本地模型，需本地运行）
- 第二顺位：禁用
- 第三顺位：启用（Coze）
- 最终兜底：启用（飞书表格检索）

**月成本**：0元
**优点**：完全免费，数据本地处理
**缺点**：需本地运行ALLM，速度取决于硬件

### 方案C：最简（当前配置）

- 总开关：禁用
- 所有顺位：禁用（除Coze和飞书表格检索）
- 最终兜底：启用（飞书表格检索）

**月成本**：0元
**优点**：最简单，无需配置
**缺点**：只有飞书表格检索，无LLM生成能力

---

**配置完成后**，在飞书群中发送「知识：xxx」即可测试LLM问答功能。

如有问题，请检查配置文件或运行 `python llm_fallback.py status` 查看状态。
