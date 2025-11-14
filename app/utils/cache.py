"""
缓存管理工具

提供统一的缓存清除接口, 确保用户信息, 角色, 权限变化时能及时更新缓存.
"""

from typing import Optional

from loguru import logger
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.redis import get_redis_client
from app.dependencies.permissions import clear_user_permissions_cache


async def clear_user_cache(user_id: int, redis: Optional[Redis] = None):
    """
    清除用户相关的所有缓存

    包括:
    - 用户权限缓存 (user_permissions:{user_id})
    - 其他用户相关缓存(如果有)

    Args:
        user_id: 用户ID
        redis: Redis 客户端(可选, 如果不提供会自动获取)

    使用场景:
    - 用户信息更新(邮箱, 密码等)
    - 用户角色变化
    - 用户被禁用/启用
    """
    if redis is None:
        redis = await get_redis_client()

    try:
        # 清除权限缓存
        await clear_user_permissions_cache(user_id, redis)
        logger.debug(f"用户缓存已清除: user_id={user_id}")
    except RedisError as e:
        logger.error(f"清除用户缓存失败: user_id={user_id}, error={e}")
        raise

    # 可以在这里添加其他用户相关缓存的清除逻辑
    # 例如: 用户信息缓存, 用户会话缓存等


async def clear_role_users_cache(role, redis: Optional[Redis] = None):
    """
    清除拥有指定角色的所有用户的缓存

    当角色信息或权限变化时, 需要清除所有拥有该角色的用户的缓存.

    Args:
        role: Role 对象(必须包含 users 关系, 使用 selectinload 加载)
        redis: Redis 客户端(可选, 如果不提供会自动获取)

    使用场景:
    - 角色权限变化
    - 角色信息更新(is_super_admin 等)
    - 角色被删除

    使用示例:
        from sqlalchemy.orm import selectinload

        # 查询角色时加载 users 关系
        result = await db.execute(
            select(Role)
            .where(Role.id == role_id)
            .options(selectinload(Role.users))
        )
        role = result.scalar_one_or_none()

        # 清除所有拥有此角色的用户的缓存
        await clear_role_users_cache(role)

    Raises:
        AttributeError: 如果 role 对象没有 users 属性或 users 关系未加载
    """
    if redis is None:
        redis = await get_redis_client()

    # 检查 role 对象是否有 users 属性
    if not hasattr(role, "users"):
        raise AttributeError(
            "Role 对象缺少 users 属性. 请确保使用 selectinload(Role.users) 加载关系."
        )

    # 如果角色没有用户, 直接返回
    if not role.users:
        return

    # 清除所有拥有此角色的用户的权限缓存
    user_count = len(role.users)
    logger.debug(f"开始清除角色相关用户缓存: role_id={role.id}, role_name={role.name}, 用户数量={user_count}")
    for user in role.users:
        try:
            await clear_user_permissions_cache(user.id, redis)
        except RedisError as e:
            logger.error(f"清除用户缓存失败: user_id={user.id}, role_id={role.id}, error={e}")

