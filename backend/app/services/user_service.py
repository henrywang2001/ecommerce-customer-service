"""用户服务 — 数据库后端（MySQL/SQLite）+ 内存兜底。

AR-3 / EX-5（M3）：注册/登录读写真实数据库（User 模型 + SQLAlchemy 异步会话）。
当 DATABASE_URL 不可达时，回退到线程安全的内存用户表，保证服务不中断、请求不阻断。

为什么用「独立后台事件循环线程」驱动异步 DB I/O：
    鉴权路由是 async def，运行在 FastAPI 的事件循环内，无法在其中调用 asyncio.run
    （会报 'event loop is already running'）；而在运行中的循环里用
    run_until_complete / run_coroutine_threadsafe(...).result() 又会死锁。
    因此这里用一个常驻后台线程持有独立事件循环来驱动所有异步 DB 操作，连接池
    固定绑定到该循环，避免跨循环复用连接导致的 'Event loop is closed'。
内存字典仅作为 DATABASE_URL 不可达时的兜底（try DB first，失败 → 内存）。
公共 API（create_user / authenticate / get_by_id / list_usernames）保持同步，
以便 auth.py 无需改动即可调用。
"""
import asyncio
import threading
import time
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.schemas.user import UserCreateRequest, UserLoginRequest, UserResponse
from app.models.user import User

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────────────────────────
# 独立后台事件循环：承载 user_service 的异步 DB 操作
# ───────────────────────────────────────────────────────────────────────────
class _DBLoopRunner:
    """常驻后台线程 + 独立事件循环，用于驱动 user_service 的异步 DB I/O。

    - 引擎与会话工厂在该循环内创建，连接池绑定到该循环，杜绝跨循环复用连接。
    - run(coro) 通过 run_coroutine_threadsafe 提交到该循环并阻塞等待结果。
    """

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._started = threading.Event()
        self._thread = threading.Thread(target=self._run, name="user-db-loop", daemon=True)
        self._thread.start()
        self._engine = None
        self._session_factory = None

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._started.set()
        self._loop.run_forever()

    def init_engine(self, database_url: str, debug: bool) -> None:
        """在 runner 循环内创建引擎与会话工厂（连接池绑定到 runner 循环）。"""
        self._started.wait(timeout=10)

        async def _create():
            engine = create_async_engine(
                database_url,
                echo=debug,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_recycle=3600,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 5},
            )
            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            return engine, factory

        self._engine, self._session_factory = self.run(_create())

    def run(self, coro, timeout: float = 20):
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout)

    def engine(self):
        return self._engine

    def session_factory(self):
        return self._session_factory

    def shutdown_engine(self) -> None:
        """释放 DB 引擎（连接池），但不停止后台事件循环线程。

        保留事件循环（daemon 线程，进程退出时自动回收），以便测试等多次
        lifespan 周期可安全重建引擎，不会因循环被停而崩溃。
        """
        if self._engine is not None:
            try:
                self.run(self._engine.dispose())
            except Exception as e:  # pragma: no cover - best effort
                logger.warning("释放 user_service 数据库引擎失败: %s", e)
        self._engine = None
        self._session_factory = None


_db_runner = _DBLoopRunner()
_db_initialized = False


def _ensure_engine() -> None:
    """按当前 settings 懒创建引擎（仅一次），连接池绑定到 runner 循环。"""
    global _db_initialized
    if not _db_initialized:
        _db_runner.init_engine(settings.DATABASE_URL, settings.DEBUG)
        _db_initialized = True


# ───────────────────────────────────────────────────────────────────────────
# DB 不可达时的短冷却：避免 MySQL 宕机时每次请求都去试连接
# ───────────────────────────────────────────────────────────────────────────
_db_unreachable_until = 0.0
_db_lock = threading.Lock()


def _db_is_enabled() -> bool:
    if _db_runner.session_factory() is None:
        return False
    now = time.monotonic()
    with _db_lock:
        return now >= _db_unreachable_until


def _mark_db_unreachable(failed: bool) -> None:
    global _db_unreachable_until
    now = time.monotonic()
    with _db_lock:
        _db_unreachable_until = (now + 15.0) if failed else 0.0


# ───────────────────────────────────────────────────────────────────────────
# 内存兜底（仅 DATABASE_URL 不可达时使用）
# ───────────────────────────────────────────────────────────────────────────
_lock = threading.Lock()
_users: Dict[str, dict] = {}  # key: 小写用户名
_next_id = 1

# 预置验证账户（演示/本地多账户验证用；DB 可达时同样会写入 DB）
_SEED_ACCOUNTS = [
    {"username": "alice", "password": "Alice@123", "email": "alice@example.com",
     "phone": "13800000001", "user_type": "customer"},
    {"username": "bob", "password": "Bob@123", "email": "bob@example.com",
     "phone": "13800000002", "user_type": "customer"},
    {"username": "admin", "password": "Admin@123", "email": "admin@example.com",
     "phone": "13800000003", "user_type": "admin"},
]

_seeded = False


def _seed_memory() -> None:
    """惰性初始化预置账户（仅一次）。"""
    global _seeded, _next_id
    if _seeded:
        return
    for acc in _SEED_ACCOUNTS:
        uid = _next_id
        _next_id += 1
        _users[acc["username"].lower()] = {
            "id": uid,
            "username": acc["username"],
            "email": acc.get("email"),
            "phone": acc.get("phone"),
            "password_hash": hash_password(acc["password"]),
            "user_type": acc.get("user_type", "customer"),
            "avatar_url": None,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }
    _seeded = True


def _to_response(u) -> UserResponse:
    """内存 dict 与 ORM User 均可转换为 UserResponse。"""
    if isinstance(u, dict):
        return UserResponse(
            id=u["id"],
            username=u["username"],
            email=u.get("email"),
            phone=u.get("phone"),
            user_type=u["user_type"],
            avatar_url=u.get("avatar_url"),
            is_active=u["is_active"],
            created_at=u["created_at"],
        )
    return UserResponse(
        id=u.id,
        username=u.username,
        email=u.email,
        phone=u.phone,
        user_type=u.user_type,
        avatar_url=u.avatar_url,
        is_active=u.is_active,
        created_at=u.created_at,
    )


# ── 内存兜底实现 ──
def _create_user_memory(req: UserCreateRequest) -> UserResponse:
    _seed_memory()
    key = req.username.lower()
    with _lock:
        if key in _users:
            raise ValueError("用户名已存在")
        if req.email:
            for u in _users.values():
                if u.get("email") and u["email"].lower() == req.email.lower():
                    raise ValueError("邮箱已被注册")
        if req.phone:
            for u in _users.values():
                if u.get("phone") and u["phone"] == req.phone:
                    raise ValueError("手机号已被注册")
        global _next_id
        uid = _next_id
        _next_id += 1
        _users[key] = {
            "id": uid,
            "username": req.username,
            "email": req.email,
            "phone": req.phone,
            "password_hash": hash_password(req.password),
            "user_type": "customer",
            "avatar_url": None,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }
        return _to_response(_users[key])


def _authenticate_memory(username: str, password: str) -> Optional[UserResponse]:
    _seed_memory()
    u = _users.get(username.lower())
    if not u or not u.get("is_active", True):
        return None
    if not verify_password(password, u["password_hash"]):
        return None
    return _to_response(u)


def _get_by_id_memory(user_id: int) -> Optional[UserResponse]:
    _seed_memory()
    for u in _users.values():
        if u["id"] == user_id:
            return _to_response(u)
    return None


def _list_usernames_memory() -> List[str]:
    _seed_memory()
    return [u["username"] for u in _users.values()]


# ───────────────────────────────────────────────────────────────────────────
# DB 后端实现（异步，运行在 _db_runner 的独立事件循环内）
# ───────────────────────────────────────────────────────────────────────────
async def _create_user_repo(req: UserCreateRequest) -> User:
    factory = _db_runner.session_factory()
    async with factory() as session:
        existing = await session.execute(
            select(User).where(func.lower(User.username) == req.username.lower())
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError("用户名已存在")
        if req.email:
            r = await session.execute(
                select(User).where(func.lower(User.email) == req.email.lower())
            )
            if r.scalar_one_or_none() is not None:
                raise ValueError("邮箱已被注册")
        if req.phone:
            r = await session.execute(select(User).where(User.phone == req.phone))
            if r.scalar_one_or_none() is not None:
                raise ValueError("手机号已被注册")
        user = User(
            username=req.username,
            email=req.email,
            phone=req.phone,
            password_hash=hash_password(req.password),
            user_type="customer",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _authenticate_repo(username: str, password: str) -> Optional[User]:
    factory = _db_runner.session_factory()
    async with factory() as session:
        r = await session.execute(
            select(User).where(func.lower(User.username) == username.lower())
        )
        user = r.scalar_one_or_none()
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user


async def _get_by_id_repo(user_id: int) -> Optional[User]:
    factory = _db_runner.session_factory()
    async with factory() as session:
        r = await session.execute(select(User).where(User.id == user_id))
        return r.scalar_one_or_none()


async def _list_usernames_repo() -> List[str]:
    factory = _db_runner.session_factory()
    async with factory() as session:
        r = await session.execute(select(User.username))
        return [row[0] for row in r.all()]


# DB 演示账户预置（仅一次，best-effort，失败不阻断注册）
_seeded_db = False


def _ensure_db_seed() -> None:
    global _seeded_db
    if _seeded_db:
        return
    try:
        _db_runner.run(_seed_demo_accounts_repo())
        _seeded_db = True
    except Exception as e:
        logger.warning("DB 预置演示账户失败（跳过，不影响注册）: %s", e)


async def _seed_demo_accounts_repo() -> None:
    factory = _db_runner.session_factory()
    async with factory() as session:
        for acc in _SEED_ACCOUNTS:
            r = await session.execute(
                select(User).where(func.lower(User.username) == acc["username"].lower())
            )
            if r.scalar_one_or_none() is None:
                session.add(User(
                    username=acc["username"],
                    email=acc.get("email"),
                    phone=acc.get("phone"),
                    password_hash=hash_password(acc["password"]),
                    user_type=acc.get("user_type", "customer"),
                    is_active=True,
                ))
        await session.commit()


# ───────────────────────────────────────────────────────────────────────────
# 公共 API（同步）—— DB 优先，失败回退内存
# ───────────────────────────────────────────────────────────────────────────
def create_user(req: UserCreateRequest) -> UserResponse:
    """注册新用户；用户名/邮箱/手机号冲突时抛 ValueError。DB 优先，不可达回退内存。"""
    if _db_is_enabled():
        try:
            _ensure_engine()
            _ensure_db_seed()
            user = _db_runner.run(_create_user_repo(req))
            if user is not None:
                return _to_response(user)
        except ValueError:
            raise
        except Exception as e:
            logger.warning("用户落库失败，回退内存模式: %s", e)
            _mark_db_unreachable(True)
    return _create_user_memory(req)


def authenticate(username: str, password: str) -> Optional[UserResponse]:
    """校验用户名/密码；成功返回用户，失败返回 None。DB 优先，不可达回退内存。"""
    if _db_is_enabled():
        try:
            user = _db_runner.run(_authenticate_repo(username, password))
            if user is not None:
                return _to_response(user)
        except Exception as e:
            logger.warning("DB 读取用户失败，回退内存模式: %s", e)
            _mark_db_unreachable(True)
    return _authenticate_memory(username, password)


def get_by_id(user_id: int) -> Optional[UserResponse]:
    """按 id 查询用户。DB 优先，不可达回退内存。"""
    if _db_is_enabled():
        try:
            user = _db_runner.run(_get_by_id_repo(user_id))
            if user is not None:
                return _to_response(user)
        except Exception as e:
            logger.warning("DB 读取用户失败，回退内存模式: %s", e)
            _mark_db_unreachable(True)
    return _get_by_id_memory(user_id)


def list_usernames() -> List[str]:
    """返回当前所有用户名（调试/验证用）。DB 优先，不可达回退内存。"""
    if _db_is_enabled():
        try:
            return _db_runner.run(_list_usernames_repo())
        except Exception as e:
            logger.warning("DB 列举用户失败，回退内存模式: %s", e)
            _mark_db_unreachable(True)
    return _list_usernames_memory()


# ───────────────────────────────────────────────────────────────────────────
# 生命周期 / 测试钩子（非 auth.py 调用的公共 API，供 main.py 与测试使用）
# ───────────────────────────────────────────────────────────────────────────
def shutdown_db() -> None:
    """优雅关闭：释放 user_service 的 DB 引擎（连接池），并允许后续重建。

    不停止事件循环线程（其为 daemon，进程退出自动回收），从而测试多次
    lifespan 周期可安全重建引擎，不会因循环被停而崩溃。
    """
    global _db_initialized
    try:
        _db_runner.shutdown_engine()
        _db_initialized = False
    except Exception as e:  # pragma: no cover - best effort
        logger.warning("关闭 user_service DB 资源失败: %s", e)


def ensure_db_alive() -> None:
    """确保引擎可用（被 lifespan 启动时调用）：若已释放则重建。"""
    _ensure_engine()


def _install_test_db(engine, factory) -> None:
    """测试钩子：用注入的引擎/会话工厂替换默认引擎（连接池绑定到 runner 循环）。

    调用方需自行在 runner 循环内建表，例如：
        user_service._db_runner.run(_create_tables(engine))
    然后调用本函数完成替换并清除「不可达」冷却。
    """
    global _db_initialized, _seeded_db
    _db_runner._engine = engine
    _db_runner._session_factory = factory
    _db_initialized = True
    _seeded_db = False
    _mark_db_unreachable(False)


# 模块加载时按当前 settings 创建引擎（连接池绑定到 runner 循环；懒连接，不阻断导入）。
_ensure_engine()
