"""
权限检查相关的依赖注入
"""

import json
from typing import List, Set
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.db import get_db
from app.models.user import User
from app.models.role import Role
from app.dependencies.auth import get_current_user
from app.core.redis import get_redis_client


async def get_user_roles(
    user: User,
    db: AsyncSession,
) -> List[Role]:
    """
    获取用户的所有角色

    Args:
        user: 用户对象
        db: 数据库会话

    Returns:
        List[Role]: 角色列表
    """
    # 如果用户是超级用户，返回空列表（超级用户不需要角色）
    if user.is_superuser:
        return []

    result = await db.execute(
        select(Role)
        .join(Role.users)
        .where(User.id == user.id)
        .options(selectinload(Role.permissions))
    )
    return list(result.scalars().all())


async def get_user_permissions(
    user: User,
    db: AsyncSession,
    redis: Redis,
) -> Set[str]:
    """
    获取用户的所有权限（通过角色）

    Args:
        user: 用户对象
        db: 数据库会话
        redis: Redis 客户端（可选，用于缓存）

    Returns:
        Set[str]: 权限名称集合
    """
    # 超级用户或超级管理员角色拥有所有权限
    if user.is_superuser:
        return {"*"}  # 使用 "*" 表示所有权限

    # 尝试从 Redis 缓存获取
    cache_key = f"user_permissions:{user.id}"
    try:
        cached = await redis.get(cache_key)
        if cached:
            return set(json.loads(cached))
    except Exception:
        pass  # 缓存失败，继续从数据库查询

    # 从数据库查询
    roles = await get_user_roles(user, db)

    # 检查是否有超级管理员角色
    for role in roles:
        if role.is_super_admin:
            permissions = {"*"}
            # 缓存结果
            try:
                await redis.setex(
                    cache_key, 3600, json.dumps(list(permissions))
                )  # 缓存1小时
            except Exception:
                pass
            return permissions

    # 收集所有权限
    permission_names = set()
    for role in roles:
        for permission in role.permissions:
            permission_names.add(permission.name)

    # 缓存结果
    try:
        await redis.setex(
            cache_key, 3600, json.dumps(list(permission_names))
        )  # 缓存1小时
    except Exception:
        pass

    return permission_names


def require_permission(permission_name: str):
    """
    要求特定权限的依赖注入函数

    Args:
        permission_name: 权限名称，如 "users:read"

    Returns:
        依赖函数
    """

    async def _check_permission(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        """
        检查用户是否有指定权限

        Args:
            current_user: 当前用户
            db: 数据库会话

        Returns:
            User: 当前用户

        Raises:
            HTTPException: 没有权限
        """

        # 超级用户自动拥有所有权限
        if current_user.is_superuser:
            return current_user

        # 获取 Redis 客户端
        redis = await get_redis_client()

        # 获取用户权限
        permissions = await get_user_permissions(current_user, db, redis)

        # 检查是否有 "*"（所有权限）或指定权限
        if "*" in permissions or permission_name in permissions:
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"需要权限: {permission_name}",
        )

    return _check_permission


def require_role(role_name: str):
    """
    要求特定角色的依赖注入函数

    Args:
        role_name: 角色名称

    Returns:
        依赖函数
    """

    async def _check_role(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        """
        检查用户是否有指定角色

        Args:
            current_user: 当前用户
            db: 数据库会话

        Returns:
            User: 当前用户

        Raises:
            HTTPException: 没有角色
        """
        # 超级用户自动拥有所有角色
        if current_user.is_superuser:
            return current_user

        # 获取用户角色
        roles = await get_user_roles(current_user, db)
        role_names = {role.name for role in roles}

        if role_name in role_names:
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"需要角色: {role_name}",
        )

    return _check_role


async def clear_user_permissions_cache(user_id: int, redis: Redis):
    """
    清除用户权限缓存

    Args:
        user_id: 用户ID
        redis: Redis 客户端

    Raises:
        redis.exceptions.RedisError: Redis 操作失败时抛出异常
    """
    cache_key = f"user_permissions:{user_id}"
    try:
        await redis.delete(cache_key)
    except RedisError as e:
        # Redis 错误应该被记录或重新抛出, 而不是静默失败
        # 这里重新抛出异常, 让调用者决定如何处理
        raise RedisError(f"清除用户权限缓存失败 (user_id={user_id}): {e}") from e
