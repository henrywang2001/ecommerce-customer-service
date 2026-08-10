"""认证 API 路由 — 登录 / 注册 / 当前用户 (F6)"""
from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.security import create_access_token, get_current_user
from app.schemas.user import UserCreateRequest, UserLoginRequest, UserResponse, TokenResponse
from app.services import user_service

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
async def register(req: UserCreateRequest):
    """注册新用户并直接签发 JWT。"""
    try:
        user = user_service.create_user(req)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    token = create_access_token({
        "sub": str(user.id),
        "username": user.username,
        "user_type": user.user_type,
    })
    return TokenResponse(access_token=token, user=user)


@router.post("/login", response_model=TokenResponse)
async def login(req: UserLoginRequest):
    """用户名/密码登录，成功后返回 JWT。"""
    user = user_service.authenticate(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token({
        "sub": str(user.id),
        "username": user.username,
        "user_type": user.user_type,
    })
    return TokenResponse(access_token=token, user=user)


@router.get("/me", response_model=UserResponse)
async def me(request: Request):
    """返回当前登录用户信息（需有效 JWT）。"""
    payload = get_current_user(request)
    if not payload:
        raise HTTPException(status_code=401, detail="未认证或认证失效")
    user = user_service.get_by_id(int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user
