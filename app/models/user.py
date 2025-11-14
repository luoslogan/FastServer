"""
用户数据库模型
"""

from sqlalchemy import Boolean, Column, Integer, String, DateTime, text
from sqlalchemy.orm import relationship

from app.core.db import Base


class User(Base):
    """用户模型"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    email_verified = Column(
        Boolean, default=False, nullable=False, comment="邮箱是否已验证"
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
    roles = relationship("Role", secondary="user_roles", back_populates="users")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"
