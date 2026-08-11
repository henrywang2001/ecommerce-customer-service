"""FastAPI 主入口"""
import asyncio
import uuid
import contextvars
import threading
import time
from contextlib import asynccontextmanager
import logging
from logging import Filter

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.requests import Request
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)

from app.core.config import settings
from app.api.v1 import chat, intent, agent, knowledge, order, product, analytics, auth
from app.utils.rate_limiter import rate_limiter, heavy_rate_limiter
from app.utils.http_client import get_http_client, close_http_client
from app.core.security import decode_access_token
from app.utils.cache import cache
from app.rag.chroma_client import get_chroma_client
from app.services import user_service

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────────────────────────
# MN-4：请求级上下文（request_id / user_id）+ 一致性日志格式
# ───────────────────────────────────────────────────────────────────────────
request_id_var = contextvars.ContextVar("request_id", default="-")
user_id_var = contextvars.ContextVar("user_id", default="-")


class RequestContextFilter(Filter):
    """将当前请求的 request_id / user_id 注入日志记录，供格式串引用。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        return True


def configure_logging() -> None:
    """统一配置根日志：注入 RequestContextFilter，格式含 %(request_id)s %(user_id)s。

    保证全应用（含第三方库经 root 传播的日志）都带请求上下文，便于链路追踪。
    """
    root = logging.getLogger()
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s [rid=%(request_id)s uid=%(user_id)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    flt = RequestContextFilter()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    for h in root.handlers:
        h.setFormatter(fmt)
        if not any(isinstance(existing, RequestContextFilter) for existing in h.filters):
            h.addFilter(flt)
    root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), "INFO"))


configure_logging()


# ───────────────────────────────────────────────────────────────────────────
# MN-3：可观测性指标（Prometheus）
# ───────────────────────────────────────────────────────────────────────────
HTTP_REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status"]
)
HTTP_REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency in seconds", ["method", "path"]
)
ACTIVE_SESSIONS = Gauge(
    "active_sessions", "Active in-flight requests (proxy for user sessions)"
)
RATE_LIMIT_REJECTIONS = Counter(
    "rate_limit_rejections_total", "Total rate-limit rejections"
)
LLM_TOKEN_USAGE = Counter("llm_token_usage_total", "Total LLM token usage")


# /stats 的轻量 JSON 状态（与 Prometheus 指标并行维护，便于无 Prometheus 时查看）
_stats_lock = threading.Lock()
_app_stats = {
    "request_count": 0,
    "rate_limit_rejections": 0,
    "llm_token_usage": 0,
    "active_sessions": 0,
}


def record_llm_token_usage(n: int) -> None:
    """Hook：记录 LLM token 用量。

    供 llm_service 等接入以补全 /metrics 与 /stats 的 token 维度；
    当前未在 llm_service 强制接线（属其他文件职责），留作可观测扩展点。
    """
    if n and n > 0:
        LLM_TOKEN_USAGE.inc(n)
        with _stats_lock:
            _app_stats["llm_token_usage"] += n


# ───────────────────────────────────────────────────────────────────────────
# 应用生命周期
# ───────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"{'='*50}")
    logger.info(f"  {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"  LLM: {settings.LLM_MODEL} @ {settings.LLM_API_BASE}")
    logger.info(f"  Embedding: {settings.EMBEDDING_MODEL}")
    logger.info(f"{'='*50}")
    logger.info("应用启动中...")

    # ── 确保 user_service 的 DB 引擎可用（多次 lifespan 周期可安全重建）──
    try:
        user_service.ensure_db_alive()
    except Exception as e:
        logger.warning(f"user_service DB 引擎初始化失败（将回退内存兜底）: {e}")

    # ── 初始化 Langfuse 可观测性 ──
    from app.services.observe_service import observe
    if observe.enabled:
        logger.info(
            "Langfuse 可观测性已启用: %s (env=%s)",
            settings.LANGFUSE_BASE_URL,
            settings.LANGFUSE_ENVIRONMENT,
        )
    else:
        logger.warning(
            "Langfuse 未启用（未配置 API Key 或已禁用）。"
            "请在 .env 中设置 LANGFUSE_PUBLIC_KEY 和 LANGFUSE_SECRET_KEY"
        )

    # 启动时尝试建表（MySQL 可用时）；不可用也不阻断启动，user_service 会自动回退内存兜底
    try:
        from app.core.database import _get_engine, Base
        eng = _get_engine()
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表已就绪")
    except Exception as e:
        logger.warning("数据库不可用（user_service 将回退内存兜底，不阻断启动）: %s", e)

    logger.info("应用启动完成")

    # 预热共享 HTTP 连接池（P1）
    try:
        get_http_client()
        logger.info("共享 HTTP 连接池已就绪")
    except Exception as e:
        logger.warning(f"HTTP 连接池预热失败: {e}")

    # ── PF-4：预热关键资源（后台任务，失败仅告警，绝不阻断启动）──
    try:
        asyncio.create_task(_warmup())
        logger.info("预热任务已后台启动")
    except Exception as e:
        logger.warning(f"启动预热任务失败（跳过）: {e}")

    yield

    logger.info("应用关闭中...")

    # 关闭共享 HTTP 连接池（P1）
    try:
        await close_http_client()
        logger.info("HTTP 连接池已关闭")
    except Exception as e:
        logger.warning(f"关闭 HTTP 连接池失败: {e}")

    # ── MN-7b：优雅关闭 —— 显式释放 Redis 与 Chroma 客户端 ──
    try:
        r = await cache._get_redis()
        if r:  # 仅当已连接（truthy client）才关闭；None/False 表示本就未用 Redis
            try:
                await r.aclose()
            except Exception:
                pass
            cache._redis = None  # 允许下次启动重新懒加载连接
        logger.info("Redis 客户端已释放")
    except Exception as e:
        logger.warning(f"释放 Redis 客户端失败: {e}")

    try:
        from app.rag import chroma_client as _cc
        cl = _cc._client
        if cl is not None:
            try:
                if hasattr(cl, "close"):
                    cl.close()
            except Exception:
                pass
            _cc._client = None
        logger.info("Chroma 客户端已释放")
    except Exception as e:
        logger.warning(f"释放 Chroma 客户端失败: {e}")

    # ── 关闭 user_service 的 DB 引擎与后台事件循环 ──
    try:
        from app.services import user_service
        user_service.shutdown_db()
        logger.info("user_service DB 资源已释放")
    except Exception as e:
        logger.warning(f"释放 user_service DB 资源失败: {e}")

    try:
        from app.core.database import _get_engine
        eng = _get_engine()
        await eng.dispose()
    except Exception:
        pass

    # ── 关闭时刷新 Langfuse ──
    observe.flush()
    logger.info("Langfuse 追踪数据已刷新")
    logger.info("应用已关闭")


async def _warmup() -> None:
    """PF-4：预热 Chroma 客户端 + Embedding 编码 + 一次 RAG 检索。

    任何一步失败仅告警，绝不阻断启动；作为后台任务运行。
    """
    # 1) Chroma 客户端
    try:
        from app.rag.chroma_client import get_chroma_client
        get_chroma_client()
    except Exception as e:
        logger.warning("预热 Chroma 客户端失败（跳过）: %s", e)
    # 2) Embedding 编码（无 Key 时返回零向量，快速失败）
    try:
        from app.services.embedding_service import embedding_service
        await embedding_service.encode_single("__warmup__")
    except Exception as e:
        logger.warning("预热 Embedding 失败（跳过）: %s", e)
    # 3) RAG 检索（零向量时仅走内置关键词检索，不依赖外部服务）
    try:
        from app.services.rag_service import rag_service
        await rag_service.search("__warmup__")
    except Exception as e:
        logger.warning("预热 RAG 检索失败（跳过）: %s", e)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="电商智能客服系统 — Vue3 + FastAPI + LLM + RAG + Agent",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router, prefix="/api/v1/chat", tags=["对话服务"])
app.include_router(intent.router, prefix="/api/v1/intent", tags=["意图识别"])
app.include_router(agent.router, prefix="/api/v1/agent", tags=["Agent服务"])
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["知识库"])
app.include_router(order.router, prefix="/api/v1/order", tags=["订单服务"])
app.include_router(product.router, prefix="/api/v1/product", tags=["商品服务"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["数据分析"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])


# ── 全局限流中间件（防滥用，最内层）──
# 探针/指标路径跳过限流，避免被 k8s/Prometheus 频繁探测触发 429
PROBE_PATHS = {"/", "/health", "/healthz", "/readyz", "/metrics", "/stats"}


@app.middleware("http")
async def ratelimit_middleware(request: Request, call_next):
    """复用既有限流器，对匿名/高频请求返回 429。

    不修改 rate_limiter 本身，仅在此处接线使其对全部请求生效；
    探针/指标路径放行，保证健康探测与指标抓取不被限流。
    """
    path = request.url.path
    if path in PROBE_PATHS:
        return await call_next(request)
    client_ip = request.client.host if request.client else "anonymous"
    # P4：昂贵接口（触发 LLM/Embedding 的重度路径）使用更严格的限流器
    heavy_paths = {"/api/v1/chat/send", "/api/v1/chat/send_stream", "/api/v1/agent/process"}
    limiter = heavy_rate_limiter if path in heavy_paths else rate_limiter
    if not await limiter.is_allowed(client_ip):
        RATE_LIMIT_REJECTIONS.inc()
        with _stats_lock:
            _app_stats["rate_limit_rejections"] += 1
        return JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后再试。"})
    return await call_next(request)


# ── 全局鉴权中间件（B2：生产环境默认开启）──
# 永远公开：健康检查、根路径、认证路由（登录/注册本身不能要求鉴权）以及探针/指标
PUBLIC_PATHS = {"/", "/health", "/healthz", "/readyz", "/metrics", "/stats"}
AUTH_ROUTES = {"/api/v1/auth/login", "/api/v1/auth/register"}
# 文档仅在 DEBUG（开发）模式下公开；生产(DEBUG=False)下同样需鉴权，避免信息泄露
DOCS_PATHS = {"/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """鉴权网关：
    - REQUIRE_AUTH=False：放行，但仍在 request.state.user 写入可解析的令牌（供业务层使用）。
    - REQUIRE_AUTH=True：无有效 Bearer JWT 即 401（公开路径除外）。
    - /docs 等文档路径仅在 DEBUG 下公开，生产环境强制鉴权。
    解析到合法令牌时把 user_id 写入上下文变量，供日志链路追踪。
    """
    path = request.url.path

    # 提前解析令牌（供 docs/鉴权分支与业务层统一使用）
    request.state.user = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        payload = decode_access_token(auth[len("Bearer "):])
        if payload:
            request.state.user = payload
            user_id_var.set(str(payload.get("sub")))

    if path in PUBLIC_PATHS or path in AUTH_ROUTES:
        return await call_next(request)

    if path in DOCS_PATHS:
        if settings.DEBUG:
            return await call_next(request)
        # 生产环境：文档不公开，需有效令牌
        if request.state.user:
            return await call_next(request)
        return JSONResponse(
            status_code=401,
            content={"detail": "生产环境文档已关闭，请提供 Bearer 令牌访问。"},
        )

    if settings.REQUIRE_AUTH and not request.state.user:
        return JSONResponse(status_code=401, content={"detail": "未认证或认证失效，请提供 Bearer 令牌。"})
    return await call_next(request)


# ── MN-3：请求指标中间件（记录每路由请求数 + 延迟直方图）──
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    path = request.url.path
    method = request.method
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
    finally:
        duration = time.perf_counter() - start
        HTTP_REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
        HTTP_REQUEST_LATENCY.labels(method=method, path=path).observe(duration)
        with _stats_lock:
            _app_stats["request_count"] += 1
    return response


# ── MN-4：请求 ID 中间件（最外层，最先执行；为全链路日志与追踪提供 request_id）──
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    rid_token = request_id_var.set(rid)
    uid_token = user_id_var.set("-")  # 默认 -；合法令牌由 auth_middleware 覆盖
    ACTIVE_SESSIONS.inc()
    with _stats_lock:
        _app_stats["active_sessions"] += 1
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(rid_token)
        user_id_var.reset(uid_token)
        ACTIVE_SESSIONS.dec()
        with _stats_lock:
            _app_stats["active_sessions"] -= 1
    response.headers["X-Request-ID"] = rid
    return response


@app.get("/")
async def root():
    return {
        "message": f"欢迎使用{settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "docs": "/docs",
    }


# ── MN-2：存活探针（liveness）——trivial 200，不检查任何依赖 ──
@app.get("/healthz")
async def healthz():
    return {"status": "alive", "version": settings.VERSION}


# 兼容旧探针路径
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.VERSION}


# ── MN-2：就绪探针（readiness）——检查关键依赖，失败返回 503 + 各依赖状态 ──
@app.get("/readyz")
async def readyz():
    deps: dict = {}
    # Redis 连通性
    try:
        r = await cache._get_redis()
        if r and await r.ping():
            deps["redis"] = "ok"
        else:
            deps["redis"] = "unavailable"
    except Exception as e:
        deps["redis"] = f"error: {e}"
    # Chroma 可达性
    try:
        cl = get_chroma_client()
        deps["chroma"] = "ok" if cl is not None else "unavailable"
    except Exception as e:
        deps["chroma"] = f"error: {e}"
    # LLM / Embedding API Key 是否已配置
    deps["llm_api_key"] = "configured" if settings.LLM_API_KEY else "missing"
    deps["embedding_api_key"] = "configured" if settings.EMBEDDING_API_KEY else "missing"

    all_ok = (
        deps.get("redis") == "ok"
        and deps.get("chroma") == "ok"
        and deps.get("llm_api_key") == "configured"
        and deps.get("embedding_api_key") == "configured"
    )
    payload = {"status": "ready" if all_ok else "not_ready", "dependencies": deps}
    return JSONResponse(status_code=200 if all_ok else 503, content=payload)


# ── MN-3：Prometheus 指标端点 ──
@app.get("/metrics")
def metrics():
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


# ── MN-3：轻量 JSON 状态（/metrics 的降级/补充，无需 Prometheus 即可查看）──
@app.get("/stats")
def stats():
    cache_stats = cache.stats()
    with _stats_lock:
        data = dict(_app_stats)
    data["cache"] = cache_stats
    data["version"] = settings.VERSION
    return JSONResponse(data)
