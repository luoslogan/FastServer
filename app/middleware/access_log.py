"""
HTTP 访问日志中间件

记录所有 HTTP 请求的访问日志到 access.log 文件.

使用方式:
    在 main.py 中添加:
    from app.middleware.access_log import AccessLogMiddleware
    app.add_middleware(AccessLogMiddleware)
"""

import time
from typing import Callable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.logging import get_access_logger

# 获取访问日志专用的 logger
access_logger = get_access_logger()


class AccessLogMiddleware(BaseHTTPMiddleware):
    """
    HTTP 访问日志中间件

    功能:
    1. 记录所有 HTTP 请求的访问日志
    2. 记录请求方法、路径、状态码、响应时间等信息
    3. 日志格式: {method} {path} {status_code} {duration}ms {client_ip}
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求并记录访问日志

        Args:
            request: FastAPI Request 对象
            call_next: 下一个中间件或路由处理函数

        Returns:
            Response: HTTP 响应
        """
        # 记录请求开始时间
        start_time = time.time()

        # 获取客户端 IP
        client_ip = request.client.host if request.client else "unknown"

        # 处理请求
        response = await call_next(request)

        # 计算响应时间
        duration = (time.time() - start_time) * 1000  # 转换为毫秒

        # 记录访问日志
        access_logger.info(
            f"{request.method} {request.url.path} {response.status_code} {duration:.2f}ms {client_ip}"
        )

        return response
