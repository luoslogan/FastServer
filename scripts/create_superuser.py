"""
创建超级用户脚本

使用方法:
    python scripts/create_superuser.py <username> <email> <password>

示例:
    python scripts/create_superuser.py admin admin@example.com password123
"""

import asyncio
import sys
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.user import User


async def create_superuser(username: str, email: str, password: str):
    """
    创建或升级超级用户

    Args:
        username: 用户名
        email: 邮箱
        password: 密码
    """
    async with AsyncSessionLocal() as db:
        # 检查用户是否已存在
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if user:
            # 如果用户存在，升级为超级用户
            user.is_superuser = True
            if user.email != email:
                user.email = email
            # 如果提供了新密码，更新密码
            if password:
                user.hashed_password = get_password_hash(password)
            await db.commit()
            await db.refresh(user)
            print(f"✅ 用户 '{username}' 已升级为超级用户")
            print(f"   ID: {user.id}")
            print(f"   邮箱: {user.email}")
            print(f"   是否激活: {user.is_active}")
            print(f"   是否超级用户: {user.is_superuser}")
        else:
            # 如果用户不存在，创建新的超级用户
            hashed_password = get_password_hash(password)
            user = User(
                username=username,
                email=email,
                hashed_password=hashed_password,
                is_active=True,
                is_superuser=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            print(f"✅ 成功创建超级用户 '{username}'")
            print(f"   ID: {user.id}")
            print(f"   用户名: {user.username}")
            print(f"   邮箱: {user.email}")
            print(f"   是否激活: {user.is_active}")
            print(f"   是否超级用户: {user.is_superuser}")


async def main():
    """主函数"""
    if len(sys.argv) < 4:
        print("❌ 参数不足")
        print("\n使用方法:")
        print("  python scripts/create_superuser.py <username> <email> <password>")
        print("\n示例:")
        print(
            "  python scripts/create_superuser.py admin admin@example.com password123"
        )
        sys.exit(1)

    username = sys.argv[1]
    email = sys.argv[2]
    password = sys.argv[3]

    # 验证输入
    if len(username) < 3:
        print("❌ 用户名至少需要3个字符")
        sys.exit(1)

    if len(password) < 6:
        print("❌ 密码至少需要6个字符")
        sys.exit(1)

    if "@" not in email:
        print("❌ 邮箱格式不正确")
        sys.exit(1)

    try:
        await create_superuser(username, email, password)
    except Exception as e:
        print(f"❌ 创建超级用户失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
