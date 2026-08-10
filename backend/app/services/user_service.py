"""用户服务 — 进程内内存存储（MySQL 不可用时的最小可用实现）。

说明：本项目 lifespan 在 MySQL 不可达时会回退到内存模式。鉴权链路同样需要
可用的用户源，因此这里提供线程安全的内存用户表，并预置可验证的多账户。
生产环境应替换为 app.models.user.User 的数据库实现（保持相同接口即可）。
"""
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.security import hash_password, verify_password
from app.schemas.user import UserCreateRequest, UserLoginRequest, UserResponse

_lock = threading.Lock()
_users: Dict[str, dict] = {}  # key: 小写用户名
_next_id = 1

# 预置验证账户（演示/本地多账户验证用）
_SEED_ACCOUNTS = [
    {"username": "alice", "password": "Alice@123", "email": "alice@example.com",
     "phone": "13800000001", "user_type": "customer"},
    {"username": "bob", "password": "Bob@123", "email": "bob@example.com",
     "phone": "13800000002", "user_type": "customer"},
    {"username": "admin", "password": "Admin@123", "email": "admin@example.com",
     "phone": "13800000003", "user_type": "admin"},
]

_seeded = False


def _seed() -> None:
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


def _to_response(u: dict) -> UserResponse:
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


def create_user(req: UserCreateRequest) -> UserResponse:
    """注册新用户；用户名/邮箱/手机号冲突时抛 ValueError。"""
    _seed()
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


def authenticate(username: str, password: str) -> Optional[UserResponse]:
    """校验用户名/密码；成功返回用户，失败返回 None。"""
    _seed()
    u = _users.get(username.lower())
    if not u or not u.get("is_active", True):
        return None
    if not verify_password(password, u["password_hash"]):
        return None
    return _to_response(u)


def get_by_id(user_id: int) -> Optional[UserResponse]:
    """按 id 查询用户。"""
    _seed()
    for u in _users.values():
        if u["id"] == user_id:
            return _to_response(u)
    return None


def list_usernames() -> List[str]:
    """返回当前所有用户名（调试/验证用）。"""
    _seed()
    return [u["username"] for u in _users.values()]
