"""
认证路由
- 用户注册
- 用户登录
- 获取当前用户信息
"""

from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.db import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    hash_token,
)
from app.core.config import settings
from app.core.redis import get_redis_client
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.dependencies.auth import get_current_user
from app.schemas.auth import (
    Token,
    TokenRefresh,
    TokenRefreshResponse,
    LogoutResponse,
    UserRegister,
    DeviceListResponse,
    RevokeDeviceResponse,
    RefreshTokenInfo,
)
from app.schemas.user import UserResponse
from app.core.security import decode_refresh_token
from app.utils.token import TokenService

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    """
    用户注册

    - **username**: 用户名(3-50个字符)
    - **email**: 邮箱地址
    - **password**: 密码(至少6个字符)
    - **full_name**: 全名(可选)
    """
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在"
        )

    # 检查邮箱是否已存在
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被注册"
        )

    # 创建新用户
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        is_active=True,
        is_superuser=False,
    )

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    return db_user


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    用户登录

    使用 OAuth2 标准格式(username 和 password)
    返回 JWT Access Token 和 Refresh Token, 同时设置 Cookie(用于 Web 应用)

    注意:
    - Access Token 和 Refresh Token 会同时通过响应体和 Cookie 返回
    - Cookie 名称: "token" (Access Token), "refresh_token" (Refresh Token)
    - Cookie 属性: HttpOnly=True, Secure=True (生产环境), SameSite=Lax
    """
    # 查询用户(支持用户名或邮箱登录)
    result = await db.execute(
        select(User).where(
            (User.username == form_data.username) | (User.email == form_data.username)
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 验证密码
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 检查用户是否激活
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用"
        )

    # 创建 Access Token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # 创建 Refresh Token
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token_value = create_refresh_token(
        data={"sub": user.username, "user_id": user.id},
        expires_delta=refresh_token_expires,
    )

    # 获取设备信息
    user_agent = request.headers.get("user-agent", "")
    ip_address = request.client.host if request.client else None

    # 解析设备信息
    device_info = None
    device_type = "web"
    if user_agent:
        # 简单的设备类型判断
        user_agent_lower = user_agent.lower()
        if (
            "mobile" in user_agent_lower
            or "android" in user_agent_lower
            or "iphone" in user_agent_lower
        ):
            device_type = "mobile"
        elif "tablet" in user_agent_lower or "ipad" in user_agent_lower:
            device_type = "tablet"
        elif (
            "windows" in user_agent_lower
            or "mac" in user_agent_lower
            or "linux" in user_agent_lower
        ):
            device_type = "desktop"

        device_info = {
            "type": device_type,
            "name": user_agent[:100],  # 限制长度
            "user_agent": user_agent,
        }

    # 存储 Refresh Token
    redis = await get_redis_client()
    await TokenService.store_refresh_token(
        token=refresh_token_value,
        user_id=user.id,
        username=user.username,
        redis=redis,
        db=db,
        device_info=device_info,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # 设置 Cookie（用于 Web 应用自动携带）
    # HttpOnly: 防止 JavaScript 访问，提高安全性
    # Secure: 只在 HTTPS 下传输（生产环境建议开启）
    # SameSite: 防止 CSRF 攻击
    access_token_max_age = int(access_token_expires.total_seconds())
    refresh_token_max_age = int(refresh_token_expires.total_seconds())

    response.set_cookie(
        key="token",
        value=access_token,
        max_age=access_token_max_age,
        httponly=True,
        secure=not settings.DEBUG,  # 生产环境启用 Secure
        samesite="lax",
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token_value,
        max_age=refresh_token_max_age,
        httponly=True,
        secure=not settings.DEBUG,  # 生产环境启用 Secure
        samesite="lax",
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_value,
        "token_type": "bearer",
        "expires_in": access_token_max_age,
    }


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_access_token(
    request: Request,
    response: Response,
    token_data: Optional[TokenRefresh] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    刷新 Access Token

    使用 Refresh Token 获取新的 Access Token
    Refresh Token 可以从请求体或 Cookie 中获取

    注意:
    - Refresh Token 必须有效且未被撤销
    - 返回新的 Access Token
    - Refresh Token 保持不变
    """
    # 从请求体或 Cookie 获取 Refresh Token
    refresh_token_value = None
    if token_data and token_data.refresh_token:
        refresh_token_value = token_data.refresh_token
    else:
        refresh_token_value = request.cookies.get("refresh_token")

    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供 Refresh Token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 解码 Refresh Token
    payload = decode_refresh_token(refresh_token_value)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Refresh Token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 验证 Refresh Token 是否在黑名单中
    token_hash = hash_token(refresh_token_value)
    redis = await get_redis_client()
    token_info = await TokenService.get_refresh_token(token_hash, redis)
    if not token_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh Token 已失效",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 获取用户信息
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Refresh Token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 查询用户
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 创建新的 Access Token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # 更新 Cookie
    access_token_max_age = int(access_token_expires.total_seconds())
    response.set_cookie(
        key="token",
        value=access_token,
        max_age=access_token_max_age,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": access_token_max_age,
    }


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    用户登出

    撤销当前的 Refresh Token, 清除 Cookie

    注意:
    - 需要提供有效的 Refresh Token
    - 登出后, Refresh Token 将被加入黑名单
    """
    # 从 Cookie 获取 Refresh Token
    refresh_token_value = request.cookies.get("refresh_token")

    if refresh_token_value:
        # 撤销 Refresh Token
        token_hash = hash_token(refresh_token_value)
        redis = await get_redis_client()
        await TokenService.revoke_refresh_token(token_hash, redis, db)

    # 清除 Cookie
    response.delete_cookie(key="token", httponly=True, samesite="lax")
    response.delete_cookie(key="refresh_token", httponly=True, samesite="lax")

    return LogoutResponse(message="登出成功")


@router.get("/devices", response_model=DeviceListResponse)
async def get_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户的所有登录设备

    返回所有有效的 Refresh Token 信息, 包括设备信息、IP地址、登录时间等
    """
    tokens = await TokenService.get_user_tokens(
        current_user.id, db, include_revoked=False
    )

    devices = [
        RefreshTokenInfo(
            id=token.id,
            device_name=token.device_name,
            device_type=token.device_type,
            ip_address=token.ip_address,
            created_at=token.created_at.isoformat(),
            expires_at=token.expires_at.isoformat(),
            revoked=token.revoked,
        )
        for token in tokens
    ]

    return DeviceListResponse(devices=devices, total=len(devices))


@router.delete("/devices/{device_id}", response_model=RevokeDeviceResponse)
async def revoke_device(
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    撤销指定设备的登录

    撤销后, 该设备的 Refresh Token 将失效, 需要重新登录
    """
    # 查询 Token
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.id == device_id, RefreshToken.user_id == current_user.id
        )
    )
    token = result.scalar_one_or_none()

    if token is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")

    if token.revoked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="设备已被撤销"
        )

    # 撤销 Token
    redis = await get_redis_client()
    await TokenService.revoke_refresh_token(token.token_hash, redis, db)

    return RevokeDeviceResponse(message="设备已撤销")


@router.post("/devices/revoke-all", response_model=LogoutResponse)
async def revoke_all_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    撤销所有设备的登录(除了当前设备)

    撤销后, 所有其他设备的 Refresh Token 将失效, 需要重新登录
    当前设备的 Token 不受影响
    """
    redis = await get_redis_client()
    revoked_count = await TokenService.revoke_all_user_tokens(
        current_user.id, redis, db
    )

    return LogoutResponse(message=f"已撤销 {revoked_count} 个设备的登录")


# 注意：/me 端点已移至 users 路由，这里保留是为了向后兼容
# 实际实现请使用 /api/v1/users/me
