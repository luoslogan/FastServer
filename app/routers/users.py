"""
用户管理路由
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from redis.exceptions import RedisError

from app.core.db import get_db
from app.core.security import verify_password, get_password_hash
from app.core.redis import get_redis_client
from app.models.user import User
from app.models.role import Role
from app.schemas.user import (
    UserResponse,
    UserUpdate,
    UserRoleAssign,
    PasswordChange,
    PasswordChangeResponse,
)
from app.dependencies.auth import get_current_user, require_superuser
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
    # 加载角色关系
    await db.refresh(current_user, ["roles"])

    return current_user


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_superuser),
):
    """
    更新用户信息（需要超级用户权限）
    """
    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.roles))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 更新字段
    if user_data.email is not None:
        # 检查邮箱是否已被其他用户使用
        existing = await db.execute(
            select(User).where(User.email == user_data.email, User.id != user_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被使用"
            )
        user.email = user_data.email

    if user_data.full_name is not None:
        user.full_name = user_data.full_name

    # 记录 is_active 的旧值，用于判断是否需要清除缓存
    old_is_active = user.is_active

    if user_data.is_active is not None:
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
        except RedisError:
            # Redis 错误不应该影响用户更新操作，只记录日志
            # 缓存会在下次查询时自动更新
            pass

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
    # 验证旧密码
    if not verify_password(password_data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="旧密码错误"
        )

    # 更新密码
    current_user.hashed_password = get_password_hash(password_data.new_password)
    await db.commit()

    # 撤销所有 Refresh Token
    redis = await get_redis_client()
    try:
        revoked_count = await TokenService.revoke_all_user_tokens(
            current_user.id, redis, db
        )
    except RedisError:
        # Redis 错误不应该影响密码修改操作
        pass

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 查询角色
    result = await db.execute(select(Role).where(Role.id.in_(role_data.role_ids)))
    roles = result.scalars().all()

    if len(roles) != len(role_data.role_ids):
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
    except RedisError:
        # Redis 错误不应该影响角色分配操作，只记录日志
        # 缓存会在下次查询时自动更新
        pass

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
    except RedisError:
        # Redis 错误不应该影响角色移除操作，只记录日志
        # 缓存会在下次查询时自动更新
        pass

    return user
