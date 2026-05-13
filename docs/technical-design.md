# Chatroom 聊天室 — 技术设计文档

> v3.0 | 2026-05-13

> **v3.0 重写**: 聚焦Bot架构设计、并发控制、负载均衡、网络风暴防护。用户聊天为基础层，一笔带过。

---

## 1. 系统总览

### 1.1 架构分层

```
┌──────────────────────────────────────────────────────────────┐
│                    Frontend (Vue 3)                          │
│  SockJS/STOMP.js  ←→  WebSocket  ←→  REST API               │
└──────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│              Spring Boot Server (8080)                       │
│  ┌──────────────────┐  ┌──────────────────────────────┐     │
│  │  用户聊天层 (基础) │  │       Bot 引擎层 (核心)       │     │
│  │  - 消息路由      │  │  - BotManager (生命周期)      │     │
│  │  - 在线状态      │  │  - Skill 蒸馏 & 导入          │     │
│  │  - 好友/群组     │  │  - LLM API Client           │     │
│  │  - JWT 认证      │  │  - 并发控制 (信号量/熔断/队列) │     │
│  └──────────────────┘  │  - 主动模式调度               │     │
│                         └──────────────────────────────┘     │
│  ┌──────────────────────────────────────────────────────┐    │
│  │           Thread Pool Layer                          │    │
│  │  botTaskExecutor (4/20/200)  │  taskScheduler (4)    │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼──────┐  ┌───────────▼──────┐  ┌─────────▼─────────┐
│  MySQL 8.0  │  │  Redis Cluster  │  │  RabbitMQ Cluster │
│  (H2 Demo)  │  │  (Pub/Sub+缓存)  │  │  (消息队列)        │
└──────────────┘  └─────────────────┘  └───────────────────┘
        │                     │
        │         ┌───────────▼──────────────────────┐
        │         │  LLM API 集群 (多厂商)            │
        │         │  DeepSeek │ OpenAI │ Qwen │ GLM  │
        │         │   (每Bot独立API Key)              │
        │         └──────────────────────────────────┘
```

### 1.2 用户聊天层

用户聊天为标准IM功能栈：

| 层 | 组件 | 职责 |
|----|------|------|
| 认证 | `AuthHandshakeInterceptor` + JWT | WebSocket握手验证 + REST API Spring Security |
| 路由 | `ChatWebSocketHandler` | `@MessageMapping("/chat.send")` → 消息分发 |
| 持久化 | `MessageService.sendAndSaveMessage()` | 消息入库 + clientMessageId去重 |
| 推送 | `SimpMessagingTemplate` | `/user/queue/private/chat`、`/topic/group/{id}` |
| 在线 | `OnlineStatusManager` | `ConcurrentHashMap` 管理session→userId，心跳30s |

消息流向：客户端 → STOMP `/app/chat.send` → `handleChatMessage()` → 持久化 + 推送双方 + [Bot检测]

---

## 2. Bot 引擎核心设计

### 2.1 BotManager — 生命周期管理

`BotManager` 是整个Bot系统的中枢，管理Bot的全生命周期：

```
registerBot()        创建users记录(is_bot=1) + bot_skills记录 + Skill文档导出
     │
     ▼
[ACTIVE 运行中]
     │
     ├── handleBotMessage()    被动回复：接收用户消息 → LLM推理 → 推送回复
     ├── processActiveBots()   主动模式：定时生成开场白 → 推送给随机好友
     │
     ▼
deactivateBot()       设置status=INACTIVE，清理内存结构
     │
     ▼
permanentDelete()     删除users + bot_skills + friends + Skill文档
```

**核心数据结构**（全部 `ConcurrentHashMap`，线程安全）：

```java
// 每Bot并发控制
ConcurrentHashMap<Long, Semaphore> botSemaphores     // permit=1
// 每Bot消息缓冲队列
ConcurrentHashMap<Long, LinkedList<Map>> botQueues   // max=10
// 每Bot熔断器状态
ConcurrentHashMap<Long, Boolean> circuitBreakers     // true=OPEN
ConcurrentHashMap<Long, Long> circuitOpenTime        // 打开时间戳
// 每Bot主动模式配置
ConcurrentHashMap<Long, ActiveModeConfig> activeModeConfigs
```

### 2.2 消息处理流程（详细）

```
WebSocket 入站线程 (Tomcat NIO)
  │
  │  handleChatMessage(dto, principal)
  │
  ├── 1. messageService.sendAndSaveMessage()
  │      ├── 生成 clientMessageId (UUID)
  │      ├── INSERT messages表
  │      └── 返回 MessageVO (含自增ID)
  │
  ├── 2. WebSocket 即时推送
  │      ├── 私聊: convertAndSendToUser(sender) + convertAndSendToUser(target)
  │      └── 群聊: convertAndSend("/topic/group/{id}")
  │
  └── 3. Bot 检测与路由 (异步)
         │
         ├── 私聊: targetUser.is_bot == 1 ?
         │   └── CompletableFuture.runAsync(
         │           () -> handleBotReply(senderId, botUserId, msgVO),
         │           botTaskExecutor)
         │
         └── 群聊: content contains "@botNickname" ?
             └── CompletableFuture.runAsync(
                     () -> 遍历bots → @mention匹配 → handleBotReplyEach,
                     botTaskExecutor)
```

**Bot回复子流程** (`handleBotReply`):

```
botTaskExecutor 线程
  │
  ├── 1. botManager.handleBotMessage(botUserId, senderId, senderName, content)
  │      │
  │      ├── 1.1 获取 BotSkill (DB查bot_skills)
  │      ├── 1.2 熔断器检查
  │      │      └── circuitBreakers.get(botUserId)==true?
  │      │          ├── Yes + 未到30s → return null (静默)
  │      │          └── Yes + 已到30s → HALF-OPEN → 放行探测
  │      ├── 1.3 信号量获取 tryAcquire()
  │      │      ├── 成功 → 执行LLM调用
  │      │      └── 失败 → enqueueMessage(入队最多10条) → return null
  │      ├── 1.4 LLM API 调用
  │      │      └── llmApiClient.chat(endpoint, key, model, systemPrompt, messages)
  │      │           ├── 成功 → errorCount=0, status=ACTIVE, return reply
  │      │           └── 失败/异常 → recordError(botUserId, skill)
  │      │                └── errorCount >= 3? → 熔断OPEN
  │      ├── 1.5 sem.release() → processQueue() [异步处理排队消息]
  │      └── 1.6 return reply (or null)
  │
  └── 2. reply != null ?
         └── pushBotMessage(botUserId, targetId, reply)
              ├── sendAndSaveMessage(botUserId, dto)
              └── WS推送双方 (target + botUserId)
```

### 2.3 排队消息处理

```
handleBotMessage 释放信号量后
  │
  └── processQueue(botUserId)
       │
       └── queue.poll() → 有排队消息?
           └── CompletableFuture.runAsync(() -> {
                   handleBotMessage(botUserId, senderId, senderName, content)
                   // 如果产生回复 → pushBotReply
               }, botTaskExecutor)
```

排队消息也是异步处理，不阻塞当前LLM调用完成后的信号量释放。如果排队消息也产生了队列溢出（极端情况），会被静默丢弃。

### 2.4 熔断器实现

```java
// 状态判断:
if (circuitBreakers.get(botUserId) == true) {
    if (System.currentTimeMillis() - circuitOpenTime.get(botUserId) 
        < BOT_CIRCUIT_BREAK_SILENCE_MS) {  // 30,000ms
        return null;  // 仍在静默期，不调用LLM
    }
    // 超时，进入HALF-OPEN状态，允许一次探测
    circuitBreakers.put(botUserId, false);
}

// 错误累计:
void recordError(botUserId, skill) {
    int errors = skill.getErrorCount() + 1;
    skill.setErrorCount(errors);
    if (errors >= BOT_CIRCUIT_BREAK_THRESHOLD) {  // 3
        circuitBreakers.put(botUserId, true);
        circuitOpenTime.put(botUserId, System.currentTimeMillis());
        skill.setStatus(BOT_STATUS_CIRCUIT_BROKEN);  // 2
    }
}

// 成功后重置:
skill.setErrorCount(0);
skill.setStatus(BOT_STATUS_ACTIVE);
// 熔断器不再OPEN（handleBotMessage在成功时不清除circuitBreakers，
// 但HALF-OPEN探测成功后circuitBreakers保持false → CLOSED）
```

关键设计决策：

- **熔断状态仅存内存**：当前版本`circuitBreakers`和`circuitOpenTime`为`ConcurrentHashMap`，Server重启后所有Bot恢复为CLOSED（重新计数）。生产环境需迁移到Redis `bot:status:{botId}` Hash。
- **半开探测**：探测失败立即重新OPEN（再等30s），成功则恢复CLOSED。
- **线程安全**：`ConcurrentHashMap`保证多线程读写一致，信号量锁内完成状态变更。

---

## 3. Skill 引擎设计

### 3.1 数据流

```
┌─────────────┐   ┌──────────────────┐   ┌──────────────┐
│ 聊天记录文件  │──▶│ ChatRecordImport │──▶│  BotManager  │
│ (JSONL/TXT) │   │ Service          │   │ .registerBot │
└─────────────┘   │ .importAndGenerate│   └──────┬───────┘
                  │ .generateBotsFrom │          │
┌─────────────┐   │ Messages          │          ▼
│ 30天DB消息   │──▶└──────────────────┘   ┌──────────────┐
│             │──▶ SkillDistillerService │  users表      │
└─────────────┘   │ .distillSkills()     │  bot_skills表 │
                  └──────────────────────┘  Skill文档.md  │
                                            └──────────────┘
                                                   │
                    ┌──────────────────────────────┘
                    ▼
              ┌──────────────┐
              │ LLMApiClient │  chat(endpoint, key, model, systemPrompt, messages)
              └──────┬───────┘
                     ▼
              LLM API (DeepSeek/OpenAI/Qwen/GLM)
```

### 3.2 特征提取算法

#### 3.2.1 情绪分布（六维）

```java
// ChatRecordImportService.extractEmotions()
for (情绪维度 in {joy, anger, sad, surprise, fear, care}):
    keywords = 情绪词典[维度].split("|")  // 每维度8-15个关键词
    count = 0
    for (消息 in 用户消息列表):
        for (kw in keywords):
            if 消息.contains(kw):
                count++
                break  // 每条消息每种情绪只计1次
    记入dist[维度] = count

// 归一化: dist[维度] = count / totalCount
// 输出: {"joy": 0.25, "anger": 0.15, "sad": 0.10, ...}
```

#### 3.2.2 语言风格

```java
// ChatRecordImportService.extractStyle()
统计维度:
  句长: 中位数 / 均值 / min-max范围
  标点: 逗号密度 = 逗号总数 / 总字符数
        感叹号比例 = 含感叹号消息数 / 总消息数
  用词: Emoji使用率 / 语气词频率 / 问句比例 / 俚语比例
  习惯: topAffixes(texts, prefix=true, maxLen=4)  // 高频开头词
        topAffixes(texts, prefix=false, maxLen=3)  // 高频结尾词
  节奏: questionRatio > 0.3 ? "爱追问" : "直接"
```

#### 3.2.3 System Prompt 生成

```java
// buildPrompt()
模板变量:
  - name: 发送者昵称
  - baseTone: 主导情绪 → 性格映射
      joy→开朗, anger→直率, sad→细腻, surprise→夸张, fear→谨慎, care→贴心
  - habitOpenings: 高频开头词 (如"哈哈, 嗯, 行吧")
  - habitEndings: 高频结尾词 (如"呢, 啊, 吧")
  - responsePacing: 回复节奏
  - useEmoji / useToneWords: 是否使用Emoji/语气词

输出结构（固定六段式）:
  1. 人设与背景 (年龄段/兴趣/价值观)
  2. 目标与动机 (说人话/不教条)
  3. 性格与习惯 (主基调/习惯用语/回复节奏/emoji偏好)
  4. 边界与禁区 (不讨论违法/伤害/隐私)
  5. 对话策略 (先回应再追问/吐槽)
  6. 关系定位 (熟悉网友/同龄朋友)

结尾固定: "回复要简短自然，不超过80字，不要透露你是AI。"
```

### 3.3 Skill 双存储模型

```
注册Bot / 更新Skill
    │
    ├── 1. 写入 bot_skills 表 (运行时读取)
    │      system_prompt, emotion_profile_json, language_style_json,
    │      few_shot_examples, api_endpoint, api_key, model, status
    │
    └── 2. 自动导出 docs/skills/skill_{id}.md  (可编辑、版本管理、分享)
           YAML frontmatter + ## 分区 (system_prompt/emotion_profile/...)

手动编辑 .md
    │
    └── 3. POST /api/bots/skills/import
          解析 YAML frontmatter → 识别 skill_id → 解析所有分区
          → 写入 bot_skills 表 → 覆盖对应字段
```

**数据库表 `bot_skills`（运行时快照）**:

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 自增，对应 skill_{id}.md |
| bot_user_id | BIGINT FK | 关联 users.id |
| skill_name | VARCHAR | 技能名称 |
| system_prompt | TEXT | **核心**: LLM system message |
| emotion_profile_json | TEXT | 六维情绪画像 JSON |
| language_style_json | TEXT | 语言风格全维度 JSON (含嵌套子文档) |
| few_shot_examples | TEXT | Few-shot示例 JSON |
| api_endpoint | VARCHAR | LLM API 端点 |
| api_key | VARCHAR | API Key |
| model | VARCHAR | 模型名称 |
| status | INT | 1=活跃, 0=停用, 2=熔断 |
| error_count | INT | 连续错误计数 |
| last_active_at | DATETIME | 最后活跃时间 |

**Markdown 文件结构** (真源):

```markdown
---
skill_id: skill_42
name: 温柔知心派
version: 1.0.0
model: deepseek-chat
api_endpoint: https://api.deepseek.com/v1/chat/completions
---

## system_prompt
你是一个普通聊天用户...（直接作为 LLM system message）

## emotion_profile
base_tone: 温和
joy: 0.3 | care: 0.4 | sad: 0.1 | surprise: 0.1 | anger: 0.0 | fear: 0.1
emotion_variance: 0.35

## language_style
avg_sentence_len: 12 | use_emoji: true | emoji_rate: 0.15 | ...

## tone_signature / rhythm_profile / discourse_tactics
## topic_preferences / safety_boundaries / repair_strategy
## example_guidelines / few_shot_examples
```

每个分区在数据库中以JSON存储。`language_style_json` 包含嵌套子文档（tone_signature, rhythm_profile等），在导入/导出时展开为独立 `##` 分区。

---

## 4. 高并发设计

### 4.1 线程池架构

```java
// AsyncExecutorConfig
@Bean("botTaskExecutor")
ThreadPoolTaskExecutor:
  corePoolSize: 4       // 4个常驻线程处理常规Bot负载
  maxPoolSize: 20       // 峰值可扩展到20线程 (对应20+Bot)
  queueCapacity: 200    // 缓冲队列200个任务
  rejectedExecution: CallerRunsPolicy  // 满时降级为同步执行
  keepAliveSeconds: 60  // 空闲线程60s后回收

@Bean
ThreadPoolTaskScheduler:
  poolSize: 4           // 4个调度线程
  // 执行 @Scheduled 定时任务:
  //   - processActiveBots (fixedRate=10s)  检查主动模式Bot
  //   - cleanupOldMessages (cron: 3:00)    清理30天前消息
```

**线程安全设计**:

- `ConcurrentHashMap` 用于所有Bot状态（信号量、队列、熔断器、主动模式配置）
- 每Bot独立 `Semaphore(1)` 保证单线程处理，避免同一Bot的LLM调用重入
- `LinkedList` 作为队列仅在信号量锁内操作（offer/poll），无需额外同步
- DB操作由 MyBatis-Plus 的 `updateById` 保证行级锁

### 4.2 负载均衡

#### 单机负载路径

```
用户消息 → WebSocket (Tomcat NIO线程)
  ├── 轻量操作: 持久化 + WS推送 → 立即返回 (< 5ms)
  └── Bot检测 → botTaskExecutor 异步 → 不阻塞用户消息流
```

**关键指标**: 用户消息的发送→ACK延迟不受Bot处理时间影响（Bot异步执行）。

#### 多节点负载均衡（生产环境）

```
Nginx (ip_hash / consistent-hash)
  │
  ├── 策略1: ip_hash
  │     同一客户端IP始终路由到同一节点（WebSocket长连接亲和性）
  │     问题: Bot重连可能分配到不同节点
  │
  └── 策略2: consistent-hash (推荐)
        基于 userId 做一致性哈希，同一用户始终落在同一节点
        Bot的消息通过 Redis Pub/Sub 跨节点路由到目标Bot所在节点
        
扩容/缩容方案:
  - 新节点加入 → 一致性哈希环自动重分配部分userId
  - 旧节点移除 → 剩余节点接管，重分配用户重新建立WS连接
  - 扩容触发: 单节点 CPU > 70% (持续5min) / WS连接 > 800/节点
```

#### Bot 跨节点消息路由（Redis Pub/Sub）

```
Node-1 (Bot-A 所在节点)          Node-2 (用户U 所在节点)
  │                                   │
  │  U发送消息给Bot-A                  │
  │                                   │
  │  1. U的消息进入Node-2              │
  │  2. Node-2检测target是Bot          │
  │  3. publish("ws:bot:A", msg)  →   │
  │     ─────Redis Pub/Sub───────→    │
  │                                   4. Node-1收到 → handleBotMessage
  │   ←──publish("ws:user:U", reply)─ 5. Bot回复后推送回U所在节点
  │   6. Node-2收到 → WS推送给U        │
```

频道设计:
- `ws:user:{userId}` — 用户私聊消息
- `ws:group:{groupId}` — 群聊广播消息
- `ws:bot` — Bot管理系统消息
- `ws:presence` — 在线状态变更

### 4.3 防止网络风暴

#### 4.3.1 风暴场景分析

```
场景A: 20个Bot同时收到消息 → 20个LLM调用同时发出 → API Rate Limit触发
  防护: 每Bot Semaphore=1 → 全局限20并发 → 排队机制吸收峰值

场景B: 500人群里5个Bot被@mention → 5个LLM调用 + 5条群消息推送
  防护: 遍历Bot异步串行 → 每个Bot独立回复 → 间隔自然错开

场景C: 主动模式20个Bot同时到间隔 → 20条开场白同时发出
  防护: taskScheduler 4线程轮询 → 自然错开 + 随机选择好友

场景D: 某Bot API故障 → 连续重试 → 线程耗尽
  防护: 熔断器30s静默 + error_count持久化

场景E: 客户端断连重连循环 → WS连接风暴
  防护: 每IP 5连接上限 + 心跳30s + 断连不重试主动模式消息
```

#### 4.3.2 限流层级

| 层级 | 位置 | 机制 | 当前状态 |
|------|------|------|---------|
| L1 连接限流 | WebSocket握手 | 每IP最大5连接 | 📋 计划中 |
| L2 用户消息限流 | ChatWebSocketHandler | 每用户10条/s | 📋 计划中 |
| L3 Bot并发限流 | BotManager.botSemaphores | 每Bot 1并发 | ✅ 已实现 |
| L4 全局Bot限流 | botTaskExecutor.maxPoolSize | 20线程上限 | ✅ 已实现 |
| L5 LLM API限流 | LLMApiClient | 各厂商独立监控 | 📋 计划中 |

#### 4.3.3 群组广播优化

```
500人群消息发送:
  1. 消息持久化 (1次DB INSERT)
  2. 在线成员查询 (Redis SMEMBERS group:members:{id})
  3. 分批推送 (每批50人，间隔50ms)
  4. Bot检测: 仅@mention触发 (遍历bot列表 → 文本匹配nickname/username)
  
关键: Bot回复不与原始消息混入同一广播批次
     Bot回复独立推送 (/topic/group/{id})，作为新的独立消息
```

---

## 5. 消息可靠性

### 5.1 三层去重

```
clientMessageId (UUID v4)
  │
  ├── L1 布隆过滤器 (计划中)
  │      快速判定"可能存在" → 命中则进入L2
  │      未命中 → 一定是新消息 → 直接入库
  │
  ├── L2 Redis去重缓存 (计划中)
  │      SET msg:dedup:{clientMessageId} EX 86400
  │      命中 → 返回已有 messageId，不重复推送
  │
  └── L3 DB UNIQUE索引 (已实现)
         UNIQUE INDEX idx_client_msg (client_message_id)
         INSERT成功 → 新消息
         DuplicateEntry → 幂等返回
```

### 5.2 消息有序

- 全局自增ID (`messages.id` AUTO_INCREMENT) 作为排序依据
- 客户端按 `id` 排序显示，不依赖时间戳（避免NTP时钟回拨）
- Bot消息与用户消息共用同一自增序列，全局有序

### 5.3 消息状态机

```
SENDING ──(WS发送)──▶ SENT ──(对方ACK)──▶ DELIVERED ──(已读ACK)──▶ READ
                          │
                          └──(30s超时+重试3次)──▶ FAILED
```

Bot消息状态流与用户消息一致，通过 `clientMessageId` 前缀区分来源：
- `BQ_xxx` — Bot被动回复 (Bot Queue)
- `Axxx` — Bot主动消息 (Active)
- `BOT_xxx` — Bot通过WebSocket Handler发出的消息
- 用户消息 — 标准UUID格式

---

## 6. 关键类设计

### 6.1 服务层

| 类 | 职责 | 关键方法 |
|----|------|---------|
| `BotManager` | Bot生命周期、并发控制、消息处理 | `registerBot`, `handleBotMessage`, `processQueue`, `setActiveMode`, `processActiveBots` |
| `ChatRecordImportService` | 文件导入→解析→特征提取→Bot生成 | `importAndGenerate`, `generateBotsFromMessages`, `extractEmotions`, `extractStyle`, `buildPrompt` |
| `SkillDistillerService` | 30天DB消息蒸馏→Skill配置 | `distillSkills`, `extractEmotionDistribution`, `generateSystemPrompt` |
| `BotSkillDocService` | Skill Markdown导出/删除 | `exportSkillDoc`, `deleteSkillDoc`, `buildMarkdown` |
| `SkillDocImportService` | Skill Markdown导入→解析→写入DB | `importSkillDoc`, `parseFrontMatter`, `parseSections` |
| `LLMApiClient` | LLM API调用（Chat Completion兼容） | `chat`, `healthCheck` |
| `QQChatExporterClient` | QQ Chat Exporter本地服务代理 | `healthCheck`, `getFriends`, `getGroups`, `fetchMessages` |

### 6.2 控制器

| 端点 | 方法 | 说明 |
|------|------|------|
| `GET /api/bots/` | `list()` | 获取所有Bot |
| `GET /api/bots/active` | `active()` | 获取活跃Bot |
| `GET /api/bots/count` | `count()` | 在线Bot数 |
| `GET /api/bots/config` | `config()` | 默认LLM配置（Key脱敏） |
| `POST /api/bots/register` | `register()` | 注册新Bot |
| `DELETE /api/bots/{id}` | `deleteBot()` | 永久删除Bot |
| `PUT /api/bots/{id}/active-mode` | `setActiveMode()` | 启用/禁用/调整主动模式 |
| `POST /api/bots/distill` | `distill()` | 触发30天消息蒸馏 |
| `POST /api/bots/import` | `importRecords()` | 上传文件导入 |
| `POST /api/bots/skills/import` | `importSkillDoc()` | 上传.md导入Skill |
| `POST /api/bots/qq/import` | `qqImport()` | QQ CE选择导入 |

### 6.3 常量配置

```java
// Bot限制
BOT_CIRCUIT_BREAK_THRESHOLD = 3      // 熔断阈值（连续失败次数）
BOT_CIRCUIT_BREAK_SILENCE_MS = 30000  // 熔断静默期（30秒）
BOT_MAX_QUEUE_SIZE = 10              // 每Bot消息队列容量
BOT_MAX_CONCURRENCY = 1              // 每Bot最大并发推理数

// Bot状态
BOT_STATUS_ACTIVE = 1         // 活跃
BOT_STATUS_INACTIVE = 0       // 停用
BOT_STATUS_CIRCUIT_BROKEN = 2 // 熔断

// 蒸馏参数
DISTILL_MIN_MESSAGES = 100    // 最小消息数阈值
DISTILL_CONTEXT_WINDOW = 4    // 上下文窗口
DISTILL_MAX_WORDS = 50
DISTILL_MIN_WORDS = 5
DISTILL_MAX_CHARS = 200
DISTILL_MIN_CHARS = 5

// 消息
HISTORY_RETENTION_DAYS = 30   // 消息保留天数
RECALL_WINDOW_MS = 120_000    // 撤回窗口（2分钟）
```

---

## 7. 实施规划

### 7.1 已实现 (✅)

| 功能 | 状态 | 关键文件 |
|------|------|---------|
| Bot注册/删除/上下线 | ✅ | `BotManager.registerBot/deactivateBot/permanentDelete` |
| 逐Bot信号量并发控制 | ✅ | `ConcurrentHashMap<Long, Semaphore>` permit=1 |
| 消息缓冲队列(FIFO 10) | ✅ | `ConcurrentHashMap<Long, LinkedList>` |
| 熔断器 (3次→30s→半开) | ✅ | `ConcurrentHashMap<Long, Boolean> circuitBreakers` |
| 异步Bot处理线程池 | ✅ | `botTaskExecutor` (4/20/200) |
| 调度器线程池 | ✅ | `taskScheduler` (4线程) |
| 主动聊天模式 | ✅ | `setActiveMode/processActiveBots/getActiveModeConfig` |
| 聊天记录文件导入(QQ/微信/通用) | ✅ | `ChatRecordImportService.importAndGenerate` |
| QQ Chat Exporter集成 | ✅ | `QQChatExporterClient` + `BotController.qqImport` |
| 特征提取(情绪/风格/句式/节奏) | ✅ | `ChatRecordImportService.extractEmotions/extractStyle` |
| System Prompt生成 | ✅ | `ChatRecordImportService.buildPrompt` |
| Skill Markdown导出 | ✅ | `BotSkillDocService.exportSkillDoc` |
| Skill Markdown导入 | ✅ | `SkillDocImportService.importSkillDoc` |
| 在线蒸馏 | ✅ | `SkillDistillerService.distillSkills` |
| 导入自动加好友 | ✅ | `ChatRecordImportService.generateBots` 内 friendMapper.insert |
| WebSocket Bot路由(私聊+群@) | ✅ | `ChatWebSocketHandler.handleBotReply/handleGroupBotReply` |
| 多厂商API Key隔离 | ✅ | 每Bot独立 `api_endpoint/api_key/model` |

### 7.2 计划中 (📋)

| 功能 | 优先级 | 说明 |
|------|--------|------|
| **L1-L2限流** | P0 | 连接限流(每IP 5) + 消息限流(每用户10条/s)，防止恶意刷接口 |
| **Redis跨节点Bot状态** | P0 | `bot:status:{botId}` Hash同步熔断/主动模式状态，解决内存状态丢失问题 |
| **主动模式持久化** | P1 | `bot_skills`表新增`active_mode`/`active_interval`字段，服务重启后恢复 |
| **Bot WebSocket连接池** | P1 | Bot实例化真实WS连接（当前被动回复走HTTP→LLM），减少延迟 |
| **布隆过滤器去重** | P1 | L1快速去重，减少Redis/DB压力 |
| **多厂商故障转移** | P2 | API健康检查 + 厂商级熔断 + 自动切换备用厂商 |
| **Bot监控面板** | P2 | Bot延迟/错误率/在线状态/API调用量实时看板 |
| **Skill版本回滚** | P2 | Skill配置多版本存档 + 一键回滚到历史版本 |
| **群聊Bot隔离** | P2 | 群聊中Bot仅回复@mention消息（当前已实现），增加频率限制防止Bot刷群 |
| **API Key加密存储** | P2 | `bot_skills.api_key` 当前明文存储，需AES加密 |

---

## 8. 监控与运维

### 8.1 关键指标

| 指标 | 采集点 | 告警阈值 |
|------|--------|---------|
| Bot回复延迟 P95 | `BotManager.handleBotMessage` 耗时 | > 3s |
| Bot错误率 | `error_count` / 总调用次数 (每Bot) | > 5%/min |
| Bot在线数 | `getActiveBots().size()` | < 期望数 |
| 线程池队列长度 | `botTaskExecutor.getQueueSize()` | > 150 |
| 线程池活跃线程 | `botTaskExecutor.getActiveCount()` | = maxPoolSize |
| 熔断Bot数 | `circuitBreakers` 中 value=true 的数量 | > 5 |
| LLM API调用量 | 各厂商独立计数 | 接近RPM上限 |

### 8.2 日志规范

```
Bot注册:     "Bot registered: id={}, name={}, skill={}"
Bot回复:     "Bot {} (active) sent to {}: {}"
Bot熔断:     "Bot {} circuit breaker OPEN after {} errors"
Bot恢复:     "Bot {} circuit half-open, probing"
Bot错误:     "Bot {} API call failed" + exception
主动模式:    "Bot {} active mode: enabled={}, interval={}s"
导入生成:    "Generated {} bots from imported records"
蒸馏生成:    "Generated {} skill configs from chat records"
```

---

## 9. 测试设计

### 9.1 并发测试（核心重点）

- 20+ Bot同时在线，随机向不同Bot发送消息，验证：
  - 每Bot信号量正确串行化（无重入）
  - 熔断器正确触发和恢复
  - 队列满时静默丢弃
  - 线程池不拒绝任务（CallerRunsPolicy降级）
  - WebSocket推送不丢消息
- 主动模式20个Bot同时触发 → 验证错开执行

### 9.2 导入测试

- QQ CE JSON v5+ 格式解析正确性
- QQ CE TXT 格式解析正确性
- 微信 TXT 格式解析正确性
- 群聊消息peerUid过滤正确性
- 情绪/风格提取结果合理性校验

### 9.3 集成测试

- 端到端: 上传文件 → 生成Skill → 注册Bot → WS连接 → 发消息 → 收到回复
- Skill Markdown: 导出 → 手动修改 → 导入 → 数据库更新验证
- 好友关系: 导入后自动建立creator→bot好友

### 9.4 回归测试

- Skill版本回滚: 旧版.md导入 → 覆盖当前配置
- Bot切换Skill: update bot_skills → Bot立即使用新system_prompt
- API Key失效: error_count累积 → 熔断触发 → 状态迁移验证
