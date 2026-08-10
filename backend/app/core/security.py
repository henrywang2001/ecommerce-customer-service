"""安全认证模块"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

# 使用 pbkdf2_sha256 而非 bcrypt：避免 passlib 与 bcrypt 4.x 后端探测不兼容
# （bcrypt 4.x 在后端自检测时会抛出 "password cannot be longer than 72 bytes"），
# 该方案为纯 Python 实现，跨环境稳定且强度足够。
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """哈希密码"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT 访问令牌"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> Optional[dict]:
    """解码 JWT 令牌"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


def get_current_user(request: Request) -> Optional[dict]:
    """从鉴权中间件写入的 request.state.user 取回 JWT 载荷。

    - REQUIRE_AUTH=True（生产）：缺失或无效令牌直接 401。
    - REQUIRE_AUTH=False（demo）：返回 None，由业务层决定是否放行。
    调用方应优先使用令牌中的 user_id（不可伪造），而非前端传入值。
    """
    payload = getattr(request.state, "user", None)
    if settings.REQUIRE_AUTH and not payload:
        raise HTTPException(status_code=401, detail="未认证或认证失效，请提供 Bearer 令牌。")
    return payload


def current_user_id(request: Request) -> Optional[int]:
    """从令牌载荷中提取 user_id（sub）。"""
    payload = get_current_user(request)
    if not payload:
        return None
    sub = payload.get("sub")
    try:
        return int(sub) if sub is not None else None
    except (TypeError, ValueError):
        return None
