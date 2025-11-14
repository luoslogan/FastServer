from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """应用配置，从环境变量读取"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # 忽略未定义的额外环境变量(如数据库容器初始化变量)
    )

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

    # 日志配置
    LOG_LEVEL: str = Field(
        default="INFO", description="日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)"
    )
    LOG_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "logs",
        description="日志目录路径",
    )
    ENABLE_ACCESS_LOG: bool = Field(default=True, description="是否启用 HTTP 访问日志")

    # 邮件配置（用于邮箱验证和密码重置）
    SMTP_HOST: Optional[str] = Field(default=None, description="SMTP 服务器地址")
    SMTP_PORT: int = Field(default=587, description="SMTP 服务器端口")
    SMTP_USER: Optional[str] = Field(
        default=None, description="SMTP 用户名（通常是邮箱地址）"
    )
    SMTP_PASSWORD: Optional[str] = Field(
        default=None, description="SMTP 密码或应用专用密码"
    )
    SMTP_FROM_EMAIL: Optional[str] = Field(default=None, description="发件人邮箱地址")
    SMTP_FROM_NAME: str = Field(default="FastAPI Server", description="发件人名称")
    SMTP_USE_TLS: bool = Field(default=True, description="是否使用 TLS")
    # 前端 URL（用于生成验证链接）
    # 如果设置为后端地址（如 http://localhost:8000），则直接使用后端页面完成验证（不需要前端）
    # 如果设置为前端地址（如 https://myapp.com），则使用前端页面完成验证（需要前端配合）
    FRONTEND_URL: str = Field(
        default="http://localhost:8000",
        description="前端应用 URL 或后端 API URL（用于生成验证链接）",
    )


settings = Settings()
