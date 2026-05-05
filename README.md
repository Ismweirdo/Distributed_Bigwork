# 分布式大作业：Chatroom 聊天室

本项目是分布式课程大作业，目标是实现一个类 QQ 的实时聊天室。前后端分离，HTTP + WebSocket 双通道，支持私聊、群聊、好友管理等核心能力，并预留高并发扩展方案。

## 功能特性

- 用户注册/登录（JWT + BCrypt）
- 个人信息维护与在线状态
- 好友管理（申请/处理/删除）
- 私聊：实时消息、引用回复、撤回、已读状态、历史记录
- 群聊：创建/邀请/移除成员、退出群组、群内广播
- 消息可靠性与 30 天保留策略

## 技术栈

- **前端**：Vue 3 + Vite + Element Plus + Pinia + Axios + SockJS/STOMP
- **后端**：Spring Boot 3.2 + Java 17 + WebSocket(STOMP) + Spring Security + JWT + MyBatis-Plus
- **数据库**：H2（默认 Demo），MySQL 8（生产）
- **可选组件**：Redis、RabbitMQ（生产扩展）
- **API 文档**：Knife4j(OpenAPI3)

## 系统架构概览

- 浏览器通过 REST API 与 WebSocket 与后端交互
- 后端支持无状态部署，生产环境可通过 Redis/RabbitMQ 扩展

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

## 相关文档

- 需求文档：`docs/requirements.md`
- 技术设计：`docs/technical-design.md`
