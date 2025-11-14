from typing import AsyncGenerator

from loguru import logger
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.core.config import settings

# 创建 Base 类，用于定义数据库模型
Base = declarative_base()

async_database_url: str = settings.DATABASE_URL

# 创建异步数据库引擎
engine = create_async_engine(
    async_database_url,
    # 连接池配置
    pool_size=20,  # 连接池大小（默认 5，建议根据并发量调整）
    max_overflow=10,  # 最大溢出连接数（超过 pool_size 时可以创建的额外连接）
    pool_recycle=3600,  # 连接回收时间（秒），超过此时间的连接会被回收重建
    pool_pre_ping=True,  # 连接前检查连接是否有效，自动重连失效连接
    # 其他配置
    echo=settings.DEBUG,  # 调试模式下打印 SQL
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    异步数据库会话依赖注入
    使用示例:
        @app.get("/items/")
        async def read_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"数据库会话异常: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()
