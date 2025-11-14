from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.routers import auth, users, roles, permissions
from app.middleware.global_auth import GlobalAuthMiddleware
from app.middleware.access_log import AccessLogMiddleware

# 初始化日志系统 (必须在其他模块导入之前)
setup_logging(
    log_dir=settings.LOG_DIR,
    log_level=settings.LOG_LEVEL if not settings.DEBUG else "DEBUG",
    enable_access_log=settings.ENABLE_ACCESS_LOG,
)

# 创建 FastAPI 应用实例
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)

# 根据环境变量配置CORS
if settings.DEBUG:
    # 开发环境：允许所有（但不使用Cookie）
    allow_origins = ["*"]
    allow_credentials = False
else:
    # 生产环境：指定具体域名（使用Cookie）
    allow_origins = [
        "http://137.59.101.10:80",
        "http://137.59.101.10",
    ]
    allow_credentials = True

# 配置 CORS(必须在认证中间件之前)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置访问日志中间件(记录所有 HTTP 请求)
# 注意: 中间件的执行顺序是后进先出(LIFO), 访问日志中间件最先执行
app.add_middleware(AccessLogMiddleware)

# 配置全局认证中间件(强制所有接口都需要认证, 除了白名单)
# 注意: 中间件的执行顺序是后进先出(LIFO), 认证中间件会在 CORS 之后执行
app.add_middleware(GlobalAuthMiddleware)


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Welcome to FastAPI Server",
        "version": settings.APP_VERSION,
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


# 注册路由
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)
app.include_router(roles.router, prefix=settings.API_V1_PREFIX)
app.include_router(permissions.router, prefix=settings.API_V1_PREFIX)
