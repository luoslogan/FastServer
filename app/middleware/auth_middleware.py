"""
路由级认证中间件示例

这个文件展示了如何使用路由级中间件来简化鉴权流程。
路由级中间件只对特定路由组生效，比全局中间件更灵活。
"""

from typing import Callable
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class AuthMiddleware(BaseHTTPMiddleware):
    """
    路由级认证中间件

    使用场景：
    1. 整个路由组都需要认证
    2. 需要在请求处理前统一设置用户信息
    3. 需要统一处理认证失败的情况

    注意：这个中间件会为所有请求执行认证，即使某些接口可能不需要。
    如果只需要部分接口认证，建议使用依赖注入。
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求，执行认证检查

        Args:
            request: FastAPI Request 对象
            call_next: 下一个中间件或路由处理函数

        Returns:
            Response: HTTP 响应
        """
        # 定义不需要认证的路径（相对于路由前缀）
        no_auth_paths = {
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
        }

        # 检查当前路径是否需要认证
        if request.url.path in no_auth_paths or request.url.path.startswith("/docs"):
            return await call_next(request)

        # 执行认证（这里简化处理，实际应该调用 get_current_user 的逻辑）
        # 注意：在中间件中直接使用依赖注入比较复杂，建议：
        # 1. 要么在中间件中手动实现认证逻辑
        # 2. 要么使用路由级依赖（dependencies 参数）而不是中间件

        # 这里展示如何在中间件中获取 token
        token = None
        # 优先从 Cookie 获取
        token = request.cookies.get("token")
        if not token:
            # 从 Header 获取
            authorization = request.headers.get("Authorization")
            if authorization and authorization.startswith("Bearer "):
                token = authorization.split(" ")[1]

        if not token:
            return Response(
                content='{"detail":"未提供认证凭据"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 继续处理请求
        response = await call_next(request)
        return response


# ============================================================================
# 推荐方式：使用路由级依赖而不是中间件
# ============================================================================
#
# 更推荐的方式是使用路由级依赖（dependencies 参数），而不是中间件。
#
# 示例 1：整个路由组都需要认证
# ------------------------------------------------------------
# from fastapi import APIRouter, Depends
# from app.dependencies.auth import get_current_user
#
# # 所有这个路由下的接口都需要认证
# protected_router = APIRouter(
#     prefix="/protected",
#     dependencies=[Depends(get_current_user)]  # 路由级依赖
# )
#
# @protected_router.get("/data")
# async def get_data():
#     # 这个接口自动需要认证，不需要再写 Depends(get_current_user)
#     return {"data": "protected data"}
#
# @protected_router.post("/create")
# async def create_data():
#     # 这个接口也自动需要认证
#     return {"message": "created"}
#
#
# 示例 2：需要特定权限的路由组
# ------------------------------------------------------------
# from fastapi import APIRouter, Depends
# from app.dependencies.permissions import require_permission
#
# # 所有内容管理接口都需要 content:read 权限
# content_router = APIRouter(
#     prefix="/content",
#     dependencies=[Depends(require_permission("content:read"))]
# )
#
# @content_router.get("/list")
# async def list_content():
#     # 自动需要 content:read 权限
#     return {"contents": []}
#
#
# 示例 3：混合使用（路由级 + 接口级）
# ------------------------------------------------------------
# from fastapi import APIRouter, Depends
# from app.dependencies.auth import get_current_user
# from app.dependencies.permissions import require_permission
#
# # 路由级：所有接口都需要登录
# user_router = APIRouter(
#     prefix="/users",
#     dependencies=[Depends(get_current_user)]  # 路由级：需要登录
# )
#
# @user_router.get("/me")
# async def get_me():
#     # 只需要登录（路由级已处理）
#     return {"user": "me"}
#
# @user_router.delete("/{user_id}")
# async def delete_user(
#     user_id: int,
#     _: None = Depends(require_permission("users:delete"))  # 接口级：额外需要权限
# ):
#     # 需要登录 + 特定权限
#     return {"message": "deleted"}
#
#
# 示例 4：使用 request.state.userinfo（推荐）
# ------------------------------------------------------------
# from fastapi import APIRouter, Depends, Request
# from app.dependencies.auth import get_current_user, get_userinfo
#
# # 路由级：设置 userinfo
# user_router = APIRouter(
#     prefix="/users",
#     dependencies=[Depends(get_current_user)]  # 这会设置 request.state.userinfo
# )
#
# # 方式 1：使用 Depends(get_userinfo)（推荐）
# # 优点：有错误处理、类型提示、符合 FastAPI 模式
# @user_router.get("/my-data")
# async def get_my_data(
#     userinfo: dict = Depends(get_userinfo)  # 从 request.state 获取，无需再查数据库
# ):
#     user_id = userinfo["user_id"]
#     username = userinfo["username"]
#     return {"user_id": user_id, "username": username}
#
# # 方式 2：直接访问 request.state.userinfo（也可以）
# # 优点：更直接，不需要额外的依赖
# # 注意：需要确保路由级依赖已经设置了 userinfo，否则可能报错
# @user_router.get("/my-data-direct")
# async def get_my_data_direct(request: Request):
#     # 直接访问 request.state.userinfo
#     userinfo = request.state.userinfo
#     user_id = userinfo["user_id"]
#     username = userinfo["username"]
#     return {"user_id": user_id, "username": username}
