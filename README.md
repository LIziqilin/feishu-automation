# GitHub Actions 外部数据抓取模板

## 功能说明
每天定时抓取外部数据（RSS资讯、天气等），自动写入飞书多维表格，并发送飞书通知。

## 目录结构
```
├── .github/workflows/
│   └── fetch_external_data.yml    # 主工作流
├── scripts/
│   ├── fetch_rss.py               # RSS资讯抓取
│   ├── fetch_weather.py           # 天气数据抓取
│   └── write_to_feishu.py         # 写入飞书多维表格
└── README.md                       # 本文件
```

## 配置步骤（小白版）

### 第一步：创建GitHub仓库
1. 打开 https://github.com/new
2. 仓库名填 `feishu-automation`
3. 选 Public（公开）或 Private（私有）都可以
4. 勾选 "Add a README file"
5. 点 "Create repository"

### 第二步：上传模板文件
1. 在仓库页面点 "Add file" → "Upload files"
2. 把本目录的所有文件拖进去（保持目录结构）
3. 点 "Commit changes"

### 第三步：配置Secrets（密钥）
1. 仓库页面点 "Settings"（设置）
2. 左侧菜单点 "Secrets and variables" → "Actions"
3. 点 "New repository secret"，依次添加以下密钥：

| Secret名称 | 值 | 是否必须 | 获取方式 |
|---|---|---|---|
| FEISHU_APP_ID | 飞书应用ID | 必须 | 飞书开放平台→创建应用→凭证与基础信息 |
| FEISHU_APP_SECRET | 飞书应用密钥 | 必须 | 同上 |
| FEISHU_WEBHOOK | 群机器人webhook地址 | 可选 | 飞书群→设置→群机器人→添加自定义机器人 |
| RSS_URLS | RSS源URL，多个用逗号分隔 | 可选 | 例如：https://36kr.com/feed,https://sspai.com/feed |
| WEATHER_API_KEY | 和风天气API密钥 | 可选 | https://dev.qweather.com/ 免费注册，每天1000次 |

### 第四步：飞书应用配置
1. 打开 https://open.feishu.cn/app
2. 创建企业自建应用，名称填 "外部数据采集"
3. 在 "权限管理" 中开通以下权限：
   - `bitable:app`（多维表格读写）
   - `im:message`（发送消息）
4. 在 "版本管理与发布" 中创建版本并发布
5. 把应用添加到多维表格的协作者中（打开多维表格→分享→添加应用）

### 第五步：测试运行
1. 仓库页面点 "Actions"
2. 左侧选 "抓取外部数据写入飞书多维表格"
3. 点 "Run workflow" → "Run workflow"
4. 等待运行完成，查看结果

## 自定义配置

### 修改执行时间
编辑 `.github/workflows/fetch_external_data.yml` 中的 cron 表达式：
```yaml
schedule:
  - cron: '0 8 * * *'  # UTC时间，北京时间=UTC+8
```
- 北京时间8:00 = UTC 0:00 = `0 0 * * *`
- 北京时间9:00 = UTC 1:00 = `0 1 * * *`

### 添加新的数据源
1. 在 `scripts/` 目录新建 `fetch_xxx.py`
2. 在工作流中添加调用步骤
3. 在 `write_to_feishu.py` 中添加读取逻辑

### 修改目标表
编辑工作流中的环境变量：
```yaml
env:
  FEISHU_BASE_TOKEN: X8N1bvN3na99dFsyu0gcU8zTnHf  # 多维表格token
  FEISHU_TABLE_ID: tbl0NiUFeQzH2r3n  # 目标表ID（建议新建外部数据采集表）
```

## 免费额度
- GitHub Actions：公开仓库无限，私有仓库2000分钟/月
- 和风天气API：1000次/天免费
- 飞书多维表格API：按企业版本配额

## 常见问题

**Q: 运行失败怎么办？**
A: 在 Actions 页面点击失败的运行，查看日志，根据错误信息排查。

**Q: 飞书写入失败？**
A: 检查①应用是否已添加到多维表格协作者 ②应用权限是否已开通 ③APP_ID和APP_SECRET是否正确。

**Q: 不想用了怎么停？**
A: 在 Actions 页面点 "..." → "Disable workflow" 即可停用。
