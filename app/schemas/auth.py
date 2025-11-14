"""
认证相关的 Pydantic 模型
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field

from app.schemas.base import BaseResponseModel


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


class UserResponse(BaseResponseModel):
    """用户响应模型"""

    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_superuser: bool
    created_at: datetime


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


class RefreshTokenInfo(BaseResponseModel):
    """Refresh Token 信息模型"""

    id: int
    device_name: Optional[str]
    device_type: Optional[str]
    ip_address: Optional[str]
    created_at: datetime
    expires_at: datetime
    revoked: bool


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


class EmailVerificationRequest(BaseModel):
    """邮箱验证请求模型"""

    token: str = Field(..., description="验证 Token")


class EmailVerificationResponse(BaseModel):
    """邮箱验证响应模型"""

    message: str = "邮箱验证成功"


class ResendVerificationEmailResponse(BaseModel):
    """重新发送验证邮件响应模型"""

    message: str = "验证邮件已发送"


class ForgotPasswordRequest(BaseModel):
    """忘记密码请求模型"""

    email: EmailStr = Field(..., description="邮箱地址")


class ForgotPasswordResponse(BaseModel):
    """忘记密码响应模型"""

    message: str = "密码重置邮件已发送，请查收邮箱"


class ResetPasswordRequest(BaseModel):
    """重置密码请求模型"""

    token: str = Field(..., description="重置 Token")
    new_password: str = Field(..., min_length=6, description="新密码")


class ResetPasswordResponse(BaseModel):
    """重置密码响应模型"""

    message: str = "密码重置成功，请使用新密码登录"


class TestEmailRequest(BaseModel):
    """测试邮件请求模型"""

    to_email: EmailStr = Field(..., description="收件人邮箱地址")
    subject: str = Field(default="测试邮件", description="邮件主题")
    content: str = Field(default="这是一封测试邮件", description="邮件内容")


class TestEmailResponse(BaseModel):
    """测试邮件响应模型"""

    success: bool
    message: str
    smtp_config_status: dict = Field(
        default_factory=dict, description="SMTP 配置状态（不包含敏感信息）"
    )
