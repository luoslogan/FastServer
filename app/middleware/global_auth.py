"""
全局认证中间件

强制所有接口都需要认证(除了白名单中的路径).
自动设置 request.state.userinfo, 方便后续使用.

使用说明:
1. 在 main.py 中已注册此中间件
2. 所有接口(除了白名单)都需要提供有效的 Token
3. Token 可以从 Cookie 或 Header (Authorization Bearer) 获取
4. 认证成功后, 会自动设置 request.state.userinfo
5. 后续代码可以直接使用 request.state.userinfo 或 Depends(get_userinfo)

白名单路径(不需要认证):
- / (根路径)
- /health (健康检查)
- /docs, /openapi.json, /redoc (API 文档)
- /api/v1/auth/* (认证相关接口, 如登录, 注册)

如果需要添加更多白名单路径, 修改 NO_AUTH_PATHS 或 NO_AUTH_PREFIXES.
"""

from typing import Callable
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from sqlalchemy import select

from app.core.security import decode_access_token
from app.core.db import AsyncSessionLocal
from app.models.user import User


class GlobalAuthMiddleware(BaseHTTPMiddleware):
    """
    全局认证中间件

    功能:
    1. 强制所有接口都需要认证(除了白名单)
    2. 自动从 Cookie 或 Header 获取 Token
    3. 验证 Token 并查询用户
    4. 自动设置 request.state.userinfo
    5. 如果认证失败, 返回 401 错误

    白名单路径(不需要认证):
    - / (根路径)
    - /health (健康检查)
    - /docs, /openapi.json, /redoc (API 文档)
    - /api/v1/auth/* (认证相关接口, 如登录, 注册)
    """

    # 不需要认证的路径(白名单)
    NO_AUTH_PATHS = {
        "/",
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    }

    # 不需要认证的路径前缀
    NO_AUTH_PREFIXES = (
        "/docs/",
        "/api/v1/auth/",  # 认证相关接口(登录, 注册等)
    )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求，执行全局认证检查

        Args:
            request: FastAPI Request 对象
            call_next: 下一个中间件或路由处理函数

        Returns:
            Response: HTTP 响应
        """
        # 检查是否在白名单中
        if self._is_no_auth_path(request.url.path):
            return await call_next(request)

        # 获取 Token
        token = self._get_token_from_request(request)
        if not token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "未提供认证凭据"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 验证 Token 并获取用户
        user = await self._authenticate_token(token)
        if not user:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "无效的认证凭据"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 检查用户是否激活
        if not user.is_active:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "用户已被禁用"},
            )

        # 设置 request.state.userinfo(方便后续使用)
        request.state.userinfo = {
            "user": user,
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
        }

        # 继续处理请求
        response = await call_next(request)
        return response

    def _is_no_auth_path(self, path: str) -> bool:
        """
        检查路径是否在白名单中(不需要认证)

        Args:
            path: 请求路径

        Returns:
            bool: 如果不需要认证返回 True
        """
        # 检查完整路径
        if path in self.NO_AUTH_PATHS:
            return True

        # 检查路径前缀
        for prefix in self.NO_AUTH_PREFIXES:
            if path.startswith(prefix):
                return True

        return False

    def _get_token_from_request(self, request: Request) -> str | None:
        """
        从请求中获取 Token, 支持 Cookie 和 Header 两种方式

        优先级: Cookie > Header (Authorization Bearer)

        Args:
            request: FastAPI Request 对象

        Returns:
            str: Token 字符串, 如果未找到则返回 None
        """
        # 1. 优先从 Cookie 获取
        token = request.cookies.get("token")
        if token:
            return token

        # 2. 从 Header 获取
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            return authorization.split(" ")[1]

        return None

    async def _authenticate_token(self, token: str) -> User | None:
        """
        验证 Token 并获取用户

        Args:
            token: JWT Token

        Returns:
            User: 用户对象，如果 Token 无效则返回 None
        """
        try:
            # 解码 Token
            payload = decode_access_token(token)
            if payload is None:
                return None

            # 从 Token 中获取用户名
            username: str = payload.get("sub")
            if username is None:
                return None

            # 从数据库查询用户
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(User).where(User.username == username))
                user = result.scalar_one_or_none()
                # 在会话关闭前刷新对象, 确保所有属性都已加载
                if user:
                    await db.refresh(user)
                return user
        except Exception:
            # 捕获所有异常, 避免中间件崩溃影响整个应用
            # 在生产环境中应该记录日志
            return None
