"""
用户相关的 Pydantic 模型（扩展）
"""

from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field

from app.schemas.role import RoleListResponse


class UserBase(BaseModel):
    """用户基础模型"""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)


class UserUpdate(BaseModel):
    """更新用户请求模型"""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    """用户响应模型"""

    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_superuser: bool
    roles: List[RoleListResponse] = []
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class UserRoleAssign(BaseModel):
    """分配用户角色请求模型"""

    role_ids: List[int] = Field(..., description="角色ID列表")


class PasswordChange(BaseModel):
    """修改密码请求模型"""

    old_password: str = Field(..., min_length=6, description="旧密码")
    new_password: str = Field(..., min_length=6, description="新密码")


class PasswordChangeResponse(BaseModel):
    """修改密码响应模型"""

    message: str = "密码修改成功"
