from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import info_hub, auth, users, roles, permissions
from app.middleware.global_auth import GlobalAuthMiddleware

# 创建 FastAPI 应用实例
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)

# 配置 CORS(必须在认证中间件之前)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应指定具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置全局认证中间件(强制所有接口都需要认证, 除了白名单)
# 注意: 中间件的执行顺序是后进先出(LIFO), 所以认证中间件会在 CORS 之后执行
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
app.include_router(info_hub.router, prefix=settings.API_V1_PREFIX)
