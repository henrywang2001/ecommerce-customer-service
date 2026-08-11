# 电商智能客服系统 — 运行指南

## 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.10+ |
| Node.js | 18+ |
| pip | 最新版 |
| npm | 最新版 |

> 注意：MySQL、Redis、ChromaDB 均为可选依赖，不配置时系统自动降级运行（内存模式 / 有界内存缓存 / 关键词检索）。

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
> 向量数据持久化目录默认为 `backend/chroma_db`（已配置为绝对路径，不依赖启动目录）。

### 5. 环境变量说明

将 `backend/.env.example` 复制为 `backend/.env` 并按需修改。**`.env` 已被 `.gitignore` 排除，绝不会提交到版本库。**

```bash
# 鉴权（生产环境必改）
SECRET_KEY=change-me-to-a-random-secret
REQUIRE_AUTH=true          # true=全站需 Bearer JWT；false=demo 免鉴权

# LLM: DeepSeek
LLM_API_KEY=your-deepseek-api-key
LLM_MODEL=deepseek-v4-flash

# Embedding: 千问
EMBEDDING_API_KEY=your-dashscope-api-key

# Provider 抽象层（切换厂商仅改此处）
LLM_PROVIDER=deepseek
EMBEDDING_PROVIDER=dashscope
VECTORSTORE_PROVIDER=chroma

# 会话治理
SESSION_MAX_COUNT=200
SESSION_TTL=86400

# Langfuse 可观测性（可选）
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

> **SECRET_KEY**：若使用占位值，系统会在每次启动时自动生成随机密钥（旧令牌失效）。生产环境务必配置固定且随机的 `SECRET_KEY`，否则重启后所有已登录用户需重新登录。
> 完整配置项见 `backend/.env.example`（含 Provider 抽象层、会话治理、上游弹性、限流等）。

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
- 健康检查：http://localhost:8000/healthz（存活探针）、http://localhost:8000/readyz（就绪探针）
- 指标：http://localhost:8000/metrics（Prometheus）、http://localhost:8000/stats（JSON）
- 首页：http://localhost:8000/

> `/`、`/healthz`、`/readyz`、`/metrics`、`/stats` 为永远公开路由；`/docs` 仅在 `DEBUG=true` 时公开。其余接口在 `REQUIRE_AUTH=true` 下均需 Bearer JWT。

---

## 二、鉴权与演示账号

系统内置 JWT 鉴权，`REQUIRE_AUTH` 默认开启。前端自动完成登录态管理；直接调 API 时需先登录获取 token。

### 演示账号（内存用户表预置，仅本地演示）

| 用户名 | 密码 | 角色 |
|--------|------|------|
| `alice` | `Alice@123` | customer |
| `bob` | `Bob@123` | customer |
| `admin` | `Admin@123` | admin |

### 鉴权接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册（成功即签发 JWT） |
| POST | `/api/v1/auth/login` | 登录 |
| GET | `/api/v1/auth/me` | 当前用户信息 |

> 会话、订单等数据按登录用户隔离；未登录时敏感工具（查订单/建工单）会被拦截并提示"请先登录"。
> 生产环境应将 `user_service` 的内存用户表替换为数据库实现（接口保持不变即可）。

---

## 三、前端运行

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

访问 http://localhost:5173 ，**首次进入需登录/注册**（可用上方演示账号）。

> 前端通过 Vite 代理将 `/api` 请求转发到后端 `http://localhost:8000`，无需额外配置。
> 如需直连后端，可在 `frontend/.env.local` 设置 `VITE_API_BASE_URL=http://localhost:8000`。

---
## 四、Docker 一键部署

项目提供了完整的容器化编排，包含 nginx 边缘网关、backend、frontend 和 Redis：

```bash
# 克隆项目后，在根目录执行
docker compose up -d

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f
```

服务启动后访问 **http://localhost:8080**（nginx 统一入口）。

> `docker-compose.yml` 中 `LLM_API_KEY`、`EMBEDDING_API_KEY`、`SECRET_KEY` 等通过环境变量传入，
> 启动前先确保已设置（或创建 `.env` 文件，docker compose 会自动读取）。

| 服务 | 内部端口 | 说明 |
|------|----------|------|
| nginx | 8080→80 | 边缘网关，`/api/*` → backend，其余 → frontend |
| backend | 8000 | FastAPI，健康检查指向 `/readyz` |
| frontend | 80 | nginx 静态托管 Vue3 构建产物 |
| redis | 6379 | 会话缓存 & 限流计数器 |

---

## 五、测试对话

### 1. 通过前端测试

打开浏览器访问 http://localhost:5173 ，登录后进入聊天页，输入例如：

- "你好"
- "我想查一下我的订单"
- "退换货政策是什么"
- "有什么优惠活动"
- "转人工客服"

> 聊天默认走 **SSE 流式输出**，逐 token 渲染；机器人回复后可在消息下方进行 **1-5 星满意度评价**。

### 2. 通过 API 测试

先登录获取 token：

```bash
# 登录（演示账号）
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "Alice@123"}'
# 返回 access_token，后续请求放入 Authorization: Bearer <token>

TOKEN="<上一步返回的 access_token>"
AUTH="Authorization: Bearer $TOKEN"
```

然后带 token 调用业务接口：

```bash
# 创建会话
curl -X POST http://localhost:8000/api/v1/chat/session \
  -H "Content-Type: application/json" -H "$AUTH" \
  -d '{"channel": "web"}'

# 发送消息（替换 YOUR_SESSION_ID）
curl -X POST http://localhost:8000/api/v1/chat/send \
  -H "Content-Type: application/json" -H "$AUTH" \
  -d '{"session_id": "YOUR_SESSION_ID", "content": "退换货政策是什么"}'

# 流式发送（SSE，逐 token 返回）
curl -N -X POST http://localhost:8000/api/v1/chat/send_stream \
  -H "Content-Type: application/json" -H "$AUTH" \
  -d '{"session_id": "YOUR_SESSION_ID", "content": "我想查一下订单 ORDER20260315001 的物流"}'

# 意图识别测试
curl -X POST http://localhost:8000/api/v1/intent/recognize \
  -H "Content-Type: application/json" -H "$AUTH" \
  -d '{"text": "我想查一下订单 ORDER20260315001 的物流"}'
```

> 昂贵接口（`/chat/send`、`/chat/send_stream`、`/agent/process`）有限流：30 次/分钟，超限返回 429。

### 3. 通过 Swagger 文档测试

打开 http://localhost:8000/docs，先调 `/api/v1/auth/login` 获取 token，点击右上角 **Authorize** 填入 `Bearer <token>`，即可交互式测试各接口。

---

## 六、常见问题

### Q: 数据库连接失败？
A: 系统无需数据库即可运行。对话历史、会话信息和用户表存储在内存中（重启后丢失）。如需持久化，请配置 MySQL。

### Q: LLM 调用失败？
A: 检查 `.env` 中的 `LLM_API_KEY` 是否正确，以及网络是否能访问 DeepSeek API（`https://api.deepseek.com`）。上游已内置重试 + 熔断，持续失败多为网络问题。

### Q: Embedding 调用失败？
A: 检查 `.env` 中的 `EMBEDDING_API_KEY` 是否正确，以及网络是否能访问阿里云 DashScope API（`https://dashscope.aliyuncs.com`）。Embedding 不可用时系统自动降级为纯关键词检索。

### Q: ChromaDB 安装失败？
A: ChromaDB 在 Windows 上可能需要 Visual C++ 运行时。不安装也不影响使用，系统会自动回退到关键词匹配。

### Q: 前端端口冲突？
A: 编辑 `frontend/vite.config.ts`，修改 `server.port` 的值。

### Q: 接口返回 401 / 登录页一直跳转？
A: 后端默认 `REQUIRE_AUTH=true`，未带 token 或 token 过期会 401。先登录拿 token；若配置了占位 `SECRET_KEY`，后端重启后旧 token 全部失效，需重新登录。

### Q: 如何关闭鉴权做纯演示？
A: 在 `backend/.env` 设置 `REQUIRE_AUTH=false` 后重启后端。此时所有接口免鉴权放行，前端仍会尝试登录（演示账号可直接登录）。

### Q: Docker 部署后无法访问 LLM？
A: 确保启动时传入了 `LLM_API_KEY` 环境变量（或项目根目录有 `.env` 文件），容器内网络需能访问外部 API。

---

## 七、架构特性说明

### 会话生命周期管理

- **Redis 优先**：会话状态优先存储在 Redis；Redis 不可用时自动回退内存模式（单进程开发可用）
- **容量上限**：最多保持 200 个活跃会话（`SESSION_MAX_COUNT`），超出时按 LRU 淘汰
- **空闲 TTL**：`SESSION_TTL` 秒无活动自动清理（默认 24h，当前会话豁免）
- **用户隔离**：会话按登录用户隔离，`GET /api/v1/chat/sessions` 只返回当前用户的会话
- **本地缓存**：前端按会话缓存消息，支持历史合并去重与恢复

### 安全机制

- **全站 JWT 鉴权**：`REQUIRE_AUTH=true`（默认）时所有接口需 Bearer JWT，中间件统一校验
- **占位密钥加固**：`SECRET_KEY` 若为占位值，运行时自动生成随机密钥并告警，杜绝硬编码密钥
- **生产密钥强制**：`DEBUG=false` 时，`LLM_API_KEY`、`EMBEDDING_API_KEY`、`SECRET_KEY` 缺少或为占位值会启动失败
- **全局限流**：基于 IP 的频率限制中间件 + 昂贵接口差异化限流（30 次/分钟），防止 API 滥用
- **敏感工具鉴权**：查订单/建工单等工具 `requires_auth`，未登录用户会被拦截
- **密钥隔离**：所有 API Key 通过 `backend/.env` 注入，`.env` 已加入 `.gitignore` 不会上传

### RAG 双路检索

- **架构**：`chroma_client.py` 提供 ChromaDB 客户端单例 + collection 非空缓存，`vector_store.py` 复用该单例，检索统一走 `rag_service.search()`
- **双路合并**：Chroma 向量检索与内置知识库关键词匹配并行执行，结果合并去重，按 id 去重取高分、降序截取 top_k，向量分数 min-max 归一化到 [0,1]
- **关键词预索引**：启动时将知识库文本预分词索引（jieba），避免每次检索重复分词，提升关键词召回性能
- **降级**：Embedding 不可用（返回零向量）时自动降级为纯关键词检索

### 数据收敛（单一数据源）

- 订单/商品数据统一存放在 `backend/app/data/mock_data.py`，路由层与对话工具层均从此读取，消除双源漂移
- 记录采用对话工具所需的"富字段"结构（`product_name / status_text / rating / sales / tags` 等），对外契约保持一致

### Agent 工具接线

6 个工具（search_knowledge / query_order / query_product / refund / create_ticket / transfer_human）已通过 **工具注册表** 接入 Agent 执行链：
- **声明式注册**：每个工具类通过 `@tool(name, triggers=[...], requires_auth=...)` 一行装饰器完成注册，新增工具只需 1 个类 + 1 行装饰器
- **意图 → 工具映射**：注册表自动从装饰器参数生成意图编码到工具名的映射，调度时直接路由
- 意图识别后按 `handler_type` 分发；支持 `preferred_intent` 预识别短路，跳过 LLM 调用保证链路一致

### 意图识别体系

- 11 个意图码：product_inquiry / order_query / refund_request / ticket_create / complaint / human_agent / payment_issue / shipping_info / promotion / greeting / fallback
- **同义词归一化**：37 组意图同义词映射，LLM 返回未知码时按"标准码 → 同义词 → 模糊包含 → 关键词结果"逐级归一
- 意图识别与情感分析在消息处理中**并发执行**，节省串行等待

### 流式输出

- `POST /api/v1/chat/send_stream` 返回 SSE（`text/event-stream`），事件类型：`token`（逐片段）/ `done`（携带 response/intent/sentiment/quick_replies/need_transfer）/ `error`
- 前端用 fetch + ReadableStream 手写 SSE 解析，逐 token 渲染；出错且无 token 时自动回退非流式

### 缓存机制

- **优先 Redis**：连接失败自动降级，不再重试
- **内存回退**：有界（maxsize=1000）+ TTL（默认 3600s）+ FIFO 淘汰，长期运行不会内存膨胀

### 上游弹性（重试 + 熔断 + 并发控制）

- LLM / Embedding 上游：最大并发各 20，失败重试 3 次（指数退避 0.5s→8s）
- 熔断器：5 次失败进入冷却 30s，快速失败保护下游

### LLM 模型配置

当前使用：
- **模型**：DeepSeek V4 Flash
- **API Base**：`https://api.deepseek.com/v1`
- **API Key**：在 `backend/.env` 中配置 `LLM_API_KEY`

切换到其他 LLM（如 OpenAI）只需修改 `backend/.env` 中的 `LLM_API_KEY`、`LLM_MODEL`、`LLM_API_BASE`。

### Provider 抽象层

Provider 抽象层将 LLM / Embedding / 向量库的厂商实现与业务逻辑解耦：

- **LLMProvider ABC**：统一 `chat` / `chat_json` / `chat_stream` 接口，当前实现 `LLMService`（DeepSeek / OpenAI 兼容协议）
- **EmbeddingProvider ABC**：统一 `embed` / `embed_batch` 接口，当前实现 `EmbeddingService`（千问 DashScope）
- **VectorStoreProvider ABC**：统一 `search` / `add` 接口，当前实现 `ChromaVectorStoreProvider`
- **配置驱动**：`LLM_PROVIDER` / `EMBEDDING_PROVIDER` / `VECTORSTORE_PROVIDER` 选择厂商，新增厂商只需实现对应 ABC 并在工厂函数注册

### 健康探针与可观测性

| 端点 | 类型 | 说明 |
|------|------|------|
| `/healthz` | 存活探针 | 总是返回 200，供 K8s livenessProbe |
| `/readyz` | 就绪探针 | 检查 Redis / Chroma / LLM Key / Embedding Key，全部就绪才 200 |
| `/metrics` | Prometheus | 请求数/延迟/活跃会话/限流拒绝计数 |
| `/stats` | JSON | 人类可读的运行时统计 + 缓存命中率 |
| `/health` | 兼容 | 旧版健康检查（保留兼容） |

所有中间件请求均携带 `X-Request-ID` 响应头，配合结构化日志（`rid`/`uid` 字段）实现全链路追踪。

### 优雅关闭

应用收到 SIGTERM/SIGINT 后：关闭 HTTP 监听 → 等待进行中请求完成（最长 30s 超时）→ 释放 Redis 连接池 → 清理临时资源，保证无请求丢失。

### 向量模型配置

当前使用：
- **模型**：千问 text-embedding-v1
- **API Base**：`https://dashscope.aliyuncs.com/compatible-mode/v1`（兼容 OpenAI 格式）
- **API Key**：在 `backend/.env` 中配置 `EMBEDDING_API_KEY`

### 可观测性配置 (Langfuse)

项目集成了 Langfuse 全链路追踪，覆盖 LLM 调用、RAG 检索、Agent 工具执行等环节。

**快速配置：**

1. 注册 [Langfuse Cloud](https://cloud.langfuse.com) 或部署自托管实例
2. 在 `backend/.env` 中配置（参考 `.env.example` 了解完整配置项）
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
