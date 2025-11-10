from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

# MongoDB 客户端实例（单例模式，按需连接）
_client: Optional[AsyncIOMotorClient] = None


async def get_mongodb_client() -> AsyncIOMotorClient:
    """
    获取 MongoDB 客户端（单例模式，按需连接）

    Returns:
        AsyncIOMotorClient: MongoDB 异步客户端
    """
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=5000,
        )
    return _client


async def get_mongodb(db_name: str) -> AsyncIOMotorDatabase:
    """
    获取 MongoDB 数据库实例

    Args:
        db_name: 数据库名称

    Returns:
        AsyncIOMotorDatabase: MongoDB 数据库实例
    """
    client = await get_mongodb_client()
    return client[db_name]


# FastAPI 依赖注入
def get_mongodb_db(db_name: str):
    """
    FastAPI 依赖注入：获取 MongoDB 数据库实例
    使用示例:
        @app.get("/items/")
        async def read_items(db: AsyncIOMotorDatabase = Depends(get_mongodb_db("my_db"))):
            collection = db["items"]
            items = await collection.find().to_list(length=100)
            return items
    """

    async def _get_db() -> AsyncIOMotorDatabase:
        return await get_mongodb(db_name)

    return _get_db
