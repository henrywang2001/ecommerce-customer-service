# 电商智能客服系统 — 运行指南

## 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.10+ |
| Node.js | 18+ |
| pip | 最新版 |
| npm | 最新版 |

> 注意：MySQL 和 Redis 为可选依赖，不配置时系统使用内存模式运行。

---

## 一、后端运行

### 1. 进入后端目录

```bash
cd backend
```

### 2. 创建虚拟环境

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

> 如果 MySQL 或 Redis 不可用，可以先注释掉 `requirements.txt` 中的 `aiomysql`、`pymysql`、`redis` 和 `chromadb`，它们都是可选的。

### 4. （可选）配置 ChromaDB 向量数据库

```bash
# 安装 chromadb
pip install chromadb>=0.4.0

# 初始化向量数据库（将内置知识库向量化）
python scripts/init_vector_db.py
```

> 不安装 chromadb 也能运行，系统会自动使用内置知识库做关键词匹配。

### 5. 环境变量说明

项目已预配置 `.env` 文件，模型及 API Key 通过环境变量注入：
- **LLM**: DeepSeek `deepseek-v4-flash` → 环境变量 `LLM_API_KEY`
- **Embedding**: 千问 `text-embedding-v1` → 环境变量 `EMBEDDING_API_KEY`
- **可观测性**: Langfuse → 环境变量 `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`

如需修改，编辑 `backend/.env` 中对应的环境变量。

### 6. 启动后端服务

```bash
# 开发模式（推荐）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 或者直接
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动成功后会看到：
```
==================================================
  电商智能客服系统 v1.0.0
  LLM: deepseek-v4-flash @ https://api.deepseek.com/v1
  Embedding: text-embedding-v1
==================================================
```

### 7. 验证后端

- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health
- 首页：http://localhost:8000/

---

## 二、前端运行

### 1. 进入前端目录

```bash
cd frontend
```

### 2. 安装依赖

```bash
npm install
```

### 3. 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:5173 即可看到聊天界面。

> 前端通过 Vite 代理将 `/api` 请求转发到后端 `http://localhost:8000`，无需额外配置。

---

## 三、测试对话

### 1. 通过前端测试

打开浏览器访问 http://localhost:5173，在聊天框输入问题，例如：

- "你好"
- "我想查一下我的订单"
- "退换货政策是什么"
- "有什么优惠活动"
- "转人工客服"

### 2. 通过 API 测试

```bash
# 创建会话
curl -X POST http://localhost:8000/api/v1/chat/session \
  -H "Content-Type: application/json" \
  -d '{"channel": "web"}'

# 发送消息（替换 YOUR_SESSION_ID）
curl -X POST http://localhost:8000/api/v1/chat/send \
  -H "Content-Type: application/json" \
  -d '{"session_id": "YOUR_SESSION_ID", "content": "退换货政策是什么"}'

# 意图识别测试
curl -X POST http://localhost:8000/api/v1/intent/recognize \
  -H "Content-Type: application/json" \
  -d '{"text": "我想查一下订单 ORDER20260315001 的物流"}'
```

### 3. 通过 Swagger 文档测试

打开 http://localhost:8000/docs，直接通过交互式文档测试各接口。

---

## 四、常见问题

### Q: 数据库连接失败？
A: 系统无需数据库即可运行。对话历史和会话信息存储在内存中（重启后丢失）。如需持久化，请配置 MySQL。

### Q: LLM 调用失败？
A: 检查 `.env` 中的 `LLM_API_KEY` 是否正确，以及网络是否能访问 DeepSeek API（`https://api.deepseek.com`）。

### Q: Embedding 调用失败？
A: 检查 `.env` 中的 `EMBEDDING_API_KEY` 是否正确，以及网络是否能访问阿里云 DashScope API（`https://dashscope.aliyuncs.com`）。

### Q: ChromaDB 安装失败？
A: ChromaDB 在 Windows 上可能需要 Visual C++ 运行时。不安装也不影响使用，系统会自动回退到关键词匹配。

### Q: 前端端口冲突？
A: 编辑 `frontend/vite.config.ts`，修改 `server.port` 的值。

---

## 五、项目配置说明

### LLM 模型配置

当前使用：
- **模型**：DeepSeek V4 Flash
- **API Base**：`https://api.deepseek.com/v1`
- **API Key**：在 `backend/.env` 中配置 `LLM_API_KEY`

切换到其他 LLM（如 OpenAI）只需修改 `backend/.env` 中的 `LLM_API_KEY`、`LLM_MODEL`、`LLM_API_BASE`。

### 向量模型配置

当前使用：
- **模型**：千问 text-embedding-v1
- **API Base**：`https://dashscope.aliyuncs.com/compatible-mode/v1`（兼容 OpenAI 格式）
- **API Key**：在 `backend/.env` 中配置 `EMBEDDING_API_KEY`

### 可观测性配置 (Langfuse)

项目集成了 Langfuse 全链路追踪，覆盖 LLM 调用、RAG 检索、Agent 工具执行等环节。

**快速配置：**

1. 注册 [Langfuse Cloud](https://cloud.langfuse.com) 或部署自托管实例
2. 在 `backend/.env` 中配置：
```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_TRACING_ENABLED=true
LANGFUSE_ENVIRONMENT=development
```
3. 重启后端，追踪数据自动上报

**追踪结构：**
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

> 未配置 API Key 时，所有追踪代码自动降级为 no-op，不影响业务运行。

### 意图分类体系

| 分类 | 意图代码 | 处理方式 |
|------|----------|----------|
| 商品咨询 | product_inquiry | RAG 检索 |
| 订单查询 | order_query | 工具调用 |
| 退款退货 | refund_request | 工具调用 |
| 投诉 | complaint | 转人工 |
| 转人工 | human_agent | 转人工 |
| 支付问题 | payment_issue | RAG 检索 |
| 配送查询 | shipping_info | RAG 检索 |
| 促销活动 | promotion | RAG 检索 |
| 问候 | greeting | LLM 直接回复 |
| 兜底 | fallback | LLM 直接回复 |
