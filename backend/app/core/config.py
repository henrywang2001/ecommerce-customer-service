"""应用配置模块 - 使用 Pydantic Settings 管理环境变量"""
from pydantic_settings import BaseSettings
from typing import List
import os

# 确保 .env 路径相对于 backend 目录而非调用者 cwd
_backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_env_file = os.path.join(_backend_dir, ".env")


class Settings(BaseSettings):
    # 项目基本信息
    PROJECT_NAME: str = "电商智能客服系统"
    VERSION: str = "1.0.0"
    DEBUG: bool = True

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000", "http://localhost:80"]

    # 数据库配置
    DATABASE_URL: str = "mysql+aiomysql://root:123456@localhost:3306/ecommerce_cs?charset=utf8mb4"
    DATABASE_URL_SYNC: str = "mysql+pymysql://root:123456@localhost:3306/ecommerce_cs?charset=utf8mb4"

    # Redis 配置
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT 配置
    SECRET_KEY: str = "ecommerce-cs-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 小时

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

    # ChromaDB 向量存储配置
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CHROMA_COLLECTION: str = "knowledge_base"

    # RAG 配置
    RAG_TOP_K: int = 5
    RAG_SIMILARITY_THRESHOLD: float = 0.7
    RAG_MAX_CONTEXT_LENGTH: int = 4000

    # Agent 配置
    AGENT_NAME: str = "小e"
    AGENT_MAX_ITERATIONS: int = 5
    AGENT_TIMEOUT_SECONDS: int = 30

    # 意图识别配置
    INTENT_THRESHOLD: float = 0.6
    INTENT_FALLBACK_CONFIDENCE: float = 0.4

    # 转人工策略
    AUTO_TRANSFER_ON_COMPLAINT: bool = True
    AUTO_TRANSFER_ON_NEGATIVE: bool = True
    AUTO_TRANSFER_THRESHOLD: float = -0.5

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./logs"

    # 知识库路径
    KNOWLEDGE_BASE_DIR: str = "../knowledge_base"

    # Langfuse 可观测性配置
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"
    LANGFUSE_TRACING_ENABLED: bool = True
    LANGFUSE_SAMPLE_RATE: float = 1.0
    LANGFUSE_ENVIRONMENT: str = "development"
    LANGFUSE_RELEASE: str = "1.0.0"

    class Config:
        env_file = _env_file
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
