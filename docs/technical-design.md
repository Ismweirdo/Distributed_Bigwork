# Chatroom 聊天室 — 技术设计文档

## 1. 系统架构

```
┌─────────────┐     ┌──────────────────────────────────┐     ┌──────────┐
│   Browser   │────▶│  Spring Boot Server (8080)        │────▶│  MySQL   │
│  (Vue 3)    │◀────│  ├ REST API (HTTP)               │◀────│  (H2)    │
│             │     │  ├ WebSocket (STOMP)              │     └──────────┘
│  SockJS/    │     │  ├ Spring Security + JWT          │
│  STOMP.js   │     │  └ MyBatis-Plus ORM               │
└─────────────┘     └──────────────────────────────────┘
```

### 扩展架构 (生产环境)
```
                   ┌──────────┐    ┌──────────┐
                   │  Redis   │    │ RabbitMQ │
                   │ (缓存)   │    │ (消息队列)│
                   └──────────┘    └──────────┘
                        ▲               ▲
                        │               │
┌──────────┐    ┌──────────────────────────┐    ┌──────────┐
│ Browser  │◀──▶│  Spring Boot Cluster     │◀──▶│  MySQL   │
│          │    │  (N instances)           │    │  (主从)  │
└──────────┘    └──────────────────────────┘    └──────────┘
```

## 2. 数据库设计

### 表结构
- `users` — 用户表 (id, username, password, nickname, avatar, status, last_login_time, created_at, updated_at)
- `friends` — 好友关系表 (id, user_id, friend_id, status, created_at)
- `groups` — 群组表 (id, name, avatar, owner_id, announcement, max_members, created_at)
- `group_members` — 群成员表 (id, group_id, user_id, role, nickname_in_group, joined_at)
- `messages` — 消息表 (id, message_type, sender_id, target_id, reply_to_id, content, content_type, status, created_at)

### 消息表索引
- PRIMARY KEY (id) — 全局自增，保证消息顺序
- INDEX idx_target_time (message_type, target_id, created_at) — 会话查询
- INDEX idx_private_query (sender_id, target_id, created_at) — 私聊双向查询
- INDEX idx_created_at (created_at) — 定时清理

## 3. 实时通信设计

### WebSocket 连接流程
1. 客户端通过SockJS连接 `/ws/chat?token={jwt}`
2. 握手拦截器验证JWT，提取userId存入SessionAttributes
3. 连接建立后，订阅 `/user/queue/private/chat`（私聊）和 `/topic/group/{id}`（群聊）
4. 发送消息通过 `/app/chat.send`

### 消息协议
```json
// Client → Server
{
  "content": "消息内容",
  "messageType": 0,
  "targetId": 2,
  "replyToId": null,
  "contentType": 0,
  "clientMessageId": "uuid"
}

// Server → Client
{
  "type": "CHAT",
  "messageId": 12345,
  "messageType": 0,
  "senderId": 1,
  "senderName": "Alice",
  "targetId": 2,
  "replyToId": null,
  "replyToContent": null,
  "content": "消息内容",
  "createdAt": "2024-05-05T12:00:00"
}
```

### 消息可靠性
1. 客户端发送消息 → 服务端推送+持久化 → 返回ACK
2. 接收方在线 → 实时推送
3. 接收方离线 → 上线后从数据库拉取

## 4. 高并发设计

### 连接管理
- ConcurrentHashMap管理在线用户 (单机)
- 生产环境使用Redis Pub/Sub跨节点同步

### 异步处理
- 消息先推后存: WebSocket推送 → 异步写DB
- 生产环境引入RabbitMQ: WS → MQ → Batch Insert DB

### 缓存策略
- 在线用户状态: 本地Map / Redis Hash
- 最近消息: Redis ZSet (TTL=1h)
- JWT Session: Redis String (TTL=7d)

### 限流
- API: Guava RateLimiter / Sentinel
- WebSocket连接: 每IP限制5个连接

## 5. 消息一致性保证

1. **全局有序**: 自增ID保证消息全局顺序
2. **去重**: clientMessageId (UUID) 防止重复
3. **回复追踪**: reply_to_id 关联引用消息
4. **送达确认**: ACK机制 + 消息状态追踪

## 6. 30天数据保留

- 每日凌晨3:00定时任务清理
- 清除条件: `created_at < NOW() - 30 days`
- 后续可升级为MySQL分区表滚动删除

## 7. 安全设计

- 密码: BCrypt (cost=10)
- 认证: JWT (HMAC-SHA256, 7天过期)
- API授权: Spring Security + @PreAuthorize
- WebSocket: 握手阶段JWT验证
- XSS防护: 前端输入过滤
- SQL注入: MyBatis-Plus参数化查询
