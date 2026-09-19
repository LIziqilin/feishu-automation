# AI系统综合方案-客户使用指导手册
**版本**：V47 | **日期**：2026-09-19 | **对象**：系统所有者（单人日常使用）

---

## 一、系统能帮你做什么（速览）
1. **飞书总控群@机器人**：下任务、销项、归档、记洞察、问系统、智能对话、闪卡复习、系统体检。
2. **早晚自动推送**：早报07:30、晚报20:00（西安天气+社会/自然/人性三察洞察）。
3. **多维表格批量AI**：错题解析、学习周报、画像演化、健康诊断（飞书点数耗尽自动走DeepSeek）。
4. **AnythingLLM深度问答**：5个工作区，1939篇文档，可直接问方案/手册/学习内容。
5. **自动运维**：每日03:00维护+7轮备份、每小时备份、8桥接巡检、失败企微告警。

## 二、飞书总控群指令（最常用）
在总控群 @机器人，发送：
| 你想做的事 | 直接发 |
|---|---|
| 新建任务 | `新建任务：落实泛光照明验收节奏` |
| 标记完成 | `搞定了：【P3】GitHub抓外部数据` |
| 归档任务 | `归档 【P3】GitHub抓外部数据` |
| 记一条洞察 | `洞察：事情落实清楚后再找对策` |
| 让Coze办复杂事 | `智能：帮我把这条任务拆成3步` |
| 查系统怎么运作 | `问系统：系统的备份策略是什么` |
| 开始复习 | `开始闪卡复习` |
| 系统健康检查 | `系统体检` |
| 学一个知识点 | `学知识：工程总监` |

> 机器人无反应时：先看是否@对、再跑桥接自检（见第六节）。

## 三、多维表格批量AI（4类）
**方式A（脚本，现已可用，推荐）**：打开PowerShell
```powershell
cd D:\AI-Tools\feishu\V13方案增强
$env:DEEPSEEK_API_KEY="sk-你的key"   # 已写入shared配置，通常无需再设
python scripts\coze_batch_tasks.py wrong_answer --limit 3   # 错题解析
python scripts\coze_batch_tasks.py weekly_report            # 学习周报
python scripts\coze_batch_tasks.py profile --limit 5        # 画像演化
python scripts\coze_batch_tasks.py health --limit 5         # 健康诊断
```
**方式B（表格内字段捷径）**：等Coze发布的"错题解析助手"等4个捷径飞书审批通过后，在对应表新建"字段捷径"列，点单元格即生成。
- 错题解析→学习卡片表；学习周报→复习流水表；画像→用户画像表；健康诊断→系统健康表。

## 四、AnythingLLM 用法
1. 打开 AnythingLLM 桌面端。
2. 左侧选工作区：学习助手Agent / 知识库Agent / 洞察Agent。
3. 直接提问；@agent 可调用飞书文档工具（feishu-mcp）或读写文件（filesystem MCP）。
4. 长期记忆：正常对话即自动积累（memories表），无需配置。

## 五、自动推送与定时任务（无需操作）
- 早报07:30 / 午报 / 晚报20:00：本地计划任务 + GitHub云端（fetch_external_data，北京8/20点）。
- 每日03:00：维护链（开头先跑桥接巡检，红项自动报总控群）。
- 每小时：hourly_backup滚动备份。
- 云端失败：alert_fail.py自动发消息到总控群。

## 六、故障自查（按顺序）
| 现象 | 第一步 | 命令/动作 |
|---|---|---|
| 群@机器人没反应 | 桥接自检 | `python scripts\bridge_health_check.py`，红项即故障桥 |
| 早/晚报没收到 | 查GitHub | github.com/LIziqilin/feishu-automation/actions 看 fetch_external_data 日志；失败会有群告警 |
| Coze不回/积分耗尽 | 看fallback | llm_router会自动切DeepSeek；手动验证 `python scripts\llm_router.py --check` |
| 表格AI字段不工作 | 用脚本 | 走第三节方式A（DeepSeek），不等字段捷径 |
| 想全面体检 | 健康自检 | `python scripts\system_health_check.py` |
| 查备份 | 看backups目录 | 最新应为每小时的 hourly_*.json |

## 七、常用命令速查
```powershell
cd D:\AI-Tools\feishu\V13方案增强
python scripts\llm_router.py "你的问题"        # 统一LLM（Coze→DeepSeek）
python scripts\llm_router.py --check           # LLM双通道自检
python scripts\bridge_health_check.py          # 8桥接巡检
python scripts\system_health_check.py          # 计划任务+系统体检
python scripts\anyllm_bridge.py stats          # AnythingLLM状态
python scripts\coze_gateway.py --check         # Coze连通性
python scripts\mastery_recalc.py               # 掌握度重算
python scripts\system_rag.py "你的问题"         # 查本地方案/手册
```

## 八、日常维护节奏
| 频率 | 事项 |
|---|---|
| 每天 | 确认早报/晚报收到；看是否有红色告警 |
| 每周 | 跑一次 bridge_health_check + system_health_check；做学习周报 |
| 每月 | 检查Coze令牌有效期（当前2026-10-10到期，需提前换服务访问令牌）；核对GitHub secrets |
| 每季度 | 跑一次 recovery_drill/restore_drill 恢复演练；git push确认异地代码备份 |
| 变更/删除前 | 手动跑 backup_with_rotation.py |

## 九、密钥与配置位置
- Coze + DeepSeek：`D:\AI-Tools\shared\coze_config.json`（coze_api_token / bot_id / deepseek_api_key）。
- 企业微信：`scripts\wecom_config.json`。
- 多维表格/群ID：见《综合方案-预验收版》第3章。
- 切勿把密钥发到群里或写进前端页面。


## 十、webapi 云端部署与整机恢复（V49新增）

### 10.1 三种运行位置，关机后能力对照
| 组件 | 本机 | GitHub Actions 云端 | 云服务器 |
|---|---|---|---|
| 早/午/晚报 | 关机停 | 关机照常推送 | 关机照常 |
| webapi /ask /webhook | 仅本机127.0.0.1 | on-demand（已配） | 公网常驻 |
| 4个DeepSeek助手 | 手动 | 可定时 | 可定时 |

### 10.2 云服务器部署（买好服务器后，约10分钟）
1. 把项目 scp 到服务器 /opt/feishu-automation
2. 编辑 scripts/webapi_secrets.env，把 WEBAPI_TOKEN 改成强口令
3. 执行：bash scripts/deploy/deploy_cloud.sh
4. 云厂商安全组放行 8765；建议套 Nginx + HTTPS 后再对公网开
5. 验证：curl http://服务器IP:8765/health 返回 ok
（产物：scripts/deploy/ 下 Dockerfile / docker-compose.yml / feishu-webapi.service / deploy_cloud.sh）

### 10.3 GitHub Actions on-demand（零成本关机可用，已配好）
外部机器触发云端问答（示例，github_pat 换成你自己的）：
```
curl -X POST https://api.github.com/repos/LIziqilin/feishu-automation/dispatches   -H "Authorization: Bearer 你的github_pat"   -H "Accept: application/vnd.github+json"   -d '{"event_type":"ask","client_payload":{"q":"今天做什么"}}'
```
workflow：.github/workflows/webapi_on_demand.yml；需在 GitHub 仓库 Settings- Secrets 配 DEEPSEEK_API_KEY、WEBAPI_TOKEN。

### 10.4 整机恢复（电脑坏了/重装后）
1. 装 Python3.10、Node、git
2. git clone 仓库到 D:\AI-Tools\feishu\V13方案增强
3. 从飞书云盘 feishuAI 文件夹下载 feishu_scripts_snapshot_*.zip，解压覆盖 scripts/ docs/
4. 还原密钥：D:\AI-Tools\shared\coze_config.json、scripts\webapi_secrets.env（这两个不入仓）
5. 跑 python scripts/control_center.py all 自检，全 PASS 即恢复完成


### 10.5 生成 GitHub Personal Access Token（PAT）—— 关机触发云端问答用
外部从手机/别的电脑触发云端问答（repository_dispatch）需要一个有 repo 权限的 PAT：

1. 浏览器登录 GitHub，右上角头像 -> Settings
2. 左侧最下方 Developer settings -> Personal access tokens
3. 选 Tokens (classic) -> Generate new token (classic)
4. Note 填 feishu-cloud-trigger；Expiration 选 No expiration（或 1 年）
5. 勾选权限：只勾 **repo**（整个 repo 大类即可）
6. 点 Generate token，复制形如 ghp_xxxxxxxxxxxx 的串，立刻存好（只显示一次）

用法（把 ghp_xxx 换成你复制的）：
```
curl -X POST https://api.github.com/repos/LIziqilin/feishu-automation/dispatches \
  -H "Authorization: Bearer ghp_xxx" \
  -H "Accept: application/vnd.github+json" \
  -d '{"event_type":"ask","client_payload":{"q":"今天做什么"}}'
```
安全提醒：PAT 等同账号密码，不要发群、不要写进前端；泄露了就到同一页面 Revoke 删掉再生成。
不想用 curl 时，也可直接在仓库 Actions 页点 webapi on-demand -> Run workflow 手动问。


### 10.6 云端问答加固记录（V49，2026-09-19）
- ask_cloud.py / webhook_cloud.py 已加固：网络失败自动重试3次（指数退避）、超时90s、DeepSeek失败时把原因也推群（不静默）、空参校验。
- 端到端验证：本地 code:0；GitHub Actions Run Success；飞书总控群实测收到云端问答消息。
- 云端代码包已重新同步飞书云盘 feishuAI：feishu_scripts_snapshot_20260919.zip。


### XI.5 批量新建任务（V49新增）
群里 @助手 发一条即可建多个任务，用分号/换行分隔：
```
@我的助手 批量新建：任务A；任务B；任务C
```
机器人会逐个写入任务表，并回复"✅ 批量新建完成：共3个，成功3个"。
说明：轮询间隔已在调试验收期临时改为1分钟，验收后调回5分钟。

### XI.6 批量销项与多任务（V49）
- 单任务销项：@助手 完成：任务名（任务名要唯一，重名会提示从列表选序号）
- 批量新建：@助手 批量新建：A；B；C
- 归档：@助手 归档：任务名
- 说明：同名/近似任务会提示⚠️找到N个匹配，按回复序号或发更精确任务名即可。
