"""
角色相关的 Pydantic 模型
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.base import BaseResponseModel


class PermissionResponse(BaseModel):
    """权限响应模型"""

    id: int
    name: str
    resource: str
    action: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class RoleBase(BaseModel):
    """角色基础模型"""

    name: str = Field(..., min_length=2, max_length=50, description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    is_super_admin: bool = Field(default=False, description="是否为超级管理员角色")


class RoleCreate(RoleBase):
    """创建角色请求模型"""

    permission_ids: Optional[List[int]] = Field(default=[], description="权限ID列表")


class RoleUpdate(BaseModel):
    """更新角色请求模型"""

    name: Optional[str] = Field(
        None, min_length=2, max_length=50, description="角色名称"
    )
    description: Optional[str] = Field(None, description="角色描述")
    is_super_admin: Optional[bool] = Field(None, description="是否为超级管理员角色")


class RoleResponse(BaseResponseModel, RoleBase):
    """角色响应模型"""

    id: int
    permissions: List[PermissionResponse] = []
    created_at: datetime
    updated_at: datetime


class RoleListResponse(BaseResponseModel):
    """角色列表响应模型"""

    id: int
    name: str
    description: Optional[str] = None
    is_super_admin: bool
    permission_count: int = 0
    created_at: datetime
