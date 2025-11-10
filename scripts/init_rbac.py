"""
初始化 RBAC 系统
创建默认角色和权限
"""

import asyncio
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.role import Role
from app.models.permission import Permission


# 默认权限定义（参考大厂实现）
DEFAULT_PERMISSIONS = [
    # 用户管理权限
    {"name": "users:read", "resource": "users", "action": "read", "description": "查看用户"},
    {"name": "users:write", "resource": "users", "action": "write", "description": "创建/编辑用户"},
    {"name": "users:delete", "resource": "users", "action": "delete", "description": "删除用户"},
    {"name": "users:manage", "resource": "users", "action": "manage", "description": "管理用户（包含所有用户操作）"},
    
    # 角色管理权限
    {"name": "roles:read", "resource": "roles", "action": "read", "description": "查看角色"},
    {"name": "roles:write", "resource": "roles", "action": "write", "description": "创建/编辑角色"},
    {"name": "roles:delete", "resource": "roles", "action": "delete", "description": "删除角色"},
    {"name": "roles:manage", "resource": "roles", "action": "manage", "description": "管理角色（包含所有角色操作）"},
    
    # 权限管理权限
    {"name": "permissions:read", "resource": "permissions", "action": "read", "description": "查看权限"},
    {"name": "permissions:write", "resource": "permissions", "action": "write", "description": "创建/编辑权限"},
    {"name": "permissions:delete", "resource": "permissions", "action": "delete", "description": "删除权限"},
    {"name": "permissions:manage", "resource": "permissions", "action": "manage", "description": "管理权限（包含所有权限操作）"},
    
    # 内容管理权限（示例）
    {"name": "content:read", "resource": "content", "action": "read", "description": "查看内容"},
    {"name": "content:write", "resource": "content", "action": "write", "description": "创建/编辑内容"},
    {"name": "content:delete", "resource": "content", "action": "delete", "description": "删除内容"},
    {"name": "content:manage", "resource": "content", "action": "manage", "description": "管理内容（包含所有内容操作）"},
    
    # 系统管理权限
    {"name": "system:read", "resource": "system", "action": "read", "description": "查看系统信息"},
    {"name": "system:write", "resource": "system", "action": "write", "description": "修改系统配置"},
    {"name": "system:manage", "resource": "system", "action": "manage", "description": "管理系统（包含所有系统操作）"},
]

# 默认角色定义
DEFAULT_ROLES = [
    {
        "name": "super_admin",
        "description": "超级管理员（拥有所有权限，通过 is_super_admin 标志控制）",
        "is_super_admin": True,
        "permissions": [],  # 超级管理员角色不需要分配权限，通过 is_super_admin 标志自动拥有所有权限
    },
    {
        "name": "admin",
        "description": "管理员（拥有大部分管理权限）",
        "is_super_admin": False,
        "permissions": [
            "users:manage",
            "roles:read",
            "roles:write",
            "permissions:read",
            "content:manage",
            "system:read",
        ],
    },
    {
        "name": "editor",
        "description": "编辑（可以管理内容）",
        "is_super_admin": False,
        "permissions": [
            "content:read",
            "content:write",
            "content:delete",
            "users:read",
        ],
    },
    {
        "name": "viewer",
        "description": "查看者（只能查看）",
        "is_super_admin": False,
        "permissions": [
            "content:read",
            "users:read",
        ],
    },
]


async def init_permissions(db):
    """初始化权限"""
    print("📝 初始化权限...")
    
    created_count = 0
    for perm_data in DEFAULT_PERMISSIONS:
        # 检查权限是否已存在
        result = await db.execute(
            select(Permission).where(Permission.name == perm_data["name"])
        )
        existing = result.scalar_one_or_none()
        
        if existing is None:
            permission = Permission(**perm_data)
            db.add(permission)
            created_count += 1
            print(f"  ✅ 创建权限: {perm_data['name']}")
        else:
            print(f"  ⏭️  权限已存在: {perm_data['name']}")
    
    await db.commit()
    print(f"✅ 权限初始化完成，创建了 {created_count} 个新权限\n")
    return created_count


async def init_roles(db):
    """初始化角色"""
    print("👥 初始化角色...")
    
    # 先获取所有权限
    result = await db.execute(select(Permission))
    all_permissions = {perm.name: perm for perm in result.scalars().all()}
    
    created_count = 0
    for role_data in DEFAULT_ROLES:
        # 检查角色是否已存在
        result = await db.execute(
            select(Role).where(Role.name == role_data["name"])
        )
        existing = result.scalar_one_or_none()
        
        if existing is None:
            # 创建角色
            role = Role(
                name=role_data["name"],
                description=role_data["description"],
                is_super_admin=role_data["is_super_admin"],
            )
            
            # 分配权限
            if role_data["permissions"]:
                role.permissions = [
                    all_permissions[perm_name]
                    for perm_name in role_data["permissions"]
                    if perm_name in all_permissions
                ]
            
            db.add(role)
            created_count += 1
            print(f"  ✅ 创建角色: {role_data['name']}")
            if role_data["permissions"]:
                print(f"     分配了 {len(role.permissions)} 个权限")
        else:
            print(f"  ⏭️  角色已存在: {role_data['name']}")
    
    await db.commit()
    print(f"✅ 角色初始化完成，创建了 {created_count} 个新角色\n")
    return created_count


async def main():
    """主函数"""
    print("🚀 开始初始化 RBAC 系统...\n")
    
    async with AsyncSessionLocal() as db:
        try:
            # 初始化权限
            perm_count = await init_permissions(db)
            
            # 初始化角色
            role_count = await init_roles(db)
            
            print("=" * 50)
            print(f"✅ RBAC 系统初始化完成！")
            print(f"   - 创建了 {perm_count} 个新权限")
            print(f"   - 创建了 {role_count} 个新角色")
            print("=" * 50)
            
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())

