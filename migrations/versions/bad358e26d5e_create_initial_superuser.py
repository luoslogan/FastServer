"""Create initial superuser

Revision ID: bad358e26d5e
Revises: 5392d8862baa
Create Date: 2025-11-11 19:14:05.663911

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from passlib.context import CryptContext

# revision identifiers, used by Alembic.
revision: str = "bad358e26d5e"
down_revision: Union[str, Sequence[str], None] = "5392d8862baa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 超级用户配置（硬编码在迁移文件中）
SUPERUSER_USERNAME = "admin"
SUPERUSER_EMAIL = "admin@example.com"
SUPERUSER_PASSWORD = "password123"

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def upgrade() -> None:
    """创建初始超级用户"""
    connection = op.get_bind()

    # 生成密码哈希
    hashed_password = pwd_context.hash(SUPERUSER_PASSWORD)

    # 检查用户是否已存在
    result = connection.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": SUPERUSER_USERNAME},
    )
    existing_user = result.fetchone()

    if existing_user:
        # 如果用户已存在，更新为超级用户
        connection.execute(
            text("""
                UPDATE users 
                SET email = :email,
                    hashed_password = :hashed_password,
                    is_active = TRUE,
                    is_superuser = TRUE
                WHERE username = :username
            """),
            {
                "username": SUPERUSER_USERNAME,
                "email": SUPERUSER_EMAIL,
                "hashed_password": hashed_password,
            },
        )
    else:
        # 创建新超级用户
        connection.execute(
            text("""
                INSERT INTO users (username, email, hashed_password, is_active, is_superuser)
                VALUES (:username, :email, :hashed_password, TRUE, TRUE)
            """),
            {
                "username": SUPERUSER_USERNAME,
                "email": SUPERUSER_EMAIL,
                "hashed_password": hashed_password,
            },
        )

    connection.commit()


def downgrade() -> None:
    """删除初始超级用户"""
    connection = op.get_bind()

    connection.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": SUPERUSER_USERNAME},
    )

    connection.commit()
