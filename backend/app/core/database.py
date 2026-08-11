"""数据库连接模块"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# 懒加载 — 避免 MySQL 不可用时模块级崩溃
_engine = None
_async_session_factory = None


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass


def _get_engine():
    global _engine
    if _engine is None:
        # MN-7b：pool_pre_ping 在每次从池检出连接前做一次轻量探测，
        # 避免拿到已被服务端关闭的「死连接」导致随机报错；
        # connect_args 设置连接超时，避免 MySQL 不可达时无限挂起
        # （落库失败时由调用方回退内存模式，绝不阻断请求）。
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            pool_size=20,
            max_overflow=10,
            pool_recycle=3600,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5},
        )
    return _engine


def _get_session_factory():
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：获取数据库会话"""
    async with _get_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
