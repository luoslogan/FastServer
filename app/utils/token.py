"""
Token 管理工具

提供 Refresh Token 的存储、验证、撤销等功能
使用 Redis 作为主要存储，数据库作为持久化存储
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List

from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.config import settings
from app.core.redis import get_redis_client
from app.core.security import hash_token
from app.models.refresh_token import RefreshToken


class TokenService:
    """Token 服务类"""

    @staticmethod
    def _get_token_key(token_hash: str) -> str:
        """获取 Redis Key"""
        return f"refresh_token:{token_hash}"

    @staticmethod
    def _get_blacklist_key(token_hash: str) -> str:
        """获取黑名单 Redis Key"""
        return f"token_blacklist:{token_hash}"

    @staticmethod
    def _get_user_tokens_key(user_id: int) -> str:
        """获取用户所有 Token 的 Redis Key"""
        return f"user_tokens:{user_id}"

    @staticmethod
    async def store_refresh_token(
        token: str,
        user_id: int,
        username: str,
        redis: Optional[Redis] = None,
        db: Optional[AsyncSession] = None,
        device_info: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """
        存储 Refresh Token

        Args:
            token: Refresh Token 字符串
            user_id: 用户ID
            username: 用户名
            redis: Redis 客户端(可选)
            db: 数据库会话(可选, 用于持久化存储)
            device_info: 设备信息字典
            ip_address: IP 地址
            user_agent: User-Agent

        Returns:
            str: Token 哈希值
        """
        token_hash = hash_token(token)
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        # 存储到 Redis
        if redis is None:
            redis = await get_redis_client()

        token_data = {
            "user_id": user_id,
            "username": username,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat(),
            "device_info": json.dumps(device_info) if device_info else None,
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        # 计算 TTL (秒)
        ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())

        # 存储到 Redis
        await redis.setex(
            TokenService._get_token_key(token_hash),
            ttl,
            json.dumps(token_data),
        )

        # 将 Token 哈希添加到用户的 Token 集合中
        await redis.sadd(TokenService._get_user_tokens_key(user_id), token_hash)
        await redis.expire(
            TokenService._get_user_tokens_key(user_id),
            ttl,
        )

        # 存储到数据库(持久化)
        if db:
            device_name = None
            device_type = None
            if device_info:
                device_name = device_info.get("name")
                device_type = device_info.get("type")

            db_token = RefreshToken(
                token_hash=token_hash,
                user_id=user_id,
                expires_at=expires_at,
                device_info=json.dumps(device_info) if device_info else None,
                device_name=device_name,
                device_type=device_type,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.add(db_token)
            await db.commit()
            logger.debug(
                f"Refresh Token 已存储: user_id={user_id}, username={username}, device_type={device_type}"
            )

        return token_hash

    @staticmethod
    async def get_refresh_token(
        token_hash: str, redis: Optional[Redis] = None
    ) -> Optional[Dict]:
        """
        获取 Refresh Token 信息

        Args:
            token_hash: Token 哈希值
            redis: Redis 客户端(可选)

        Returns:
            dict: Token 信息，如果不存在则返回 None
        """
        if redis is None:
            redis = await get_redis_client()

        # 检查是否在黑名单中
        blacklisted = await redis.exists(TokenService._get_blacklist_key(token_hash))
        if blacklisted:
            return None

        # 从 Redis 获取
        token_data = await redis.get(TokenService._get_token_key(token_hash))
        if token_data:
            return json.loads(token_data)

        return None

    @staticmethod
    async def revoke_refresh_token(
        token_hash: str,
        redis: Optional[Redis] = None,
        db: Optional[AsyncSession] = None,
    ) -> bool:
        """
        撤销 Refresh Token (加入黑名单)

        Args:
            token_hash: Token 哈希值
            redis: Redis 客户端(可选)
            db: 数据库会话(可选)

        Returns:
            bool: 是否成功撤销
        """
        if redis is None:
            redis = await get_redis_client()

        # 获取 Token 信息以确定过期时间
        token_data = await TokenService.get_refresh_token(token_hash, redis)
        if not token_data:
            return False

        # 计算剩余 TTL
        expires_at = datetime.fromisoformat(token_data["expires_at"])
        ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
        if ttl > 0:
            # 加入黑名单
            await redis.setex(
                TokenService._get_blacklist_key(token_hash),
                ttl,
                "1",
            )

        # 从用户的 Token 集合中移除
        user_id = token_data["user_id"]
        await redis.srem(TokenService._get_user_tokens_key(user_id), token_hash)

        # 从 Redis 中删除 Token
        await redis.delete(TokenService._get_token_key(token_hash))

        # 更新数据库
        if db:
            result = await db.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
            db_token = result.scalar_one_or_none()
            if db_token:
                db_token.revoked = True
                db_token.revoked_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info(
                    f"Refresh Token 已撤销: token_hash={token_hash[:16]}..., user_id={user_id}"
                )

        return True

    @staticmethod
    async def revoke_all_user_tokens(
        user_id: int,
        redis: Optional[Redis] = None,
        db: Optional[AsyncSession] = None,
    ) -> int:
        """
        撤销用户的所有 Refresh Token

        Args:
            user_id: 用户ID
            redis: Redis 客户端(可选)
            db: 数据库会话(可选)

        Returns:
            int: 撤销的 Token 数量
        """
        if redis is None:
            redis = await get_redis_client()

        # 获取用户的所有 Token 哈希
        token_hashes = await redis.smembers(TokenService._get_user_tokens_key(user_id))

        count = 0
        for token_hash in token_hashes:
            # Redis 配置了 decode_responses=True, 所以返回的是字符串, 不需要 decode
            if await TokenService.revoke_refresh_token(token_hash, redis, db):
                count += 1

        # 删除用户的 Token 集合
        await redis.delete(TokenService._get_user_tokens_key(user_id))

        logger.info(f"已撤销用户所有 Token: user_id={user_id}, 撤销数量={count}")
        return count

    @staticmethod
    async def get_user_tokens(
        user_id: int,
        db: AsyncSession,
        include_revoked: bool = False,
    ) -> List[RefreshToken]:
        """
        获取用户的所有 Refresh Token (从数据库)

        Args:
            user_id: 用户ID
            db: 数据库会话
            include_revoked: 是否包含已撤销的 Token

        Returns:
            List[RefreshToken]: Token 列表
        """
        query = select(RefreshToken).where(RefreshToken.user_id == user_id)

        if not include_revoked:
            query = query.where(~RefreshToken.revoked)

        # 只返回未过期的 Token (使用 UTC 时区比较)
        now = datetime.now(timezone.utc)
        query = query.where(RefreshToken.expires_at > now)

        query = query.order_by(RefreshToken.created_at.desc())

        result = await db.execute(query)
        tokens = list(result.scalars().all())

        logger.debug(
            f"查询用户 Token: user_id={user_id}, include_revoked={include_revoked}, "
            f"找到 {len(tokens)} 个有效 Token (当前时间: {now.isoformat()})"
        )

        return tokens

    @staticmethod
    async def cleanup_expired_tokens(db: AsyncSession) -> int:
        """
        清理过期的 Token (数据库)

        Args:
            db: 数据库会话

        Returns:
            int: 清理的 Token 数量
        """
        result = await db.execute(
            select(RefreshToken).where(
                and_(
                    RefreshToken.expires_at < datetime.now(timezone.utc),
                    ~RefreshToken.revoked,
                )
            )
        )
        expired_tokens = result.scalars().all()

        count = 0
        for token in expired_tokens:
            await db.delete(token)
            count += 1

        await db.commit()
        return count
