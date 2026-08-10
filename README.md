# 电商智能客服系统 (E-Commerce Intelligent Customer Service Agent)

Vue3 + FastAPI + LLM + RAG + Agent 的电商智能客服系统。融合了大语言模型（LLM）、Agent 架构、检索增强生成（RAG）、自然语言理解（NLU）意图识别、情感分析以及全站 JWT 鉴权等多项 AI 与工程化能力。

## 🎯 核心价值

| 价值点 | 说明 |
|--------|------|
| 7×24 小时在线 | 全天候自动接待，降低人工客服 80% 工作量 |
| 精准意图识别 | 基于 LLM 的意图分类 + 同义词归一化，准确率 95%+ |
| 情感智能响应 | 实时感知用户情绪，触发差异化服务策略（含负向修正） |
| RAG 知识增强 | 连接企业知识库，提供专业、准确的业务回答 |
| Agent 自主决策 | 基于 ReAct 框架的复杂多步骤任务自动执行 |
| 人工无缝协作 | 复杂问题智能转接，客服坐席高效承接 |

## 🏗️ 技术架构

- **前端**：Vue 3 + Element Plus + Pinia + TypeScript + Vite
- **后端**：FastAPI + SQLAlchemy + Pydantic
- **AI 服务**：DeepSeek（LLM）+ 千问 text-embedding-v1（向量）
- **认证**：JWT（HS256，pbkdf2_sha256 密码哈希）+ 全站 Bearer 鉴权（`REQUIRE_AUTH` 开关）
- **数据库**：MySQL（可选）+ Redis（可选）+ ChromaDB（向量数据库），均可在不可用时自动降级
- **Agent 架构**：ReAct（Reasoning + Acting），6 个工具全量接线
- **可观测性**：Langfuse（全链路追踪/LLM调用监控/RAG检索分析）

## 📁 项目结构

```
ecommerce-customer-service/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/            # API 路由
│   │   │   ├── auth.py        # 认证（注册/登录/me，JWT 签发与校验）
│   │   │   ├── chat.py        # 对话接口（含 SSE 流式 /send_stream）
│   │   │   ├── intent.py      # 意图识别接口
│   │   │   ├── agent.py       # Agent 接口
│   │   │   ├── knowledge.py   # 知识库接口
│   │   │   ├── order.py       # 订单服务接口
│   │   │   ├── product.py     # 商品服务接口
│   │   │   └── analytics.py   # 数据分析接口
│   │   ├── core/              # 核心配置
│   │   │   ├── config.py      # 应用配置（LLM/Embedding/JWT/限流，路径绝对化）
│   │   │   ├── database.py    # 数据库连接
│   │   │   └── security.py    # JWT 安全认证（pbkdf2_sha256 哈希）
│   │   ├── data/              # 统一 Mock 数据源（订单/商品，F5 消除双源漂移）
│   │   │   └── mock_data.py
│   │   ├── models/            # SQLAlchemy 模型
│   │   ├── schemas/           # Pydantic Schemas（含 user.py）
│   │   ├── services/          # 核心业务服务
│   │   │   ├── llm_service.py         # LLM 服务（DeepSeek，重试/熔断/并发控制）
│   │   │   ├── embedding_service.py   # Embedding 服务（千问）
│   │   │   ├── intent_service.py      # 意图识别（预识别短路 + 同义词归一化）
│   │   │   ├── sentiment_service.py   # 情感分析（词典+规则：B4负向修正）
│   │   │   ├── rag_service.py         # RAG 检索增强生成（双路检索：向量+关键词）
│   │   │   ├── chat_service.py        # 对话服务（会话治理 + 流式 + 满意度评价）
│   │   │   ├── user_service.py        # 用户服务（内存表 + 演示账号）
│   │   │   └── observe_service.py     # Langfuse 可观测性服务
│   │   ├── agents/            # Agent 系统
│   │   │   ├── base_agent.py          # Agent 基类
│   │   │   ├── customer_agent.py      # 客服 Agent（ReAct，敏感工具需登录）
│   │   │   ├── tools/                 # 6 个工具（订单/商品/退款/工单/转人工/RAG）
│   │   │   └── prompts/               # 提示词模板
│   │   ├── rag/               # RAG 模块
│   │   │   ├── chroma_client.py       # ChromaDB 客户端单例
│   │   │   ├── document_loader.py     # 文档加载
│   │   │   ├── text_splitter.py       # 文本分块
│   │   │   └── vector_store.py        # 向量存储（检索/写入）
│   │   └── utils/             # 工具（缓存/限流/HTTP/日志）
│   ├── tests/                  # 测试（API/聊天服务/RAG）
│   ├── scripts/               # 初始化脚本
│   ├── requirements.txt
│   └── .env.example           # 环境变量模板（复制为 .env 使用）
├── frontend/                   # Vue3 前端
│   ├── src/
│   │   ├── views/             # ChatPage / Dashboard / KnowledgeBase / LoginPage / RegisterPage
│   │   ├── layouts/           # MainLayout（侧边栏+内容区，含用户区）
│   │   ├── stores/            # Pinia 状态管理（auth / chat / theme）
│   │   ├── api/               # API 封装（auth.ts / chat.ts，自动附加 Bearer）
│   │   ├── types/             # TypeScript 类型定义
│   │   └── router/            # Vue Router（登录守卫）
│   ├── package.json
│   └── vite.config.ts
├── knowledge_base/             # 知识库文件
├── README.md
└── RUN_GUIDE.md                # 运行指南
```

## 🚀 快速开始

详见 **[RUN_GUIDE.md](RUN_GUIDE.md)**

## 🔐 鉴权说明

系统内置 **全站 JWT 鉴权**（`REQUIRE_AUTH` 默认开启）。除登录/注册/健康检查等公开路由外，所有接口均需 `Authorization: Bearer <JWT>`：

- `POST /api/v1/auth/register` — 注册（成功即签发 JWT）
- `POST /api/v1/auth/login` — 登录
- `GET /api/v1/auth/me` — 当前用户信息

预置 **演示账号**（仅本地演示，生产请替换为数据库用户表）：

| 用户名 | 密码 | 角色 |
|--------|------|------|
| `alice` | `Alice@123` | customer |
| `bob` | `Bob@123` | customer |
| `admin` | `Admin@123` | admin |

> 会话、订单等数据按用户隔离；未登录时敏感工具（查订单/建工单）会被拦截并提示登录。
> 演示模式可设 `REQUIRE_AUTH=false` 免鉴权，但生产环境务必保持 `true` 并配置强随机 `SECRET_KEY`。

## 🔭 可观测性 (Langfuse)

项目集成了 Langfuse 全链路追踪，每次对话请求自动记录完整调用链：

```
chat-send-message (根 span)
├── intent-recognition        # 意图识别 span
│   └── intent-classify       # LLM 意图分类 generation
├── sentiment-analysis        # 情感分析 span
├── handle-with-tools         # 工具处理 span
│   ├── rag-search            # RAG 检索 retriever
│   │   └── text-embedding    # 向量化 embedding
│   ├── rag-generate          # RAG 生成 generation
│   └── agent-tool-*          # Agent 工具执行 tool
├── handle-with-llm           # LLM 直接回复
│   └── llm-chat              # 多轮对话 generation
└── handle-transfer           # 转人工 span
```

### 架构亮点

| 模块 | 特性 | 说明 |
|------|------|------|
| 全站鉴权 | JWT + 中间件 | `REQUIRE_AUTH` 默认开启；占位 SECRET_KEY 运行时自动随机化；敏感工具需登录 |
| 全局中间件 | 差异化限流 | 昂贵接口（/send、/send_stream、/agent/process）30 次/分钟，超限 429 |
| 会话治理 | TTL + LRU + 用户隔离 | 24h 空闲自动失效，200 会话容量上限，会话按用户隔离 |
| 流式对话 | SSE | `/send_stream` 逐 token 推送，前端边生成边渲染 |
| RAG 双路检索 | 向量 + 关键词 | ChromaDB 单例 + collection 非空缓存，统一走 `rag_service.search` |
| 数据收敛 | 单一数据源 | 订单/商品统一从 `data/mock_data.py` 读取，杜绝双源漂移 |
| 上游弹性 | 重试 + 熔断 + 并发 | LLM/Embedding 上游限流熔断，差异化退避重试 |
| Agent 工具接线 | ReAct 框架 | 6 个工具全量接入，转人工/Ticket/RAG 均走工具分发 |
| 缓存 | Redis + 内存回退 | 优先 Redis，不可用时回退有界 TTL 内存缓存，防内存泄漏 |
| 前端体验 | 窗口化 + 满意度 | 消息窗口化渲染、1-5 星满意度评价、连接异常重连 |
| 安全 | .env 密钥隔离 | API Key 仅在 `backend/.env`（已 .gitignore），仓库只含占位符模板 |

### 配置

在 `backend/.env` 中设置（参考 `backend/.env.example`，所有第三方 API Key 仅存于此文件）：

```bash
# 鉴权（生产必改）
SECRET_KEY=change-me-to-a-random-secret
REQUIRE_AUTH=true

# LLM
LLM_API_KEY=your-deepseek-api-key
LLM_MODEL=deepseek-v4-flash

# Embedding
EMBEDDING_API_KEY=your-dashscope-api-key

# Langfuse 可观测性（可选）
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_TRACING_ENABLED=true
```

> `.env` 已被 `.gitignore` 排除，绝不会提交到版本库；未配置 API Key 时追踪自动降级为 no-op，不影响业务运行。

### 查看追踪

登录 [Langfuse Cloud](https://cloud.langfuse.com) 或自托管实例，在 Traces 页面可查看每次对话的完整调用链路、LLM 耗时、RAG 检索命中率等指标。
