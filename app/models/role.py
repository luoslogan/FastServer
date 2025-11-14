"""
角色数据库模型
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, text
from sqlalchemy.orm import relationship

from app.core.db import Base


class Role(Base):
    """角色模型"""

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(
        String(50), unique=True, index=True, nullable=False, comment="角色名称"
    )
    description = Column(Text, nullable=True, comment="角色描述")
    is_super_admin = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否为超级管理员角色（拥有所有权限）",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        comment="创建时间",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        comment="更新时间",
    )

    # 关系：用户-角色（多对多）
    users = relationship("User", secondary="user_roles", back_populates="roles")

    # 关系：角色-权限（多对多）
    permissions = relationship(
        "Permission", secondary="role_permissions", back_populates="roles"
    )

    def __repr__(self):
        return f"<Role(id={self.id}, name={self.name})>"
