"""
认证相关的 Pydantic 模型
"""

from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    """Token 响应模型"""

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None  # Access Token 过期时间(秒)


class TokenData(BaseModel):
    """Token 数据模型"""

    username: Optional[str] = None


class UserLogin(BaseModel):
    """用户登录请求模型"""

    username: str = Field(..., min_length=3, max_length=50, description="用户名或邮箱")
    password: str = Field(..., min_length=6, description="密码")


class UserRegister(BaseModel):
    """用户注册请求模型"""

    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, description="密码")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")


class UserResponse(BaseModel):
    """用户响应模型"""

    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_superuser: bool
    created_at: str

    class Config:
        from_attributes = True


class TokenRefresh(BaseModel):
    """刷新 Token 请求模型"""

    refresh_token: Optional[str] = Field(
        None, description="Refresh Token (可选, 可从 Cookie 获取)"
    )


class TokenRefreshResponse(BaseModel):
    """刷新 Token 响应模型"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Access Token 过期时间(秒)


class RefreshTokenInfo(BaseModel):
    """Refresh Token 信息模型"""

    id: int
    device_name: Optional[str]
    device_type: Optional[str]
    ip_address: Optional[str]
    created_at: str
    expires_at: str
    revoked: bool

    class Config:
        from_attributes = True


class LogoutResponse(BaseModel):
    """登出响应模型"""

    message: str = "登出成功"


class DeviceListResponse(BaseModel):
    """设备列表响应模型"""

    devices: List[RefreshTokenInfo]
    total: int


class RevokeDeviceResponse(BaseModel):
    """撤销设备响应模型"""

    message: str = "设备已撤销"
