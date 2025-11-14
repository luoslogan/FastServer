"""Initialize RBAC permissions and roles

Revision ID: 5392d8862baa
Revises: b7c392398361
Create Date: 2025-11-11 19:14:00.725911

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "5392d8862baa"
down_revision: Union[str, Sequence[str], None] = "b7c392398361"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 默认权限定义
DEFAULT_PERMISSIONS = [
    {
        "name": "users:read",
        "resource": "users",
        "action": "read",
        "description": "查看用户",
    },
    {
        "name": "users:write",
        "resource": "users",
        "action": "write",
        "description": "创建/编辑用户",
    },
    {
        "name": "users:delete",
        "resource": "users",
        "action": "delete",
        "description": "删除用户",
    },
    {
        "name": "users:manage",
        "resource": "users",
        "action": "manage",
        "description": "管理用户（包含所有用户操作）",
    },
    {
        "name": "roles:read",
        "resource": "roles",
        "action": "read",
        "description": "查看角色",
    },
    {
        "name": "roles:write",
        "resource": "roles",
        "action": "write",
        "description": "创建/编辑角色",
    },
    {
        "name": "roles:delete",
        "resource": "roles",
        "action": "delete",
        "description": "删除角色",
    },
    {
        "name": "roles:manage",
        "resource": "roles",
        "action": "manage",
        "description": "管理角色（包含所有角色操作）",
    },
    {
        "name": "permissions:read",
        "resource": "permissions",
        "action": "read",
        "description": "查看权限",
    },
    {
        "name": "permissions:write",
        "resource": "permissions",
        "action": "write",
        "description": "创建/编辑权限",
    },
    {
        "name": "permissions:delete",
        "resource": "permissions",
        "action": "delete",
        "description": "删除权限",
    },
    {
        "name": "permissions:manage",
        "resource": "permissions",
        "action": "manage",
        "description": "管理权限（包含所有权限操作）",
    },
    {
        "name": "content:read",
        "resource": "content",
        "action": "read",
        "description": "查看内容",
    },
    {
        "name": "content:write",
        "resource": "content",
        "action": "write",
        "description": "创建/编辑内容",
    },
    {
        "name": "content:delete",
        "resource": "content",
        "action": "delete",
        "description": "删除内容",
    },
    {
        "name": "content:manage",
        "resource": "content",
        "action": "manage",
        "description": "管理内容（包含所有内容操作）",
    },
    {
        "name": "system:read",
        "resource": "system",
        "action": "read",
        "description": "查看系统信息",
    },
    {
        "name": "system:write",
        "resource": "system",
        "action": "write",
        "description": "修改系统配置",
    },
    {
        "name": "system:manage",
        "resource": "system",
        "action": "manage",
        "description": "管理系统（包含所有系统操作）",
    },
]

# 默认角色定义
DEFAULT_ROLES = [
    {
        "name": "super_admin",
        "description": "超级管理员（拥有所有权限，通过 is_super_admin 标志控制）",
        "is_super_admin": True,
        "permissions": [],
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


def upgrade() -> None:
    """初始化 RBAC 权限和角色"""
    connection = op.get_bind()

    # 1. 插入权限
    permissions_map = {}
    for perm in DEFAULT_PERMISSIONS:
        result = connection.execute(
            text("""
                INSERT INTO permissions (name, resource, action, description)
                VALUES (:name, :resource, :action, :description)
                ON CONFLICT (name) DO NOTHING
                RETURNING id, name
            """),
            perm,
        )
        row = result.fetchone()
        if row:
            permissions_map[row[1]] = row[0]

    # 2. 插入角色
    roles_map = {}
    for role_data in DEFAULT_ROLES:
        result = connection.execute(
            text("""
                INSERT INTO roles (name, description, is_super_admin)
                VALUES (:name, :description, :is_super_admin)
                ON CONFLICT (name) DO NOTHING
                RETURNING id, name
            """),
            {
                "name": role_data["name"],
                "description": role_data["description"],
                "is_super_admin": role_data["is_super_admin"],
            },
        )
        row = result.fetchone()
        if row:
            roles_map[row[1]] = row[0]

            # 3. 分配权限
            if role_data["permissions"]:
                for perm_name in role_data["permissions"]:
                    if perm_name in permissions_map:
                        connection.execute(
                            text("""
                                INSERT INTO role_permissions (role_id, permission_id)
                                VALUES (:role_id, :permission_id)
                                ON CONFLICT DO NOTHING
                            """),
                            {
                                "role_id": row[0],
                                "permission_id": permissions_map[perm_name],
                            },
                        )

    connection.commit()


def downgrade() -> None:
    """删除 RBAC 权限和角色"""
    connection = op.get_bind()

    # 删除角色权限关联
    for role_data in DEFAULT_ROLES:
        connection.execute(
            text(
                "DELETE FROM role_permissions WHERE role_id IN (SELECT id FROM roles WHERE name = :name)"
            ),
            {"name": role_data["name"]},
        )

    # 删除角色
    for role_data in DEFAULT_ROLES:
        connection.execute(
            text("DELETE FROM roles WHERE name = :name"), {"name": role_data["name"]}
        )

    # 删除权限
    for perm in DEFAULT_PERMISSIONS:
        connection.execute(
            text("DELETE FROM permissions WHERE name = :name"), {"name": perm["name"]}
        )

    connection.commit()
