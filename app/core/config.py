from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """应用配置，从环境变量读取"""

    # 应用基础配置（非敏感，可保留默认值）
    APP_NAME: str = "FastAPI Server"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    BASE_PATH: Path = Path(__file__).resolve().parent.parent

    # 数据库配置（敏感，必须从环境变量读取）
    DATABASE_URL: str = Field(..., description="数据库连接 URL, 必须从环境变量读取")

    # Redis 配置（生产环境建议从环境变量读取）
    REDIS_HOST: str = Field(default="localhost", description="Redis 主机地址")
    REDIS_PORT: int = Field(default=6379, description="Redis 端口")
    REDIS_DB: int = Field(default=0, description="Redis 数据库编号")
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redis 密码")

    # MongoDB 配置（敏感，必须从环境变量读取）
    # MONGODB_URL 格式: mongodb://username:password@host:port/?authSource=admin
    # 注意：URL 中不包含数据库名，数据库名在调用时传入
    MONGODB_URL: str = Field(
        ..., description="MongoDB 连接 URL(不含数据库名), 必须从环境变量读取"
    )

    # API 配置（非敏感，可保留默认值）
    API_V1_PREFIX: str = "/api/v1"

    # 安全配置（敏感，必须从环境变量读取）
    SECRET_KEY: str = Field(..., description="密钥, 用于加密和签名, 必须从环境变量读取")
    ALGORITHM: str = Field(default="HS256", description="JWT 算法")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30, description="访问令牌过期时间, 单位: 分钟"
    )
    # Refresh Token 配置
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=30, description="刷新令牌过期时间, 单位: 天"
    )
    REFRESH_TOKEN_SECRET_KEY: Optional[str] = Field(
        default=None,
        description="Refresh Token 专用密钥(可选, 默认使用 SECRET_KEY)",
    )

    class Config:
        # 安全配置：不读取 .env 文件，只从环境变量读取
        # docker-compose 的 env_file 会将 .env 中的变量注入为环境变量
        # 这样 .env 文件不需要挂载到容器中，更安全
        # 如果需要在本地开发时读取 .env 文件，可以在本地运行时设置环境变量
        case_sensitive = True


settings = Settings()
