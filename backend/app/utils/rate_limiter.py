"""限流器"""
import time
import asyncio
from typing import Dict
from collections import defaultdict


class RateLimiter:
    """简单的滑动窗口限流器"""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: Dict[str, list] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        """检查请求是否允许"""
        now = time.time()
        window = self._windows[key]

        # 清除过期的记录
        cutoff = now - self.window_seconds
        while window and window[0] < cutoff:
            window.pop(0)

        if len(window) >= self.max_requests:
            return False

        window.append(now)
        return True

    async def wait_if_needed(self, key: str) -> bool:
        """如果需要限流则等待"""
        if self.is_allowed(key):
            return True
        await asyncio.sleep(1)
        return self.is_allowed(key)


# 全局实例：每分钟最多 60 个请求
rate_limiter = RateLimiter(max_requests=60, window_seconds=60)
