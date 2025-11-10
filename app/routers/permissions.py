"""
权限管理路由
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.db import get_db
from app.models.permission import Permission
from app.schemas.permission import PermissionCreate, PermissionUpdate, PermissionResponse
from app.dependencies.auth import require_superuser

router = APIRouter(prefix="/permissions", tags=["权限管理"])


@router.post(
    "/", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED
)
async def create_permission(
    permission_data: PermissionCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_superuser),
):
    """
    创建权限（需要超级用户权限）

    - **name**: 权限名称，格式: 资源:操作（如 "users:read"）
    - **resource**: 资源名称（如 "users", "posts"）
    - **action**: 操作名称（如 "read", "write", "delete"）
    - **description**: 权限描述（可选）
    """
    # 检查权限名称是否已存在
    result = await db.execute(
        select(Permission).where(Permission.name == permission_data.name)
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="权限名称已存在"
        )

    # 创建权限
    db_permission = Permission(
        name=permission_data.name,
        resource=permission_data.resource,
        action=permission_data.action,
        description=permission_data.description,
    )

    db.add(db_permission)
    await db.commit()
    await db.refresh(db_permission)

    return db_permission


@router.get("/", response_model=List[PermissionResponse])
async def get_permissions(
    skip: int = 0,
    limit: int = 100,
    resource: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    获取权限列表

    - **skip**: 跳过数量
    - **limit**: 返回数量
    - **resource**: 按资源过滤（可选）
    """
    query = select(Permission)

    if resource:
        query = query.where(Permission.resource == resource)

    query = query.offset(skip).limit(limit).order_by(Permission.resource, Permission.action)

    result = await db.execute(query)
    permissions = result.scalars().all()

    return list(permissions)


@router.get("/{permission_id}", response_model=PermissionResponse)
async def get_permission(
    permission_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    获取权限详情
    """
    result = await db.execute(
        select(Permission).where(Permission.id == permission_id)
    )
    permission = result.scalar_one_or_none()

    if permission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="权限不存在"
        )

    return permission


@router.put("/{permission_id}", response_model=PermissionResponse)
async def update_permission(
    permission_id: int,
    permission_data: PermissionUpdate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_superuser),
):
    """
    更新权限（需要超级用户权限）
    """
    result = await db.execute(
        select(Permission).where(Permission.id == permission_id)
    )
    permission = result.scalar_one_or_none()

    if permission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="权限不存在"
        )

    # 更新字段
    if permission_data.resource is not None:
        permission.resource = permission_data.resource
    if permission_data.action is not None:
        permission.action = permission_data.action
    if permission_data.description is not None:
        permission.description = permission_data.description

    # 如果资源或操作改变，更新权限名称
    if permission_data.resource is not None or permission_data.action is not None:
        new_name = f"{permission.resource}:{permission.action}"
        # 检查新名称是否已存在
        existing = await db.execute(
            select(Permission).where(
                Permission.name == new_name, Permission.id != permission_id
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"权限名称 '{new_name}' 已存在",
            )
        permission.name = new_name

    await db.commit()
    await db.refresh(permission)

    return permission


@router.delete("/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_permission(
    permission_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_superuser),
):
    """
    删除权限（需要超级用户权限）
    """
    result = await db.execute(
        select(Permission).where(Permission.id == permission_id)
    )
    permission = result.scalar_one_or_none()

    if permission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="权限不存在"
        )

    await db.delete(permission)
    await db.commit()

    return None

