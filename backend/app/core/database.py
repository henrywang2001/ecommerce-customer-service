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
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            pool_size=20,
            max_overflow=10,
            pool_recycle=3600,
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


# 兼容旧代码的懒加载属性
@property
def engine():
    return _get_engine()


@property
def async_session_factory():
    return _get_session_factory()


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
