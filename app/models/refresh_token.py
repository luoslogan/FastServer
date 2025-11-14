"""
Refresh Token 数据库模型
用于存储 Refresh Token 信息、设备信息、登录历史等
"""

from sqlalchemy import Boolean, Column, Integer, String, DateTime, Text, ForeignKey, text
from sqlalchemy.orm import relationship

from app.core.db import Base


class RefreshToken(Base):
    """Refresh Token 模型"""

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"), comment="创建时间"
    )
    revoked = Column(Boolean, default=False, nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # 设备信息
    device_info = Column(Text, nullable=True)  # JSON 格式存储设备信息
    device_name = Column(String(100), nullable=True)  # 设备名称
    device_type = Column(String(50), nullable=True)  # 设备类型: web, mobile, desktop
    ip_address = Column(String(45), nullable=True)  # IP 地址 (支持 IPv6)
    user_agent = Column(String(500), nullable=True)  # User-Agent

    # 关系
    user = relationship("User", backref="refresh_tokens")

    def __repr__(self):
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, revoked={self.revoked})>"
