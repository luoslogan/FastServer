"""
权限数据库模型
"""

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db import Base


class Permission(Base):
    """权限模型"""

    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False, comment="权限名称，格式: 资源:操作")
    resource = Column(String(50), nullable=False, index=True, comment="资源名称，如 users, posts")
    action = Column(String(50), nullable=False, comment="操作名称，如 read, write, delete")
    description = Column(Text, nullable=True, comment="权限描述")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now, nullable=False
    )

    # 关系：角色-权限（多对多）
    roles = relationship(
        "Role", secondary="role_permissions", back_populates="permissions"
    )

    def __repr__(self):
        return f"<Permission(id={self.id}, name={self.name})>"

