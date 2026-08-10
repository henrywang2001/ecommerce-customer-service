"""共享 HTTP 连接池客户端（P1）：模块级单例，复用 TCP/TLS 连接。

每次调用都新建 httpx.AsyncClient 会重复做 TLS 握手、消耗文件描述符，高并发下
延迟显著上升。提升为单例 + 连接池后，连接复用率接近 100%，并发吞吐可提升数倍。
"""
from typing import Optional
import httpx
from app.core.config import settings

_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    """获取（惰性创建）带连接池的共享 HTTP 客户端。"""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
    return _client


async def close_http_client() -> None:
    """应用关闭时释放连接池（在 main.py lifespan 的 shutdown 阶段调用）。"""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
