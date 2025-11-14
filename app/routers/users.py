"""
用户管理路由
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.core.redis import get_redis_client
from app.core.security import verify_password, get_password_hash
from app.dependencies.auth import get_current_user, require_superuser
from app.dependencies.permissions import require_permission
from app.models.role import Role
from app.models.user import User
from app.schemas.user import (
    UserResponse,
    UserUpdate,
    UserRoleAssign,
    PasswordChange,
    PasswordChangeResponse,
)
from app.utils.cache import clear_user_cache
from app.utils.token import TokenService

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前登录用户信息
    """
    # 从当前数据库会话中重新查询用户, 确保对象属于当前会话
    # 因为 current_user 可能来自全局中间件的缓存, 不在当前 db 会话中
    result = await db.execute(
        select(User).where(User.id == current_user.id).options(selectinload(User.roles))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    return user


@router.get("/", response_model=List[UserResponse])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_superuser),
):
    """
    获取用户列表(需要超级用户权限)

    - **skip**: 跳过数量
    - **limit**: 返回数量
    """
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles))
        .offset(skip)
        .limit(limit)
        .order_by(User.created_at)
    )
    users = result.scalars().all()

    return list(users)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_superuser),
):
    """
    获取用户详情（需要超级用户权限）
    """
    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.roles))
    )
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning(f"获取用户详情失败: 用户不存在 - user_id={user_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    logger.debug(f"获取用户详情: user_id={user_id}")
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users:manage")),
):
    """
    更新用户信息（需要 users:manage 权限）

    允许的操作：
    - 超级用户（is_superuser=True）可以更新任意用户
    - 拥有 users:manage 权限的角色（如 admin）可以更新普通用户

    限制：
    - 非超级用户不能更新超级用户（is_superuser=True）
    - 非超级用户不能更新拥有 super_admin 角色的用户
    """
    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.roles))
    )
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning(f"更新用户失败: 用户不存在 - user_id={user_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 权限检查：非超级用户不能更新超级用户
    if not current_user.is_superuser and user.is_superuser:
        logger.warning(
            f"更新用户失败: 非超级用户尝试更新超级用户 - "
            f"current_user_id={current_user.id}, target_user_id={user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权更新超级用户",
        )

    # 权限检查：非超级用户不能更新拥有 super_admin 角色的用户
    if not current_user.is_superuser:
        from app.dependencies.permissions import get_user_roles

        target_roles = await get_user_roles(user, db)
        has_super_admin_role = any(role.is_super_admin for role in target_roles)

        if has_super_admin_role:
            logger.warning(
                f"更新用户失败: 非超级用户尝试更新超级管理员角色用户 - "
                f"current_user_id={current_user.id}, target_user_id={user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权更新超级管理员角色用户",
            )

    # 更新字段
    if user_data.email is not None:
        # 检查邮箱是否已被其他用户使用
        existing = await db.execute(
            select(User).where(User.email == user_data.email, User.id != user_id)
        )
        if existing.scalar_one_or_none() is not None:
            logger.warning(
                f"更新用户失败: 邮箱已被使用 - user_id={user_id}, email={user_data.email}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被使用"
            )
        user.email = user_data.email

    if user_data.full_name is not None:
        user.full_name = user_data.full_name

    # 记录 is_active 的旧值，用于判断是否需要清除缓存
    old_is_active = user.is_active

    if user_data.is_active is not None:
        # 检查是否尝试拉黑超级用户或超级管理员（非超级用户不能这样做）
        if not user_data.is_active and not current_user.is_superuser:
            if user.is_superuser:
                logger.warning(
                    f"拉黑用户失败: 非超级用户尝试拉黑超级用户 - "
                    f"current_user_id={current_user.id}, target_user_id={user_id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权拉黑超级用户",
                )

            # 检查是否拥有 super_admin 角色
            from app.dependencies.permissions import get_user_roles

            target_roles = await get_user_roles(user, db)
            has_super_admin_role = any(role.is_super_admin for role in target_roles)

            if has_super_admin_role:
                logger.warning(
                    f"拉黑用户失败: 非超级用户尝试拉黑超级管理员角色用户 - "
                    f"current_user_id={current_user.id}, target_user_id={user_id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权拉黑超级管理员角色用户",
                )

        user.is_active = user_data.is_active

    await db.commit()
    await db.refresh(user, ["roles"])

    # 如果 is_active 状态变化了，清除权限缓存
    # 注意：虽然 request.state.userinfo 会在下次请求时自动更新，
    # 但清除 Redis 缓存可以确保权限检查立即生效
    # 当用户被禁用时，应该立即无法访问，不需要等待缓存过期
    if user_data.is_active is not None and old_is_active != user.is_active:
        try:
            await clear_user_cache(user_id)
            logger.info(
                f"用户状态变更: user_id={user_id}, is_active={user.is_active}, 已清除缓存"
            )
        except RedisError as e:
            # Redis 错误不应该影响用户更新操作，只记录日志
            # 缓存会在下次查询时自动更新
            logger.error(f"清除用户缓存失败: user_id={user_id}, error={e}")

    logger.info(f"用户信息已更新: user_id={user_id}, username={user.username}")
    return user


@router.post("/me/change-password", response_model=PasswordChangeResponse)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    修改当前用户密码

    修改密码后, 会撤销所有 Refresh Token, 用户需要重新登录
    """
    # 从当前数据库会话中重新查询用户, 确保使用正确的会话
    # 因为 current_user 可能来自全局中间件的缓存, 不在当前 db 会话中
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()

    if user is None:
        logger.error(f"修改密码失败: 用户不存在 - user_id={current_user.id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 验证旧密码
    if not verify_password(password_data.old_password, user.hashed_password):
        logger.warning(
            f"修改密码失败: 旧密码错误 - user_id={user.id}, username={user.username}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="旧密码错误"
        )

    # 更新密码
    new_hashed_password = get_password_hash(password_data.new_password)
    user.hashed_password = new_hashed_password

    # 先提交密码修改, 确保密码已经保存到数据库
    await db.commit()
    await db.refresh(user)  # 刷新用户对象, 确保数据已更新

    # 验证新密码是否正确保存 (调试用)
    verify_result = verify_password(password_data.new_password, user.hashed_password)
    logger.info(
        f"密码修改验证: user_id={user.id}, username={user.username}, "
        f"新密码验证结果={verify_result}, hashed_password前10位={user.hashed_password[:10]}..."
    )

    if not verify_result:
        logger.error(f"密码修改后验证失败: user_id={user.id}, username={user.username}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="密码修改失败, 请重试",
        )

    # 撤销所有 Refresh Token (不传入 db, 避免事务冲突)
    # 这样即使撤销 Token 失败, 也不会影响密码修改
    redis = await get_redis_client()
    try:
        revoked_count = await TokenService.revoke_all_user_tokens(
            current_user.id,
            redis,
            db=None,  # 不传入 db, 避免事务冲突
        )
        logger.info(
            f"已撤销用户所有 Token: user_id={current_user.id}, 撤销数量={revoked_count}"
        )
    except RedisError as e:
        # Redis 错误不应该影响密码修改操作
        logger.error(f"撤销 Token 失败: user_id={current_user.id}, error={e}")

    return PasswordChangeResponse(message="密码修改成功, 请重新登录")


@router.post("/{user_id}/roles", response_model=UserResponse)
async def assign_roles_to_user(
    user_id: int,
    role_data: UserRoleAssign,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_superuser),
):
    """
    给用户分配角色（需要超级用户权限）

    - **role_ids**: 角色ID列表
    """
    # 查询用户
    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.roles))
    )
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning(f"分配角色失败: 用户不存在 - user_id={user_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 查询角色
    result = await db.execute(select(Role).where(Role.id.in_(role_data.role_ids)))
    roles = result.scalars().all()

    if len(roles) != len(role_data.role_ids):
        logger.warning(
            f"分配角色失败: 部分角色ID不存在 - user_id={user_id}, role_ids={role_data.role_ids}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="部分角色ID不存在"
        )

    # 分配角色（替换现有角色）
    user.roles = roles
    await db.commit()
    await db.refresh(user, ["roles"])

    # 清除用户权限缓存
    try:
        await clear_user_cache(user_id)
        logger.info(
            f"用户角色已分配: user_id={user_id}, role_ids={role_data.role_ids}, 已清除缓存"
        )
    except RedisError as e:
        # Redis 错误不应该影响角色分配操作，只记录日志
        # 缓存会在下次查询时自动更新
        logger.error(f"清除用户缓存失败: user_id={user_id}, error={e}")

    return user


@router.delete("/{user_id}/roles/{role_id}", response_model=UserResponse)
async def remove_role_from_user(
    user_id: int,
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_superuser),
):
    """
    移除用户的角色（需要超级用户权限）
    """
    # 查询用户
    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.roles))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 查询角色
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()

    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")

    # 检查用户是否拥有该角色
    if role not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户未拥有该角色"
        )

    # 移除角色
    user.roles.remove(role)
    await db.commit()
    await db.refresh(user, ["roles"])

    # 清除用户权限缓存
    try:
        await clear_user_cache(user_id)
        logger.info(f"用户角色已移除: user_id={user_id}, role_id={role_id}, 已清除缓存")
    except RedisError as e:
        # Redis 错误不应该影响角色移除操作，只记录日志
        # 缓存会在下次查询时自动更新
        logger.error(f"清除用户缓存失败: user_id={user_id}, error={e}")

    return user
