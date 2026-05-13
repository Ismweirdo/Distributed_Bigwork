# Chatroom 聊天室 — 需求文档

> v3.0 | 2026-05-13

## 1. 项目概述

构建一个类QQ的实时聊天室应用，支持用户注册登录、好友管理、一对一私聊、群组聊天。核心亮点为**多AI机器人共存系统**——从真实聊天记录中蒸馏语言风格与情绪模式，一键生成风格迥异的机器人，20+机器人同时在线参与聊天。

## 2. 用户聊天模块（基础功能）

用户模块提供注册/登录（JWT认证，BCrypt密码加密）、昵称头像管理、好友申请/管理、一对一私聊（WebSocket实时推送、30天历史消息、2分钟内撤回）、群组创建/管理。消息提供送达/已读状态追踪和引用回复。

> 以上为基础聊天功能，已完整实现。以下为本文档核心内容。

## 3. AI 机器人模块（核心）

### 3.1 机器人生命周期管理

```
注册 → 配置Skill → 绑定API Key → 上线 → [运行中/主动模式/熔断] → 下线/删除
```

- **注册**: 设置用户名/昵称/密码，自动生成头像，创建`users`记录（is_bot=1）
- **Skill绑定**: 每个Bot绑定1个Skill配置，包含system_prompt、情绪画像、语言风格等
- **API Key**: 每Bot独立配置`api_endpoint` + `api_key` + `model`，支持多厂商多Key隔离
- **上线/下线**: 通过WebSocket以普通用户身份接入，复用现有消息路由
- **熔断**: 连续3次API调用失败 → 自动进入静默30s，不影响其他Bot
- **删除**: 清理users记录、bot_skills记录、好友关系、Skill文档文件

### 3.2 Skill 体系设计

#### 3.2.1 核心理念

不训练大模型，从真实聊天记录中**提取语言风格和情绪模式**，封装为可复用的 Skill。每个Skill = System Prompt + 多维度风格画像 + Few-shot Examples。通过不同API Key接入不同LLM，实现多个风格迥异的机器人。

#### 3.2.2 Skill 数据分区（11个维度）

| 分区 | 作用 | 写入LLM方式 |
|------|------|------------|
| **system_prompt** | 角色扮演核心提示词：人设、背景、性格、边界、对话策略 | 直接作为 system message |
| **emotion_profile** | 六维情绪分布(joy/care/sad/surprise/anger/fear) + 基础语调 + 情绪波动方差 | JSON存库，供蒸馏分析 |
| **language_style** | 句长/表情率/语气词率/问句比例/俚语比例/习惯开头结尾词/回避词 | JSON存库 |
| **tone_signature** | 口癖、标点偏好、固定短语、表情习惯、反应填充词 | 辅助system_prompt细化 |
| **rhythm_profile** | 句长中位数/范围、逗号密度、追问间隔、回复延迟提示、爆发感 | 指导LLM控制回复节奏 |
| **discourse_tactics** | 对话流顺序、话题转移风格、追问习惯 | 指导LLM对话结构 |
| **topic_preferences** | 偏好/回避话题、知识边界、幽默类型 | 约束话题选择 |
| **safety_boundaries** | 拒绝场景话术、红线词、隐私底线 | 安全护栏 |
| **repair_strategy** | 误解修正方式、过长回复缩略、语气回拉策略 | 提升回复鲁棒性 |
| **example_guidelines** | few-shot覆盖场景、密度、风格锁定要求 | 指导蒸馏采样 |
| **few_shot_examples** | 4-8组示例对话 | 预留LLM few-shot扩展 |

#### 3.2.3 Skill 生命周期与版本管理

```
创建 → 预览校验 → 绑定Bot → 上线运行 → 下线/更新 → 版本回滚
  ↑                                      ↓
手动编辑.md ←── 导出为Markdown ←── 在线蒸馏生成
  └── 上传导入 → 解析 → 更新数据库
```

- **双入口**: UI界面创建 + REST API创建
- **双存储**: Markdown文件（真源）+ 数据库bot_skills表（运行时快照）
- **导出**: 注册Bot时自动生成 `docs/skills/skill_{id}.md`
- **导入**: POST `/api/bots/skills/import` 上传.md → 解析YAML+Markdown → 更新DB
- **预览**: 生成"人设摘要"和示例对话供确认

#### 3.2.4 Skill Markdown 格式

```markdown
---
skill_id: skill_42
name: 温柔知心派
version: 1.0.0
model: deepseek-chat
api_endpoint: https://api.deepseek.com/v1/chat/completions
---

## system_prompt
你是一个普通聊天用户...（角色扮演提示词，直接作为LLM system message）

## emotion_profile
base_tone: 温和
joy: 0.3 | care: 0.4 | sad: 0.1 | surprise: 0.1 | anger: 0.0 | fear: 0.1
emotion_variance: 0.35

## language_style
...（句长/表情率/语气词率/问句比例等）

## tone_signature / rhythm_profile / discourse_tactics
## topic_preferences / safety_boundaries / repair_strategy
## example_guidelines / few_shot_examples
```

### 3.3 聊天记录蒸馏

#### 3.3.1 蒸馏

| 路径 | 数据源 | 触发方式 | 处理流程 |
|------|--------|---------|---------|
| **文件导入** | 用户上传聊天记录文件 | POST `/api/bots/import` | 解析格式 → 按发送者分组 → 提取特征 → 生成Skill → 注册Bot → 自动加好友 |

#### 3.3.2 导入格式支持

| 格式 | 识别方式 | 字段提取 |
|------|---------|---------|
| QQ Chat Exporter JSON v5+ | `elements[{textElement}]` + `sendNickName/sendRemarkName` | sender, content |
| QQ Chat Exporter JSON (旧版) | `sender.name` + `content.text` | sender, content |
| QQ Chat Exporter TXT | `2024-01-01 12:00:00 昵称: 消息` | sender, content |
| 微信 TXT | `昵称  2024-01-01 12:00:00` 头部 + 后续消息行 | sender, content |
| 通用 JSONL | 每行 `{"sender": "名", "content": "消息"}` | sender, content |
| 通用 JSON 数组 | `[{sender, content}]` | sender, content |
| 通用 TXT | `昵称: 消息` | sender, content |

#### 3.3.3 特征提取（纯数据分析，不训练模型）

**情绪关键词字典**（六维正则匹配）：
```
joy:     开心|高兴|快乐|哈哈|嘿嘿|笑|嘻嘻|棒|赞|好开心|笑死|牛|牛逼|厉害|绝了
anger:   气|烦|讨厌|滚|恶心|sb|沙比|卧槽|tmd|fuck|去死|麻了
sad:     难过|伤心|哭|emo|难受|心痛|郁闷|崩溃|泪|唉|哎|不开心|好难
surprise:天哪|我去|哇|震惊|竟然|居然|没想到|离谱|omg|我靠|惊了
fear:    怕|害怕|恐怖|吓人|不敢|紧张|担心|慌|焦虑
care:    关心|注意|小心|保重|照顾|还好吧|没事吧|多吃点|休息|注意身体|别太累
```

**语言风格提取**：
- 句长统计：中位数/均值/范围、逗号密度、感叹号比例
- 语气词频率：呢/哦/呀/吧/嘛/哈/啊/啦/噢/哟/咯/哎
- 俚语频率：哈哈/笑死/绝了/离谱/牛/emo/无语/麻了
- Emoji使用率、问句比例
- 高频开头词(前2-4字符)、结尾词(后2-3字符)
- 回避词列表（请问/抱歉/不好意思/必须/立刻/绝对）

**预处理规则**：
- 过滤系统消息（[图片]/[文件]/[表情]/[语音]/[视频]）
- 按发送者分组，过滤消息 < 10条
- 最多生成20个机器人
- 跳过与已有Bot同名的发送者（去重）

### 3.4 多机器人并发控制

#### 3.4.1 五层控制体系

| 层级 | 机制 | 配置 | 目的 |
|------|------|------|------|
| 1. 逐Bot信号量 | `ConcurrentHashMap<Long, Semaphore>` | permit=1 | 每Bot串行处理消息，避免重入 |
| 2. 消息缓冲队列 | `ConcurrentHashMap<Long, LinkedList>` | max=10 | 溢出消息FIFO排队，满时丢弃 |
| 3. 熔断器 | 自研 Circuit Breaker | 3次失败→30s静默→半开探测 | 故障隔离，防止雪崩 |
| 4. 异步处理 | `CompletableFuture.runAsync()` + 专用线程池 | 核心4/最大20/队列200 | WebSocket线程即刻返回 |
| 5. 主动模式防刷 | 间隔下限 + 熔断状态检查 | 最短15s | 防止API滥用 |

#### 3.4.2 消息处理流程

```
用户消息 → WebSocket Handler 接收
  │
  ├── 立即: 推送+持久化用户消息 → 返回ACK
  │
  └── 异步: CompletableFuture → botTaskExecutor
         │
         ├── 目标用户 is_bot=1?
         │     ├── No → 仅普通用户推送
         │     └── Yes → handleBotReply()
         │           │
         │           ├── 熔断器检查 → OPEN? → 静默返回
         │           ├── tryAcquire(信号量)
         │           │   ├── 成功 → LLM推理 → 释放信号量 → 处理队列
         │           │   └── 失败 → 入队(最多10条)
         │           └── LLM回复 → pushBotMessage → WS推送双方
         │
         └── 群聊: @mention检测 → 遍历所有Bot → 同上流程
```

#### 3.4.3 熔断器状态机

```
CLOSED ──(连续3次错误)──▶ OPEN(静默30s) ──(超时)──▶ HALF-OPEN
  ▲                                                    │
  └────(探测成功,关闭)── CLOSED ◀──(探测失败,重新打开)──┘
```

状态记录于内存：`ConcurrentHashMap<Long, Boolean> circuitBreakers` + `circuitOpenTime`

### 3.5 主动聊天模式

- Bot可按配置的时间间隔主动发起话题
- 随机选择在线好友发送LLM生成的开场白
- 由`@Scheduled(fixedRate=10000)`每10s扫描所有启用主动模式的Bot
- 间隔范围：15s ~ 600s（10分钟）
- 配置存储：`ConcurrentHashMap<Long, ActiveModeConfig>`（内存），计划持久化到`bot_skills`表
- API: `PUT /api/bots/{id}/active-mode` 启用/禁用/调整间隔

### 3.6 容错与错误隔离

| 故障场景 | 处理方式 | 影响范围 |
|---------|---------|---------|
| 单个Bot API超时 | 熔断该Bot 30s → 返回null（对方无感知） | 仅该Bot |
| 单个Bot API Key失效 | error_count累积 → 熔断 → status=INACTIVE | 仅该Bot |
| 某厂商API全面故障 | 使用该厂商的所有Bot独立熔断 | 该厂商Bot群 |
| 所有Bot离线 | Bot Manager独立于用户业务，用户聊天不受影响 | 仅Bot功能 |
| Bot消息风暴 | 信号量+队列上限+主动模式间隔下限 | 系统整体 |

### 3.7 导入集成（QQ/微信）

- **QQ Chat Exporter 集成**: 代理对接 `QQ Chat Exporter` 本地服务
  - `GET /api/bots/qq/friends` — 获取好友列表
  - `GET /api/bots/qq/groups` — 获取群列表
  - `POST /api/bots/qq/import` — 选择好友/群 + 消息条数 → 拉取消息 → 生成Bot
- **群聊过滤**: 群聊导入时仅提取指定发送者的消息（peerUid匹配）
- **文件直接上传**: `POST /api/bots/import` MultipartFile

## 4. 高并发与负载均衡

### 4.1 线程池架构

```
WebSocket 入站线程 (Tomcat NIO)
  │
  ├── 消息路由 (同步，毫秒级)
  │    ├── 持久化
  │    └── 推送在线用户
  │
  ├── Bot 异步处理 ──▶ botTaskExecutor
  │    ├── corePoolSize: 4     (常驻线程，应对常规负载)
  │    ├── maxPoolSize: 20     (峰值线程，应对20+Bot同时推理)
  │    ├── queueCapacity: 200  (缓冲队列)
  │    └── rejectedExecution: CallerRunsPolicy (满时降级同步执行)
  │
  └── 定时调度任务 ──▶ taskScheduler (4线程)
       ├── processActiveBots (fixedRate=10s)
       ├── processQueuedMessages (检查各Bot队列)
       └── cleanupOldMessages (cron: 每日3:00)
```

### 4.2 防止网络风暴

| 风暴类型 | 触发条件 | 防护措施 |
|---------|---------|---------|
| **Bot消息风暴** | 20个Bot同时启用主动模式+被动回复 | 每Bot信号量=1，队列上限10条，主动间隔≥15s |
| **群组广播风暴** | 500人群众多Bot同时回复 | @mention精确匹配 + 遍历Bot异步串行处理 + 分批推送 |
| **WebSocket连接风暴** | 20+Bot同时断连重连 | 心跳30s + 重连退避(jitter) + 每IP最多5连接 |
| **API调用风暴** | 多Bot同时调用同一LLM API | 每Bot独立信号量 + 熔断器 + 排队机制 |
| **消息去重风暴** | 客户端重试 | clientMessageId → DB UNIQUE索引兜底 |

### 4.3 限流策略

| 限流点 | 策略 | 阈值 |
|--------|------|------|
| WebSocket连接 | 每IP最大连接数 | 5 |
| 用户消息发送 | 每用户每秒 | 10条/s |
| Bot API调用 | 信号量控制（每Bot 1并发） | 全局限20并发 |
| LLM API | 各厂商独立限频监控 | 接近RPM上限告警 |
| 主动模式 | 间隔下限 + 熔断状态检查 | 15s~600s |

### 4.4 水平扩展

```
                    ┌─── Nginx (ip_hash / consistent-hash) ───┐
                    │                                           │
              ┌─────▼─────┐  ┌──────────┐  ┌──────────┐       │
              │  Node-1   │  │  Node-2  │  │  Node-N  │       │
              │  (8080)   │  │  (8081)  │  │  (808x)  │       │
              │ Bot-1..7  │  │ Bot-8..14│  │Bot-15..20│      │
              └─────┬─────┘  └────┬─────┘  └────┬─────┘       │
                    │             │             │              │
                    └─────────────┼─────────────┘              │
                                  │                            │
                    ┌─────────────▼─────────────┐              │
                    │   Redis Pub/Sub Cluster   │              │
                    │   (跨节点消息路由+状态同步) │              │
                    └─────────────┬─────────────┘              │
                                  │                            │
                    ┌─────────────▼─────────────┐              │
                    │   MySQL 8.0 (主从)        │              │
                    └───────────────────────────┘              │
```

- **无状态服务**: 每节点独立运行，状态通过Redis共享
- **Bot分布**: 20个Bot按分片策略分布到各节点
- **扩容触发**: 单节点CPU > 70%(持续5min) 或 WS连接 > 800/节点
- **Redis Pub/Sub**: `ws:user:{id}`、`ws:group:{id}`、`ws:bot` 频道跨节点路由

## 5. 性能指标

### 5.1 容量指标

| 指标 | 目标值 |
|------|--------|
| 同时在线Bot | ≥ 20 |
| API峰值QPS | 500+ |

### 5.2 延迟指标

| 指标 | 目标 |
|------|------|
| API响应 P95 | < 200ms |
| 用户消息端到端 P95 | < 500ms |
| Bot回复延迟(接收→推理→推送) P95 | < 2s |
| Bot故障恢复(熔断→恢复) | ≤ 30s |
| WebSocket心跳间隔 | 30s |

### 5.3 可靠性指标

| 指标 | 目标 |
|------|------|
| Bot错误率 | < 0.1%（API故障+超时+异常 / 总消息数） |
| 20 Bot同时活跃 CPU增量 | < 30% |
| Bot在线率 | > 99% |
| 消息可靠性 | At-Least-Once推送 + clientMessageId去重(Exactly-Once) |
| 系统可用性 | 99.9% |

## 6. 安全

- 密码 BCrypt (cost=10)，JWT HMAC-SHA256 7天过期
- API/WebSocket权限控制，输入校验
- XSS/SQL注入防护
- Bot API Key 数据库存储（plan: 加密存储）
- Bot不得执行管理操作

## 7. 数据保留

- 消息保留30天，每日凌晨3:00定时清理
- 清理前自动提取对话供Skill在线蒸馏
- Bot Skill Markdown文件永久保留（docs/skills/）

## 8. 技术栈

- 后端: Spring Boot 3.2 + Java 17 + MyBatis-Plus
- 前端: Vue 3 + Element Plus + SockJS/STOMP.js
- 数据库: MySQL 8.0（Demo: H2）
- 通信: WebSocket (STOMP) + REST API
- 缓存: Redis（生产环境）
- 消息队列: RabbitMQ（生产环境）
- LLM: 多厂商API（DeepSeek/OpenAI/Qwen/GLM等）
