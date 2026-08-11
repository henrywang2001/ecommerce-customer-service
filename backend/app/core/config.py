"""应用配置模块 - 使用 Pydantic Settings 管理环境变量"""
from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator
from typing import List
import os

# 确保 .env 路径相对于 backend 目录而非调用者 cwd
_backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_project_root = os.path.dirname(_backend_dir)
_env_file = os.path.join(_backend_dir, ".env")

# 视为「占位/未配置」的 SECRET_KEY 集合——命中则运行时随机生成，杜绝硬编码密钥漏洞 (B2)
_PLACEHOLDER_SECRETS = {
    "ecommerce-cs-secret-key-change-in-production",
    "your-secret-key-change-in-production",
    "change-me-to-a-random-secret",
}


class Settings(BaseSettings):
    # 项目基本信息
    PROJECT_NAME: str = "电商智能客服系统"
    VERSION: str = "1.0.0"
    # B9: 默认关闭 DEBUG，生产环境避免明文堆栈/文档泄露
    DEBUG: bool = False

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000", "http://localhost:80"]

    # 数据库配置
    DATABASE_URL: str = "mysql+aiomysql://root:123456@localhost:3306/ecommerce_cs?charset=utf8mb4"

    # Redis 配置
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT 配置
    # B2: 默认开启全站鉴权；占位密钥会在运行时被随机密钥覆盖
    SECRET_KEY: str = "ecommerce-cs-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 小时
    REQUIRE_AUTH: bool = True  # 生产环境鉴权开关：True 时全站需 Bearer JWT，False 时 demo 无鉴权

    # LLM 配置 — DeepSeek（API Key 通过 .env 设置，此处仅作占位）
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-v4-flash"
    LLM_API_BASE: str = "https://api.deepseek.com/v1"
    LLM_MAX_TOKENS: int = 2000
    LLM_TEMPERATURE: float = 0.7

    # Embedding 配置 — 千问 text-embedding-v1（API Key 通过 .env 设置）
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-v1"
    EMBEDDING_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_DIMENSION: int = 1536

    # ChromaDB 向量存储配置 (B9: 默认绝对路径，避免依赖启动 cwd)
    CHROMA_PERSIST_DIR: str = os.path.join(_backend_dir, "chroma_db")
    CHROMA_COLLECTION: str = "knowledge_base"

    # ── Provider 抽象层（EX-3）厂商选择 ──
    # 值为小写厂商标识；工厂函数 get_*_provider() 据此选择具体实现，未知值回退默认。
    LLM_PROVIDER: str = "deepseek"
    EMBEDDING_PROVIDER: str = "dashscope"
    VECTORSTORE_PROVIDER: str = "chroma"

    # RAG 配置
    RAG_TOP_K: int = 5

    # 意图识别配置
    INTENT_THRESHOLD: float = 0.6

    # ── CQ-6：运行期参数收口（集中可配可观测，消除魔法数字）──
    # 会话生命周期治理（M1）：容量上限 / 空闲 TTL / 历史轮数
    SESSION_MAX_COUNT: int = 200   # 单实例最大会话数（超出按最旧 LRU 淘汰）
    SESSION_TTL: int = 86400       # 会话空闲 TTL（秒），默认 24h
    HISTORY_TURNS: int = 6         # 送给 LLM 的对话历史轮数上限
    # 数据库连线池（原 database.py 20/10 与 user_service.py 10/5 不一致，统一收口）
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    # RAG 关键词召回计分权重（rag_service._keyword_search）
    INTENT_KEYWORD_WEIGHTS: dict = {
        "explicit": 0.4,   # 显式关键词子串命中 / 个
        "token": 0.8,      # 问题分词命中（按命中比例）
        "category": 0.5,   # 分类子串命中
    }

    # 上游 LLM/Embedding 弹性配置（P4）
    UPSTREAM_LLM_MAX_CONCURRENCY: int = 20
    UPSTREAM_EMBEDDING_MAX_CONCURRENCY: int = 20
    UPSTREAM_MAX_RETRIES: int = 3
    UPSTREAM_RETRY_BASE_DELAY: float = 0.5
    UPSTREAM_RETRY_MAX_DELAY: float = 8.0
    UPSTREAM_LLM_CB_FAILURES: int = 5
    UPSTREAM_LLM_CB_COOLDOWN: float = 30.0
    UPSTREAM_EMBEDDING_CB_FAILURES: int = 5
    UPSTREAM_EMBEDDING_CB_COOLDOWN: float = 30.0
    RATE_LIMIT_HEAVY_MAX_REQUESTS: int = 30  # 昂贵接口（/send、/send_stream、/agent/process）每分钟上限

    # 日志配置 (B9: 日志目录默认绝对路径)
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = os.path.join(_backend_dir, "logs")

    # 知识库路径 (B9: 默认绝对路径，避免依赖启动 cwd)
    KNOWLEDGE_BASE_DIR: str = os.path.join(_project_root, "knowledge_base")

    # Langfuse 可观测性配置
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"
    LANGFUSE_TRACING_ENABLED: bool = True
    LANGFUSE_SAMPLE_RATE: float = 1.0
    LANGFUSE_ENVIRONMENT: str = "development"
    LANGFUSE_RELEASE: str = "1.0.0"

    # ── MN-1b：阈值合理区间校验（启动即暴露异常配置，杜绝“改一处忘另一处”）──
    @field_validator("INTENT_THRESHOLD")
    @classmethod
    def _check_intent_threshold(cls, v: float) -> float:
        if not (0.0 < v <= 1.0):
            raise ValueError("INTENT_THRESHOLD 必须在 (0, 1] 区间")
        return v

    @field_validator("RAG_TOP_K")
    @classmethod
    def _check_rag_top_k(cls, v: int) -> int:
        if v < 1:
            raise ValueError("RAG_TOP_K 必须 >= 1")
        return v

    @field_validator("LLM_TEMPERATURE")
    @classmethod
    def _check_llm_temperature(cls, v: float) -> float:
        if not (0.0 <= v <= 2.0):
            raise ValueError("LLM_TEMPERATURE 必须在 [0, 2] 区间")
        return v

    @field_validator("ACCESS_TOKEN_EXPIRE_MINUTES")
    @classmethod
    def _check_token_expire(cls, v: int) -> int:
        if v < 1:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES 必须 >= 1")
        return v

    @field_validator("EMBEDDING_DIMENSION")
    @classmethod
    def _check_embed_dim(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("EMBEDDING_DIMENSION 必须 > 0")
        return v

    @field_validator(
        "UPSTREAM_LLM_MAX_CONCURRENCY",
        "UPSTREAM_EMBEDDING_MAX_CONCURRENCY",
        "UPSTREAM_MAX_RETRIES",
        "RATE_LIMIT_HEAVY_MAX_REQUESTS",
    )
    @classmethod
    def _check_positive_int(cls, v: int) -> int:
        if v < 1:
            raise ValueError("并发/重试/限流参数必须 >= 1")
        return v

    @field_validator(
        "UPSTREAM_RETRY_BASE_DELAY",
        "UPSTREAM_RETRY_MAX_DELAY",
        "UPSTREAM_LLM_CB_COOLDOWN",
        "UPSTREAM_EMBEDDING_CB_COOLDOWN",
    )
    @classmethod
    def _check_nonneg_float(cls, v: float) -> float:
        if v < 0:
            raise ValueError("退避/冷却参数必须 >= 0")
        return v

    @field_validator("LANGFUSE_SAMPLE_RATE")
    @classmethod
    def _check_sample_rate(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("LANGFUSE_SAMPLE_RATE 必须在 [0, 1] 区间")
        return v

    @field_validator("PORT")
    @classmethod
    def _check_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError("PORT 必须在 [1, 65535]")
        return v

    # ── CQ-6：会话/连接池/关键词权重 区间校验 ──
    @field_validator("SESSION_MAX_COUNT", "SESSION_TTL", "HISTORY_TURNS", "DB_POOL_SIZE")
    @classmethod
    def _check_positive_int_cq6(cls, v: int) -> int:
        if v < 1:
            raise ValueError("会话/连接池容量参数必须 >= 1")
        return v

    @field_validator("DB_MAX_OVERFLOW")
    @classmethod
    def _check_overflow(cls, v: int) -> int:
        if v < 0:
            raise ValueError("DB_MAX_OVERFLOW 必须 >= 0")
        return v

    @field_validator("INTENT_KEYWORD_WEIGHTS")
    @classmethod
    def _check_kw_weights(cls, v: dict) -> dict:
        for k in ("explicit", "token", "category"):
            if k not in v:
                raise ValueError(f"INTENT_KEYWORD_WEIGHTS 缺少键 {k}")
            if not isinstance(v[k], (int, float)) or v[k] < 0:
                raise ValueError(f"INTENT_KEYWORD_WEIGHTS[{k}] 必须 >= 0")
        return v

    # ── MN-7a：生产环境（DEBUG=False）必须配置密钥，缺失即启动失败 ──
    # 开发环境（DEBUG=True）保留 B2 的占位密钥自动随机化便利，不强制。
    @model_validator(mode="after")
    def _enforce_prod_secrets(self):
        if self.DEBUG:
            return self
        if not self.LLM_API_KEY:
            raise ValueError("生产环境(DEBUG=False)必须配置 LLM_API_KEY")
        if not self.EMBEDDING_API_KEY:
            raise ValueError("生产环境(DEBUG=False)必须配置 EMBEDDING_API_KEY")
        if (
            self.SECRET_KEY in _PLACEHOLDER_SECRETS
            or "change-in-production" in self.SECRET_KEY
            or "change-me" in self.SECRET_KEY
        ):
            raise ValueError(
                "生产环境(DEBUG=False) SECRET_KEY 不能使用占位值，请在 .env 配置固定随机密钥"
            )
        return self

    class Config:
        env_file = _env_file
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

# ── B9: 相对路径归一化 ──
# 即使 .env 仍使用相对路径，也在加载阶段解析为基于 backend 目录的绝对路径，
# 避免依赖进程启动时的 cwd（uvicorn 从不同目录启动时路径错乱）。
def _to_abs(path: str, base: str) -> str:
    return path if os.path.isabs(path) else os.path.normpath(os.path.join(base, path))


settings.CHROMA_PERSIST_DIR = _to_abs(settings.CHROMA_PERSIST_DIR, _backend_dir)
settings.KNOWLEDGE_BASE_DIR = _to_abs(settings.KNOWLEDGE_BASE_DIR, _project_root)
settings.LOG_DIR = _to_abs(settings.LOG_DIR, _backend_dir)

# ── B2: SECRET_KEY 安全加固 ──
# 若配置值为常见占位符（含 .env 里的弱密钥），运行时随机生成一次性密钥并告警，
# 杜绝「硬编码密钥」被攻击者用于伪造 JWT。生产环境应在 .env 设置真实随机密钥。
import secrets as _secrets

if settings.SECRET_KEY in _PLACEHOLDER_SECRETS or "change-in-production" in settings.SECRET_KEY or "change-me" in settings.SECRET_KEY:
    settings.SECRET_KEY = _secrets.token_urlsafe(32)
    import logging as _logging

    _logging.getLogger(__name__).warning(
        "SECRET_KEY 使用了占位值，已自动生成本次运行的随机密钥；"
        "生产环境请在 .env 中配置固定且随机的 SECRET_KEY，否则重启后旧令牌将失效。"
    )
