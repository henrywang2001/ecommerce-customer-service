"""FastAPI 主入口"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1 import chat, intent, agent, knowledge, order, product, analytics, auth
from starlette.requests import Request
from fastapi.responses import JSONResponse

from app.utils.rate_limiter import rate_limiter, heavy_rate_limiter
from app.utils.http_client import get_http_client, close_http_client
from app.core.security import decode_access_token

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"{'='*50}")
    logger.info(f"  {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"  LLM: {settings.LLM_MODEL} @ {settings.LLM_API_BASE}")
    logger.info(f"  Embedding: {settings.EMBEDDING_MODEL}")
    logger.info(f"{'='*50}")
    logger.info("应用启动中...")

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

    # 启动时创建数据库表（可选，如果 MySQL 可用）
    try:
        from app.core.database import _get_engine, Base
        eng = _get_engine()
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表已就绪")
    except Exception as e:
        logger.warning(f"数据库连接失败（将使用内存模式）: {e}")

    logger.info("应用启动完成")

    # 预热共享 HTTP 连接池（P1）
    try:
        get_http_client()
        logger.info("共享 HTTP 连接池已就绪")
    except Exception as e:
        logger.warning(f"HTTP 连接池预热失败: {e}")

    yield

    logger.info("应用关闭中...")

    # 关闭共享 HTTP 连接池（P1）
    try:
        await close_http_client()
        logger.info("HTTP 连接池已关闭")
    except Exception as e:
        logger.warning(f"关闭 HTTP 连接池失败: {e}")
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


# ── 全局限流中间件（防滥用）──
@app.middleware("http")
async def ratelimit_middleware(request: Request, call_next):
    """复用既有限流器，对匿名/高频请求返回 429。

    不修改 rate_limiter 本身，仅在此处接线使其对全部请求生效。
    """
    client_ip = request.client.host if request.client else "anonymous"
    # P4：昂贵接口（触发 LLM/Embedding 的重度路径）使用更严格的限流器
    heavy_paths = {"/api/v1/chat/send", "/api/v1/chat/send_stream", "/api/v1/agent/process"}
    limiter = heavy_rate_limiter if request.url.path in heavy_paths else rate_limiter
    if not await limiter.is_allowed(client_ip):
        return JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后再试。"})
    return await call_next(request)


# ── 全局鉴权中间件（B2：生产环境默认开启）──
# 永远公开：健康检查、根路径、认证路由（登录/注册本身不能要求鉴权）
PUBLIC_PATHS = {"/", "/health"}
AUTH_ROUTES = {"/api/v1/auth/login", "/api/v1/auth/register"}
# 文档仅在 DEBUG（开发）模式下公开；生产(DEBUG=False)下同样需鉴权，避免信息泄露
DOCS_PATHS = {"/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """鉴权网关：
    - REQUIRE_AUTH=False：放行，但仍在 request.state.user 写入可解析的令牌（供业务层使用）。
    - REQUIRE_AUTH=True：无有效 Bearer JWT 即 401（公开路径除外）。
    - /docs 等文档路径仅在 DEBUG 下公开，生产环境强制鉴权。
    """
    path = request.url.path

    # 提前解析令牌（供 docs/鉴权分支与业务层统一使用）
    request.state.user = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        payload = decode_access_token(auth[len("Bearer "):])
        if payload:
            request.state.user = payload

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


@app.get("/")
async def root():
    return {
        "message": f"欢迎使用{settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.VERSION}
