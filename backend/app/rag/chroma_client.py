"""ChromaDB 客户端单例（P7 修复）

rag_service 与 vector_store 共用同一个 PersistentClient 实例，避免两个客户端
指向同一持久化目录导致的 SQLite 锁竞争（重复创建会引发 database is locked 等错误）。
"""
import logging
from typing import Optional

import chromadb
from app.core.config import settings

logger = logging.getLogger(__name__)
_client: Optional["chromadb.Client"] = None

# P10 修复：缓存「当前 collection 是否非空」标志，避免每次检索都执行一次全量
# collection.count() 扫描（随文档数增大变重的额外开销）。add/delete 文档后失效，
# 下次检索惰性重算一次。None 表示尚未计算。
_collection_has_docs: Optional[bool] = None


def invalidate_collection_cache() -> None:
    """在 collection 文档增减后调用，使「是否非空」缓存失效。"""
    global _collection_has_docs
    _collection_has_docs = None


async def collection_has_docs(collection) -> bool:
    """返回 collection 是否包含文档（带缓存）；collection 为 None 时返回 False。"""
    global _collection_has_docs
    if _collection_has_docs is None:
        try:
            _collection_has_docs = bool(collection is not None and collection.count() > 0)
        except Exception:
            _collection_has_docs = False
    return _collection_has_docs


def get_chroma_client() -> Optional["chromadb.Client"]:
    """返回进程内唯一的 ChromaDB 客户端单例；不可用时返回 None。"""
    global _client
    if _client is None:
        try:
            _client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
            logger.info(f"ChromaDB 客户端单例已创建: {settings.CHROMA_PERSIST_DIR}")
        except ImportError:
            logger.warning("chromadb 未安装，RAG 向量检索不可用")
            return None
        except Exception as e:
            logger.warning(f"ChromaDB 连接失败: {e}")
            return None
    return _client
