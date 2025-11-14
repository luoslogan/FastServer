"""
安全工具模块
- JWT Token 生成和验证
- 密码加密和验证
"""

import hashlib
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from loguru import logger
from passlib.context import CryptContext

from app.core.config import settings

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码

    Args:
        plain_password: 明文密码
        hashed_password: 加密后的密码

    Returns:
        bool: 密码是否正确
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    加密密码

    Args:
        password: 明文密码

    Returns:
        str: 加密后的密码
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建 JWT Access Token

    Args:
        data: 要编码到 Token 中的数据(通常是用户ID, 用户名等)
        expires_delta: 过期时间增量, 如果为 None 则使用默认值

    Returns:
        str: JWT Token 字符串
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire, "iat": datetime.now()})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    解码 JWT Token

    Args:
        token: JWT Token 字符串

    Returns:
        dict: 解码后的数据，如果 Token 无效则返回 None
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError as e:
        logger.debug(f"Token 解码失败: {e}")
        return None


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建 JWT Refresh Token

    Args:
        data: 要编码到 Token 中的数据(通常是用户ID, 用户名等)
        expires_delta: 过期时间增量, 如果为 None 则使用默认值

    Returns:
        str: JWT Refresh Token 字符串
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire, "iat": datetime.now(), "type": "refresh"})

    # 使用 Refresh Token 专用密钥或默认密钥
    secret_key = (
        settings.REFRESH_TOKEN_SECRET_KEY
        if settings.REFRESH_TOKEN_SECRET_KEY
        else settings.SECRET_KEY
    )

    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_refresh_token(token: str) -> Optional[dict]:
    """
    解码 JWT Refresh Token

    Args:
        token: JWT Refresh Token 字符串

    Returns:
        dict: 解码后的数据，如果 Token 无效则返回 None
    """
    try:
        # 使用 Refresh Token 专用密钥或默认密钥
        secret_key = (
            settings.REFRESH_TOKEN_SECRET_KEY
            if settings.REFRESH_TOKEN_SECRET_KEY
            else settings.SECRET_KEY
        )

        payload = jwt.decode(token, secret_key, algorithms=[settings.ALGORITHM])

        # 验证 Token 类型
        if payload.get("type") != "refresh":
            return None

        return payload
    except JWTError as e:
        logger.debug(f"Refresh Token 解码失败: {e}")
        return None


def hash_token(token: str) -> str:
    """
    对 Token 进行哈希处理(用于存储)

    Args:
        token: Token 字符串

    Returns:
        str: Token 的 SHA256 哈希值
    """
    return hashlib.sha256(token.encode()).hexdigest()


def create_email_verification_token(user_id: int, email: str) -> str:
    """
    创建邮箱验证 Token

    Args:
        user_id: 用户ID
        email: 邮箱地址

    Returns:
        str: 验证 Token
    """
    data = {
        "user_id": user_id,
        "email": email,
        "type": "email_verification",
    }
    expires_delta = timedelta(hours=24)  # 24小时过期
    return create_access_token(data, expires_delta=expires_delta)


def decode_email_verification_token(token: str) -> Optional[dict]:
    """
    解码邮箱验证 Token

    Args:
        token: 验证 Token

    Returns:
        dict: 解码后的数据，如果 Token 无效则返回 None
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        # 验证 Token 类型
        if payload.get("type") != "email_verification":
            return None
        return payload
    except JWTError as e:
        logger.debug(f"邮箱验证 Token 解码失败: {e}")
        return None


def create_password_reset_token(user_id: int, email: str) -> str:
    """
    创建密码重置 Token

    Args:
        user_id: 用户ID
        email: 邮箱地址

    Returns:
        str: 重置 Token
    """
    data = {
        "user_id": user_id,
        "email": email,
        "type": "password_reset",
    }
    expires_delta = timedelta(hours=1)  # 1小时过期
    return create_access_token(data, expires_delta=expires_delta)


def decode_password_reset_token(token: str) -> Optional[dict]:
    """
    解码密码重置 Token

    Args:
        token: 重置 Token

    Returns:
        dict: 解码后的数据，如果 Token 无效则返回 None
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        # 验证 Token 类型
        if payload.get("type") != "password_reset":
            return None
        return payload
    except JWTError as e:
        logger.debug(f"密码重置 Token 解码失败: {e}")
        return None
