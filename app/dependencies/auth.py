"""
认证相关的依赖注入
"""

from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import (
    OAuth2PasswordBearer,
    HTTPBearer,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.db import get_db
from app.core.security import decode_access_token
from app.models.user import User

# OAuth2 密码流(用于从请求头获取 Token, 保持向后兼容)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# HTTP Bearer 方案(用于手动处理)
http_bearer = HTTPBearer(auto_error=False)


async def get_token_from_request(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[str]:
    """
    从请求中获取 Token, 支持 Cookie 和 Header 两种方式

    优先级: Cookie > Header (Authorization Bearer)

    Args:
        request: FastAPI Request 对象
        token: 从 Header 中提取的 token(通过 OAuth2PasswordBearer)

    Returns:
        str: Token 字符串, 如果未找到则返回 None
    """
    # 1. 优先从 Cookie 获取
    token_from_cookie = request.cookies.get("token")
    if token_from_cookie:
        return token_from_cookie

    # 2. 从 Header 获取(通过 OAuth2PasswordBearer)
    if token:
        return token

    # 3. 尝试直接从 Authorization Header 获取(兼容性处理)
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        return authorization.split(" ")[1]

    return None


async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(get_token_from_request),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    获取当前登录用户

    支持从 Cookie 和 Header (Authorization Bearer) 两种方式获取 Token
    优先级: Cookie > Header

    **性能优化**:
    - 如果全局中间件已经认证并设置了 request.state.userinfo, 直接复用, 不重复查询数据库
    - 如果没有, 则进行认证并设置 request.state.userinfo

    **注意**:
    - 如果全局中间件已启用, 此函数主要作用是提供类型安全的 User 对象
    - 实际认证工作由全局中间件完成

    Args:
        request: FastAPI Request 对象(用于获取 Cookie 和设置 userinfo)
        token: JWT Token(从 Cookie 或 Header 自动获取)
        db: 数据库会话

    Returns:
        User: 当前用户对象

    Raises:
        HTTPException: Token 无效或用户不存在
    """
    # 性能优化: 如果全局中间件已经认证并设置了 userinfo, 直接复用
    # 这是最常见的情况(全局中间件已启用)
    if hasattr(request.state, "userinfo") and request.state.userinfo:
        return request.state.userinfo["user"]

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 检查是否有 Token
    if not token:
        raise credentials_exception

    # 解码 Token
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    # 从 Token 中获取用户名
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    # 从数据库查询用户
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用"
        )

    # 设置 request.state.userinfo, 方便后续依赖和路由使用
    # 这样就不需要重复查询数据库了
    request.state.userinfo = {
        "user": user,
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
    }

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    获取当前活跃用户(确保用户已激活)

    Args:
        current_user: 当前用户(从 get_current_user 获取)

    Returns:
        User: 当前活跃用户

    Raises:
        HTTPException: 用户未激活
    """
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户未激活")
    return current_user


async def require_superuser(current_user: User = Depends(get_current_user)) -> User:
    """
    要求超级用户权限

    Args:
        current_user: 当前用户

    Returns:
        User: 当前超级用户

    Raises:
        HTTPException: 不是超级用户
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="需要超级用户权限"
        )
    return current_user


async def get_userinfo(request: Request) -> dict:
    """
    从 request.state 获取用户信息

    这是一个便捷的依赖函数, 用于在不需要完整 User 对象时快速获取用户信息.
    使用前提: 必须先调用过 get_current_user(或其他会设置 request.state.userinfo 的依赖)

    Args:
        request: FastAPI Request 对象

    Returns:
        dict: 包含用户信息的字典, 格式:
            {
                "user": User对象,
                "user_id": int,
                "username": str,
                "email": str,
                "full_name": str | None,
                "is_active": bool,
                "is_superuser": bool,
            }

    Raises:
        HTTPException: 如果 request.state.userinfo 不存在(用户未认证)

    使用示例:
        @router.get("/my-data")
        async def get_my_data(userinfo: dict = Depends(get_userinfo)):
            user_id = userinfo["user_id"]
            username = userinfo["username"]
            # 直接使用, 不需要再查询数据库
    """
    if not hasattr(request.state, "userinfo"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未认证, 请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return request.state.userinfo
