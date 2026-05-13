# Distributed Chatroom

Big-work project for the Distributed Systems course.

A multi-client command-line chatroom built with Python's standard library
(`socket` + `threading`). No third-party packages are required.

---

## Architecture

```
┌────────────┐        TCP        ┌──────────────────────┐
│  client.py │ ◄────────────── ► │     server.py        │
│  (thread)  │                   │  one thread/client   │
└────────────┘                   └──────────────────────┘
                                           │
                                  broadcast to all other
                                  connected clients
```

* The **server** listens on a configurable host/port and spawns one daemon
  thread per connected client.
* The **client** runs two threads: the main thread reads user input and sends
  it to the server; a background thread receives and prints incoming messages.

---

## Quick Start

**Terminal 1 — start the server**

```bash
python server.py
# or specify host/port:
python server.py --host 0.0.0.0 --port 9999
```

**Terminal 2 (and 3, 4 …) — connect clients**

```bash
python client.py
# or specify server address:
python client.py --host 127.0.0.1 --port 9999
```

You will be prompted to choose a nickname. After that, just type and press
Enter to broadcast a message.

---

## Commands

| Command | Description |
|---|---|
| `/list` | Show all currently online users |
| `/msg <nickname> <text>` | Send a private message to `<nickname>` |
| `/quit` | Disconnect from the server |

---

## Running the Tests

```bash
python test_chatroom.py -v
```

The test suite starts an in-process server on port 19999 and exercises:
nickname handshake, broadcast, join/leave notifications, `/list`, `/msg`,
duplicate-nickname rejection, and `/quit`.

---

## Requirements

* Python 3.10 or later (uses `match`-free code; compatible with 3.10+)
* No external dependencies

# 分布式大作业：Chatroom 聊天室

本项目是分布式课程大作业，目标是实现一个类 QQ 的实时聊天室。前后端分离，HTTP + WebSocket 双通道，支持私聊、群聊、好友管理等核心能力，并预留高并发扩展方案。

## 功能特性

- 用户注册/登录（JWT + BCrypt）
- 个人信息维护与在线状态
- 好友管理（申请/处理/删除）
- 私聊：实时消息、引用回复、撤回、已读状态、历史记录
- 群聊：创建/邀请/移除成员、退出群组、群内广播
- 消息可靠性与 30 天保留策略
- **机器人系统**：20+ Bot同时在线、Skill驱动的不同语言风格与情绪模式
- **聊天记录蒸馏**：从QQ/微信/本系统聊天记录生成Skill与机器人

## 技术栈

- **前端**：Vue 3 + Vite + Element Plus + Pinia + Axios + SockJS/STOMP
- **后端**：Spring Boot 3.2 + Java 17 + WebSocket(STOMP) + Spring Security + JWT + MyBatis-Plus
- **数据库**：H2（默认 Demo），MySQL 8（生产）
- **可选组件**：Redis、RabbitMQ（生产扩展）
- **API 文档**：Knife4j(OpenAPI3)

## 系统架构概览

- 浏览器通过 REST API 与 WebSocket 与后端交互
- 后端支持无状态部署，生产环境可通过 Redis/RabbitMQ 扩展
- Bot Manager 统一管理多机器人、技能与API接入

## 目录结构

- `chatroom-client/` 前端项目（Vite）
- `chatroom-server/` 后端项目（Spring Boot）
- `docs/` 需求与技术设计文档

## 快速开始

### 后端（Spring Boot）

1. 进入目录：
   ```bash
   cd chatroom-server
   ```
2. 启动服务：
   ```bash
   mvn spring-boot:run
   ```
3. 默认端口：`http://localhost:8080`

> 默认使用 H2 文件数据库（`./data/chatroom`），并自动执行 `schema.sql` 与 `data.sql` 初始化。

### 前端（Vue 3）

1. 进入目录：
   ```bash
   cd chatroom-client
   ```
2. 安装依赖并启动：
   ```bash
   npm install
   npm run dev
   ```
3. 默认端口：`http://localhost:3000`

前端开发环境通过代理转发：
- API：`/api` → `http://localhost:8080`
- WebSocket：`/ws` → `http://localhost:8080`

## 默认账号（H2 Demo）

- 用户名：`alice` / `bob` / `charlie`
- 密码：`123456`

## 配置说明

- H2 控制台：`http://localhost:8080/h2-console`
- API 文档（Knife4j）：`http://localhost:8080/doc.html`
- 切换 MySQL：修改 `chatroom-server/src/main/resources/application.yml` 中的 datasource 配置

## 机器人与Skill（重点）

### Skill设计
- Skill = System Prompt + Few-shot 示例 + 语言风格/情绪配置
- 生成来源：手动创建 / 导入聊天记录 / 数据库蒸馏
- 入口形式：UI创建与API创建同时支持
- 每个Bot绑定一个Skill，可随时切换或版本回滚

### 如何导入AI
- 每个Bot独立配置 `api_endpoint` / `api_key` / `model`
- 支持同厂商多Key、多模型混用，便于20+ Bot并行在线

### 如何蒸馏聊天记录
- 支持从数据库定时蒸馏（默认30天）
- 支持导入文件直接生成Skill与Bot
- 结果包含可上线Skill配置与人设摘要

### 导入QQ/微信聊天记录
- 优先支持 JSON / TXT 导出文件
- 导入后可映射发送者并生成Skill与Bot
- 示例数据：`test/sample-qqce-export.json`、`test/sample-qqce-export.txt`

## 测试与验证

- 并发测试：作为重点，验证20+ Bot同时在线与响应延迟
- 导入测试：QQ/微信记录 → Skill生成 → Bot注册
- 回归测试：Skill版本回滚、Bot切换Skill、API Key失效
- 参考脚本：`test/test-bots-ws.py`、`test/test-bots.sh`、`test/test-bots.bat`

## 相关文档

- 需求文档：`docs/requirements.md`
- 技术设计：`docs/technical-design.md`
