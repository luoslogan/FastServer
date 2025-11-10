from typing import Optional
from redis.asyncio import Redis, ConnectionPool
from app.core.config import settings

# Redis 连接池实例（单例模式）
_pool: Optional[ConnectionPool] = None
_redis_client: Optional[Redis] = None


def _build_redis_url() -> str:
    """构建 Redis 连接 URL"""
    if settings.REDIS_PASSWORD:
        redis_url = f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    else:
        redis_url = (
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
        )
    return redis_url


async def get_redis_client() -> Redis:
    """
    获取 Redis 客户端（单例模式，使用连接池）

    Returns:
        Redis: Redis 异步客户端
    """
    global _pool, _redis_client  # noqa: PLW0603
    if _pool is None or _redis_client is None:
        # 创建连接池
        _pool = ConnectionPool.from_url(
            _build_redis_url(),
            max_connections=50,  # 最大连接数
            decode_responses=True,  # 自动解码响应为字符串
        )
        # 创建 Redis 客户端
        _redis_client = Redis(connection_pool=_pool)

    return _redis_client


async def close_redis_client():
    """
    关闭 Redis 客户端和连接池
    通常在应用关闭时调用
    """
    global _pool, _redis_client  # noqa: PLW0603
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
    if _pool:
        await _pool.disconnect()
        _pool = None


# FastAPI 依赖注入
async def get_redis() -> Redis:
    """
    FastAPI 依赖注入：获取 Redis 客户端
    使用示例:
        @app.get("/cache/")
        async def get_cache(redis: Redis = Depends(get_redis)):
            value = await redis.get("key")
            return {"value": value}
    """
    return await get_redis_client()
