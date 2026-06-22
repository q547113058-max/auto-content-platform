# 技术决策 — Auto Content Platform

## 架构

```
auto-content-platform/
├── backend/                   # Python FastAPI
│   ├── models/                # SQLAlchemy ORM
│   ├── routers/               # API 路由
│   ├── services/              # 业务逻辑
│   │   ├── session_manager.py  # Playwright 浏览器会话管理
│   │   └── cookie_parser.py   # Cookie 字符串解析
│   ├── schemas/               # Pydantic 模型
│   └── config.py              # 配置
├── frontend/                  # Vue 3 + Vite
│   ├── src/views/             # 页面组件
│   ├── src/api/               # API 调用
│   └── src/composables/       # 组合式函数
└── docs/                      # 项目文档
```

## 技术栈

| 层 | 技术 | 原因 |
| --- | --- | --- |
| 前端 | Vue 3 + Vite + Element Plus | 用户偏好，快速开发管理后台 |
| 后端 | Python FastAPI (3.13) | 异步支持，与 Playwright/LLM 集成方便 |
| ORM | SQLAlchemy (Async) | 与 FastAPI 原生集成 |
| 数据库 | PostgreSQL (主) → SQLite (降级) | PG 功能完整，SQLite 零配置兜底 |
| 浏览器自动化 | Playwright | 知乎/微博发布需真实浏览器 |
| 内容生成 | GPT API (SSE 流式) | 长文本生成 |
| 图片生成 | Doubao-Seedream-5.0-lite | 文章配图 |
| 发布 | BackgroundTasks + ThreadPool | 长任务异步执行，线程隔离避免 anyio 冲突 |

## 关键决策

### 1. 发布任务线程隔离
- **问题**：FastAPI BackgroundTasks 在 uvicorn anyio 事件循环中运行 Playwright 冲突
- **决策**：发布任务切换到独立线程（ThreadPoolExecutor），每个线程创建独立的 ProactorEventLoop
- **日期**：2026-06

### 2. SessionManager 线程安全
- **问题**：跨线程共享 Playwright Browser 实例导致 CDP 连接断裂
- **决策**：不跨线程缓存 BrowserContext，始终从 StorageState 重新创建
- **日期**：2026-06

### 3. Cookie 导入后真实验证
- **问题**：导入后只乐观设 active，发布时才报错
- **决策**：import-cookie 后立即调用 get_context() 真实验证
- **日期**：2026-06-22

### 4. 三模式内容生成
- **决策**：支持纯产品评测、纯公司分析、混合三种模式
- **日期**：2026-06

### 5. 数据库降级策略
- **决策**：PostgreSQL 连接失败自动切换 SQLite
- **日期**：2026-06

### 6. 无官方 API 则放弃
- **决策**：依赖官方 API 的功能若无 API 支持直接取消，不做 hack
- **日期**：2026-06

## 条件质量规则

当前启用的规则：

| 规则 | 状态 |
| --- | --- |
| `framework-language` (Python + Vue 3) | ✅ 已启用 |
| `database` (PostgreSQL) | ✅ 已启用 |
| `social-distribution` (知乎/微博) | ✅ 已启用 |
| `media-generation` (Seedream) | ✅ 已启用 |
| `hooks-runtime` | ❌ 未启用 |
| `agentmemory` | ❌ 未评估 |
| `orchestration` | ❌ 暂不需要 |
| `devops-infra` | ❌ 未涉及 |
