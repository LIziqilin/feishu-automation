# 运维手册（OPS_MANUAL）

**版本**: V16交付保障版
**适用**: 间隔重复学习系统运维

---

## 一、系统架构

```
用户群消息 → 解析器(learning_system.py) → 流水表(只追加)
                                          ↓
                                    derive(review_derive.py)
                                          ↓
                                    学习卡表(派生值)
                                          ↓
                                    选题算法 → 早报推送
```

**核心原则**: 事件溯源，流水是唯一真源，派生值可随时从流水重建。

---

## 二、关键资源ID

| 资源 | ID |
|------|-----|
| Base | X8N1bvN3na99dFsyu0gcU8zTnHf |
| 学习卡片表 | tblpLvxyYpDJgF92 |
| 复习流水表 | tblbznzCSpPhSz93 |
| 系统事件日志表 | tblPreh1ipB9LQpf |
| 目标群 | oc_1fe154e172ab04622b7ffa810ac172bc |

---

## 三、日常运维命令

### 3.1 系统状态检查
```bash
python scripts/learning_system.py --status
```
输出：卡片总数、流水总数、状态分布、今日选题数。

### 3.2 手动触发derive全量重算
```bash
python scripts/review_derive.py --all
```

### 3.3 derive试运行（不写入）
```bash
python scripts/review_derive.py --all --dry-run
```

### 3.4 单卡重算
```bash
python scripts/review_derive.py --card <record_id>
```

### 3.5 全量重建（rebuild-all）
```bash
python scripts/review_derive.py --rebuild-all
```

### 3.6 手动选题
```bash
python scripts/learning_system.py --select
```

### 3.7 轮询群消息
```bash
python scripts/learning_system.py --poll
```

### 3.8 加固自检
```bash
python scripts/test_and_harden.py --harden
```

### 3.9 全部测试
```bash
python scripts/test_and_harden.py --all
```

---

## 四、回滚SOP（三类）

### 4.1 Seed/数据修复回滚（5-10min）
**触发**: 数据修复错误，卡片状态异常
```bash
# 1. 识别错误来源（来源=SEED_MIGRATION或修复脚本）
# 2. 从流水表重建派生值
python scripts/review_derive.py --rebuild-all
# 3. 抽查5张卡状态是否正确
# 4. 如仍错误，从备份恢复（原字段保留7天）
```

### 4.2 derive逻辑回滚（10min）
**触发**: derive计算错误，派生值异常
```bash
# 1. 停用即时触发（暂停轮询）
# 2. 修正review_derive.py逻辑
# 3. dry-run验证
python scripts/review_derive.py --all --dry-run
# 4. 确认无误后全量重算
python scripts/review_derive.py --all
# 5. 流水永不被污染，可随时重建
```

### 4.3 解析器回滚（30-60min）
**触发**: 正则解析错误，流水记录错误
```bash
# 1. 停用轮询（暂停消息处理）
# 2. 识别错误流水（event_id或时间范围）
# 3. 对错误流水追加REVOKE事件（revoke_of指向原event_id）
# 4. 修正解析器逻辑
# 5. 重新解析被错误处理的消息
# 6. rebuild-all重建派生值
python scripts/review_derive.py --rebuild-all
# 7. 回归测试
python scripts/test_and_harden.py --all
```

---

## 五、告警规则

### 5.1 告警分级
| 级别 | 触发条件 | 通道 |
|------|----------|------|
| CRITICAL | 权限失效/数据丢失/系统不可用 | 飞书+本地 |
| ERROR | derive失败/写入失败/连续3次重试失败 | 飞书+本地 |
| WARN | API慢(>2s)/解析成功率<90%/队列积压>3 | 飞书 |
| INFO | 日常运行状态/每日摘要 | 本地 |

### 5.2 去重规则
- 一级去重：同类型+同小时只发1条（内部计数）
- 二级聚合：每小时末1条摘要
- 三级升级：连续3h未恢复→升级通道

### 5.3 双通道硬规则
- A类告警（CRITICAL/ERROR）必须飞书+本地alerts.log
- 告警通道不得与故障域重合（Feishu写失败→走本地告警）
- 本地告警日志：scripts/alerts.log

---

## 六、监控指标

| 指标 | 阈值 | 说明 |
|------|------|------|
| last_success_time | 超1.5周期无成功 | **最重要，抓静默失败** |
| api_slow_count_daily | >5次/日(>2s) | API慢调用计数 |
| parse_success_rate_daily | <90%（仅计指令类） | 解析成功率 |
| queue_backlog | >3条 | 队列积压 |
| dlq_size | >0告警 | 死信队列大小（限流/配额只计数不告警） |

---

## 七、TTL与备份

### 7.1 日志分区TTL
| log_type | TTL | 说明 |
|----------|-----|------|
| RETRIEVAL | 90天 | 检索日志 |
| INSTRUCTION | 30天 | 指令日志 |
| ALERT | 14天 | 告警日志 |
| DEGRADE | 30天 | 降级日志 |
| AUDIT | 365天 | 审计日志 |
| USER_STATE | 90天 | 用户状态 |

### 7.2 备份策略
- 原子备份：tmp→校验(JSON可解析+记录数)→os.replace
- 7轮滚动备份
- 恢复演练：Phase1和Phase5各实测一次
- 原字段保留7天（修改后不立即删除）

---

## 八、静默期规则

- **静默期**: 23:00-07:00
- 静默期内：只施工不打扰，推送类场景压到07:00后
- DLQ静默期重试：只入库不推送，07:00随早报补推
- 告警：CRITICAL级别不受静默期限制

---

## 九、常见问题排查

### Q1: 早报显示"今日无到期复习卡片"
**排查**:
1. 运行`python scripts/learning_system.py --status`查看今日选题数
2. 检查卡片下次复习日期是否<=今天
3. 检查NOT_STARTED卡的intro_offset是否到期
4. 如选题为0，手动运行`python scripts/learning_system.py --select`

### Q2: 发「会」后无回执
**排查**:
1. 检查im:message权限是否有效
2. 检查轮询进程是否在运行
3. 查看scripts/alerts.log是否有权限失效告警
4. 手动运行`python scripts/learning_system.py --poll`测试

### Q3: derive计算结果异常
**排查**:
1. dry-run查看计算过程：`python scripts/review_derive.py --all --dry-run`
2. 检查流水表数据是否正确（superseded/untrusted标记）
3. 检查卡片状态字段是否被手动修改（应只由derive写入）
4. rebuild-all重建：`python scripts/review_derive.py --rebuild-all`

### Q4: 告警风暴
**排查**:
1. 检查去重规则是否生效（同类型+同小时只发1条）
2. 检查告警阈值是否过低
3. 查看scripts/alerts.log确认告警类型
4. 临时静默：在告警模块添加该类型到静默列表
