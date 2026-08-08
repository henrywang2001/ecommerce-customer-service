# 电商智能客服系统 (E-Commerce Intelligent Customer Service Agent)

Vue3 + FastAPI + LLM + RAG + Agent 的电商智能客服系统。融合了大语言模型（LLM）、Agent 架构、检索增强生成（RAG）、自然语言理解（NLU）意图识别以及情感分析等多项 AI 技术。

## 🎯 核心价值

| 价值点 | 说明 |
|--------|------|
| 7×24 小时在线 | 全天候自动接待，降低人工客服 80% 工作量 |
| 精准意图识别 | 基于 LLM 的意图分类，准确率 95%+ |
| 情感智能响应 | 实时感知用户情绪，触发差异化服务策略 |
| RAG 知识增强 | 连接企业知识库，提供专业、准确的业务回答 |
| Agent 自主决策 | 基于 ReAct 框架的复杂多步骤任务自动执行 |
| 人工无缝协作 | 复杂问题智能转接，客服坐席高效承接 |

## 🏗️ 技术架构

- **前端**：Vue 3 + Element Plus + Pinia + TypeScript + Vite
- **后端**：FastAPI + SQLAlchemy + Pydantic
- **AI 服务**：DeepSeek（LLM）+ 千问 text-embedding-v1（向量）
- **数据库**：MySQL + Redis + ChromaDB（向量数据库）
- **Agent 架构**：ReAct（Reasoning + Acting）
- **可观测性**：Langfuse（全链路追踪/LLM调用监控/RAG检索分析）

## 📁 项目结构

```
ecommerce-customer-service/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/            # API 路由
│   │   │   ├── chat.py        # 对话接口
│   │   │   ├── intent.py      # 意图识别接口
│   │   │   ├── agent.py       # Agent 接口
│   │   │   ├── knowledge.py   # 知识库接口
│   │   │   ├── order.py       # 订单服务接口
│   │   │   ├── product.py     # 商品服务接口
│   │   │   └── analytics.py   # 数据分析接口
│   │   ├── core/              # 核心配置
│   │   │   ├── config.py      # 应用配置（LLM/Embedding/DB）
│   │   │   ├── database.py    # 数据库连接
│   │   │   └── security.py    # JWT 安全认证
│   │   ├── models/            # SQLAlchemy 模型
│   │   ├── schemas/           # Pydantic Schemas
│   │   ├── services/          # 核心业务服务
│   │   │   ├── llm_service.py         # LLM 服务（DeepSeek）
│   │   │   ├── embedding_service.py   # Embedding 服务（千问）
│   │   │   ├── intent_service.py      # 意图识别（多策略融合）
│   │   │   ├── sentiment_service.py   # 情感分析（词典+规则：B4负向修正）
│   │   │   ├── rag_service.py         # RAG 检索增强生成（双路检索：向量+关键词）
│   │   │   ├── chat_service.py        # 对话服务（会话生命周期：TTL淘汰+LRU上限）
│   │   │   └── observe_service.py     # Langfuse 可观测性服务
│   │   ├── agents/            # Agent 系统
│   │   │   ├── base_agent.py          # Agent 基类
│   │   │   ├── customer_agent.py      # 客服 Agent（ReAct）
│   │   │   ├── tools/                 # 工具集（6个，已接线工具分发）
│   │   │   └── prompts/               # 提示词模板
│   │   ├── nlu/               # NLU 模块
│   │   ├── rag/               # RAG 模块（文档加载/分块/存储/检索）
│   │   └── utils/             # 工具（日志/缓存/限流）
│   ├── tests/                  # 测试
│   │   ├── conftest.py         # 测试夹具
│   │   ├── test_api.py         # API 测试
│   │   ├── test_chat_service.py # 对话服务测试
│   │   └── test_rag.py        # RAG 测试
│   ├── scripts/               # 初始化脚本
│   ├── requirements.txt
│   └── .env                   # 环境变量（已配置 API Key）
├── frontend/                   # Vue3 前端
│   ├── src/
│   │   ├── views/             # ChatPage / Dashboard / KnowledgeBase
│   │   ├── layouts/           # MainLayout（侧边栏+内容区）
│   │   ├── stores/            # Pinia 状态管理（含本地缓存 B1）
│   │   ├── api/               # API 封装
│   │   ├── types/             # TypeScript 类型定义
│   │   └── router/            # Vue Router
│   ├── package.json
│   └── vite.config.ts
├── knowledge_base/             # 知识库文件
├── README.md
└── RUN_GUIDE.md                # 运行指南
```

## 🚀 快速开始

详见 **[RUN_GUIDE.md](RUN_GUIDE.md)**


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
| 全局中间件 | 限流 + 鉴权 | IP 频率限制防滥用，JWT 鉴权可按需开启 |
| 会话生命周期 | TTL 淘汰 + LRU 上限 | 24h 空闲自动失效，200 会话容量上限 |
| RAG 双路检索 | 向量检索 + 关键词匹配 | ChromaDB 与内置知识库互补，零向量自动降级 |
| Agent 工具接线 | ReAct 框架 | 6 个工具全量接入，转人工/Ticket/RAG 均走工具分发 |
| 前端侧边栏 | 会话列表 + 缓存 | 本地持久化最近 10 个会话，恢复免后端调用 |
| 安全 | .env 密钥隔离 + .gitignore | API Key 不含在版本控制中 |

### 配置

在 `backend/.env` 中设置（所有第三方服务的 API Key）：

```bash
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

> 未配置 API Key 时追踪自动降级为 no-op，不影响业务运行。
> 参考 `backend/.env.example` 了解所有可配置项。

### 查看追踪

登录 [Langfuse Cloud](https://cloud.langfuse.com) 或自托管实例，在 Traces 页面可查看每次对话的完整调用链路、LLM 耗时、RAG 检索命中率等指标。
