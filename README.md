# AutoContentPlatform — 中文图文社交平台自动化运营系统

> 面向电商/消费品的多平台内容自动化运营系统。
> 一次输入产品信息，AI 自动生成6个平台适配内容，自动发布，自动采集数据，自动优化。

## 支持的6个图文平台

| 平台 | 发布方式 | 登录方式 |
|------|----------|----------|
| 小红书 | Playwright 自动化 | Cookie 注入 + StorageState 持久化 |
| 知乎 | Playwright 自动化 | Cookie 注入 + StorageState 持久化 |
| 微博 | Playwright 自动化 | Cookie 注入 + StorageState 持久化 |
| 微信公众号 | 官方 API (AppID+AppSecret) | API Token，无需浏览器 |
| 今日头条 | Playwright 自动化 | Cookie 注入 + StorageState 持久化 |
| 抖音图文 | Playwright 自动化 | Cookie 注入 + StorageState 持久化 |

## 系统架构

```
┌─────────────────────────────────────────────┐
│                     管理后台 (Vue3)        │
├─────────────────────────────────────────────┤
│                   API Gateway (FastAPI)      │
├──────┬──────┬──────┬──────┬──────────────────┤
│ 任务 │ AI   │ 发布 │ 数据 │  优化学习 (⭐)     │
│ 调度 │ 生成 │ 引擎 │ 抓取 │  (改动记录+去重+验证) │
├──────┴──────┴──────┴──────┴──────────────────┤
│             会话管理引擎 (三层保活)            │
├──────┬──────┬──────────────────────────────┤
│ Postgres│ Redis│  MinIO (图片存储)           │
├──────┴──────┴──────────────────────────────┤
│            Playwright 浏览器集群 (Docker)      │
└─────────────────────────────────────────────┘
```

## 快速启动

### 前置条件

- Docker Desktop 已安装
- Python 3.11+ (本地开发用)
- Redis (本地开发用，Docker 版也可)

### 方式一：Docker 一键启动 (推荐)

```bash
# 1. 复制环境配置
cp .env.example .env
# 修改 .env 中的 AI_API_KEY 等配置

# 2. 启动全部服务
docker-compose up -d

# 3. 访问 API 文档
open http://localhost:8000/docs
```

### 方式二：本地开发启动

```bash
# 1. 安装依赖
cd backend
pip install -r requirements.txt
playwright install chromium

# 2. 启动数据库（需要本地 Postgres）
# 或使用 Docker 只启动数据库部分：
docker-compose up -d postgres redis minio

# 3. 初始化数据库
cd backend
alembic upgrade head

# 4. 启动 API 服务
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 5. 启动 Celery Worker（新终端）
celery -A backend.tasks.content_tasks worker -l info

# 6. 启动 Playwright 浏览器（新终端，用于调试）
python -m playwright.cli codegen --target python -o login_xhs.py https://creator.xiaohongshu.com/login
```

## 核心功能

### 1. AI 内容生成

```bash
# 调用 API 生成内容
curl -X POST http://localhost:8000/api/v1/contents/generate \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": 1,
    "platforms": ["xiaohongshu", "zhihu", "weibo"]
  }'
```

### 2. 账号登录 / 会话管理

```bash
# 触发小红书登录（返回 VNC 连接信息）
curl http://localhost:8000/api/v1/sessions/xiaohongshu/login

# 检查所有账号会话状态
curl http://localhost:8000/api/v1/sessions/status
```

### 3. 内容发布

```bash
# 提交发布任务
curl -X POST http://localhost:8000/api/v1/publish \
  -H "Content-Type: application/json" \
  -d '{"content_id": 1, "account_id": 1}'
```

### 4. 数据分析 + 优化建议

```bash
# 分析产品在各平台的数据表现，生成优化建议
curl -X POST http://localhost:8000/api/v1/optimizer/analyze/1
```

## 目录结构

```
auto-content-platform/
├── backend/                    # FastAPI 后端
│   ├── main.py                 # 入口
│   ├── config.py               # 全局配置
│   ├── models/                # SQLAlchemy 模型（8张表）
│   ├── schemas/               # Pydantic 模型
│   ├── routers/               # API 路由
│   ├── services/              # 业务逻辑
│   │   ├── ai_generator.py    # AI 内容生成
│   │   ├── publisher_base.py  # 发布引擎基类
│   │   ├── publisher/         # 6个平台发布器
│   │   ├── session_manager.py # 会话管理（三层保活）
│   │   ├── scraper.py        # 数据抓取
│   │   └── optimizer.py      # 优化学习
│   ├── prompts/              # 平台提示词（6个JSON）
│   └── tasks/                # Celery 任务
├── playwright_automation/      # Playwright 自动化脚本
├── storage_states/            # 浏览器会话持久化
├── frontend/                 # Vue3 管理后台
├── docker-compose.yml        # Docker 编排
├── requirements.txt          # Python 依赖
└── .env.example             # 环境变量模板
```

## 优化学习模块 (⭐ 核心)

这是系统最核心的模块 —— 记住每次改动的原因，避免重复错误。

| 功能 | 说明 |
|------|------|
| **改动记录** | 每次优化改动自动记录，含 before/after 对比 |
| **AI 语义去重** | 新优化建议与历史记录做 AI 语义匹配，避免重复 |
| **效果验证** | 改动后自动对比下一篇内容的数据，验证效果 |
| **版本管理** | 提示词支持版本回滚，可对比不同版本效果 |

## 环境变量说明

详见 [.env.example](.env.example) — 主要需要配置：

- `DEEPSEEK_API_KEY` — AI 生成内容用（或配置 `QWEN_API_KEY`）
- `IMAGE_GEN_API_KEY` — AI 生图用（Seedream / 通义万象）
- `DB_*` — 数据库配置
- `REDIS_*` — Redis 配置

## 已知限制

| 限制 | 原因 | 缓解方案 |
|------|------|------------|
| 小红书/知乎/抖音等无官方发布 API | 平台政策 | Playwright 自动化（存在封号风险） |
| Cookie 有效期不确定 | 平台策略 | 6小时健康检查 + 过期预警 |
| 账号封禁风险 | 平台反爬 | 代理IP + 发布频率控制 + 反检测脚本 |
| 微信公众号需要企业资质 | 微信政策 | 个人可用测试号或申请服务号 |

## 开发进度

- [x] Phase 1: 基础框架 + 会话管理
- [x] Phase 2: AI 生成 + 发布引擎骨架
- [ ] Phase 3: 数据抓取 + 分析（部分完成）
- [ ] Phase 4: 优化学习 + 闭环（部分完成）
- [ ] Phase 5: 生产化部署 + 前端管理后台
- [ ] 前端 Vue3 管理后台界面

## License

MIT
