"""
角色管理路由
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.dependencies.auth import require_superuser
from app.models.permission import Permission
from app.models.role import Role
from app.schemas.role import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleListResponse,
)
from app.utils.cache import clear_role_users_cache

router = APIRouter(prefix="/roles", tags=["角色管理"])


@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_superuser),
):
    """
    创建角色(需要超级用户权限)

    - **name**: 角色名称
    - **description**: 角色描述(可选)
    - **is_super_admin**: 是否为超级管理员角色
    - **permission_ids**: 权限ID列表(可选)
    """
    # 检查角色名称是否已存在
    result = await db.execute(select(Role).where(Role.name == role_data.name))
    if result.scalar_one_or_none() is not None:
        logger.warning(f"创建角色失败: 角色名称已存在 - {role_data.name}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="角色名称已存在"
        )

    # 创建角色
    db_role = Role(
        name=role_data.name,
        description=role_data.description,
        is_super_admin=role_data.is_super_admin,
    )

    # 分配权限
    if role_data.permission_ids:
        result = await db.execute(
            select(Permission).where(Permission.id.in_(role_data.permission_ids))
        )
        permissions = result.scalars().all()
        if len(permissions) != len(role_data.permission_ids):
            logger.warning(
                f"创建角色失败: 部分权限ID不存在 - role_name={role_data.name}, permission_ids={role_data.permission_ids}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="部分权限ID不存在"
            )
        db_role.permissions = permissions

    db.add(db_role)
    await db.commit()
    await db.refresh(db_role)

    # 加载权限关系
    await db.refresh(db_role, ["permissions"])

    logger.info(f"角色创建成功: {db_role.name} (ID: {db_role.id})")
    return db_role


@router.get("/", response_model=List[RoleListResponse])
async def get_roles(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """
    获取角色列表

    - **skip**: 跳过数量
    - **limit**: 返回数量
    """
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions))
        .offset(skip)
        .limit(limit)
        .order_by(Role.created_at)
    )
    roles = result.scalars().all()

    # 转换为响应格式
    role_list = []
    for role in roles:
        role_list.append(
            RoleListResponse(
                id=role.id,
                name=role.name,
                description=role.description,
                is_super_admin=role.is_super_admin,
                permission_count=len(role.permissions),
                created_at=role.created_at.isoformat(),
            )
        )

    return role_list


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    获取角色详情
    """
    result = await db.execute(
        select(Role).where(Role.id == role_id).options(selectinload(Role.permissions))
    )
    role = result.scalar_one_or_none()

    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")

    return role


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    role_data: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_superuser),
):
    """
    更新角色（需要超级用户权限）
    """
    result = await db.execute(
        select(Role)
        .where(Role.id == role_id)
        .options(selectinload(Role.permissions), selectinload(Role.users))
    )
    role = result.scalar_one_or_none()

    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")

    # 更新字段
    if role_data.name is not None:
        # 检查新名称是否已存在
        existing = await db.execute(
            select(Role).where(Role.name == role_data.name, Role.id != role_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="角色名称已存在"
            )
        role.name = role_data.name

    if role_data.description is not None:
        role.description = role_data.description

    if role_data.is_super_admin is not None:
        role.is_super_admin = role_data.is_super_admin

    await db.commit()
    await db.refresh(role, ["permissions"])

    # 清除所有拥有此角色的用户的权限缓存
    try:
        await clear_role_users_cache(role)
        logger.info(
            f"角色已更新: role_id={role_id}, name={role.name}, 已清除相关用户缓存"
        )
    except (RedisError, AttributeError) as e:
        # Redis 错误或关系未加载错误不应该影响角色更新操作
        # 缓存会在下次查询时自动更新
        logger.error(f"清除角色用户缓存失败: role_id={role_id}, error={e}")

    return role


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_superuser),
):
    """
    删除角色（需要超级用户权限）
    """
    result = await db.execute(
        select(Role).where(Role.id == role_id).options(selectinload(Role.users))
    )
    role = result.scalar_one_or_none()

    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")

    # 清除所有拥有此角色的用户的权限缓存
    try:
        await clear_role_users_cache(role)
        logger.info(
            f"角色已删除: role_id={role_id}, name={role.name}, 已清除相关用户缓存"
        )
    except (RedisError, AttributeError) as e:
        # Redis 错误或关系未加载错误不应该影响角色删除操作
        # 缓存会在下次查询时自动更新
        logger.error(f"清除角色用户缓存失败: role_id={role_id}, error={e}")

    await db.delete(role)
    await db.commit()

    return None


@router.post("/{role_id}/permissions/{permission_id}", response_model=RoleResponse)
async def assign_permission_to_role(
    role_id: int,
    permission_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_superuser),
):
    """
    给角色分配权限（需要超级用户权限）
    """
    # 查询角色
    result = await db.execute(
        select(Role)
        .where(Role.id == role_id)
        .options(selectinload(Role.permissions), selectinload(Role.users))
    )
    role = result.scalar_one_or_none()

    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")

    # 查询权限
    result = await db.execute(select(Permission).where(Permission.id == permission_id))
    permission = result.scalar_one_or_none()

    if permission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="权限不存在")

    # 检查是否已分配
    if permission in role.permissions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="权限已分配给该角色"
        )

    # 分配权限
    role.permissions.append(permission)
    await db.commit()
    await db.refresh(role, ["permissions"])

    # 清除所有拥有此角色的用户的权限缓存
    try:
        await clear_role_users_cache(role)
        logger.info(
            f"权限已分配给角色: role_id={role_id}, permission_id={permission_id}, 已清除相关用户缓存"
        )
    except (RedisError, AttributeError) as e:
        # Redis 错误或关系未加载错误不应该影响权限分配操作
        # 缓存会在下次查询时自动更新
        logger.error(f"清除角色用户缓存失败: role_id={role_id}, error={e}")

    return role


@router.delete("/{role_id}/permissions/{permission_id}", response_model=RoleResponse)
async def remove_permission_from_role(
    role_id: int,
    permission_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_superuser),
):
    """
    移除角色的权限（需要超级用户权限）
    """
    # 查询角色
    result = await db.execute(
        select(Role)
        .where(Role.id == role_id)
        .options(selectinload(Role.permissions), selectinload(Role.users))
    )
    role = result.scalar_one_or_none()

    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")

    # 查询权限
    result = await db.execute(select(Permission).where(Permission.id == permission_id))
    permission = result.scalar_one_or_none()

    if permission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="权限不存在")

    # 检查是否已分配
    if permission not in role.permissions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="权限未分配给该角色"
        )

    # 移除权限
    role.permissions.remove(permission)
    await db.commit()
    await db.refresh(role, ["permissions"])

    # 清除所有拥有此角色的用户的权限缓存
    try:
        await clear_role_users_cache(role)
        logger.info(
            f"权限已从角色移除: role_id={role_id}, permission_id={permission_id}, 已清除相关用户缓存"
        )
    except (RedisError, AttributeError) as e:
        # Redis 错误或关系未加载错误不应该影响权限移除操作
        # 缓存会在下次查询时自动更新
        logger.error(f"清除角色用户缓存失败: role_id={role_id}, error={e}")

    return role
