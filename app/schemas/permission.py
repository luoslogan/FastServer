"""
权限相关的 Pydantic 模型
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.base import BaseResponseModel


class PermissionBase(BaseModel):
    """权限基础模型"""

    name: str = Field(
        ..., min_length=3, max_length=100, description="权限名称，格式: 资源:操作"
    )
    resource: str = Field(..., min_length=1, max_length=50, description="资源名称")
    action: str = Field(..., min_length=1, max_length=50, description="操作名称")
    description: Optional[str] = Field(None, description="权限描述")


class PermissionCreate(PermissionBase):
    """创建权限请求模型"""

    ...


class PermissionUpdate(BaseModel):
    """更新权限请求模型"""

    resource: Optional[str] = Field(
        None, min_length=1, max_length=50, description="资源名称"
    )
    action: Optional[str] = Field(
        None, min_length=1, max_length=50, description="操作名称"
    )
    description: Optional[str] = Field(None, description="权限描述")


class PermissionResponse(BaseResponseModel, PermissionBase):
    """权限响应模型"""

    id: int
    created_at: datetime
