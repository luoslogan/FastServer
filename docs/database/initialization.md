# 数据库初始化迁移指南

本文档详细记录如何从零开始设置 Alembic 迁移系统，包括完整的初始化流程。

> **注意**：本文档仅用于**首次初始化**或**重新初始化**数据库。日常的迁移操作请参考 [迁移操作指南](./migration.md)。

## 📋 前置条件

1. **项目已配置 Docker Compose**
2. **数据库服务已运行**
3. **已安装 Alembic**（在 `requirements.txt` 中）

## 🚀 完整初始化流程

### 步骤 1: 清理数据库（如果需要）

如果数据库已有数据，需要先清理：

```bash
# 方式 1: 删除并重建 schema（推荐）
docker compose exec db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# 方式 2: 删除并重建数据库（更彻底）
docker compose exec db psql -U postgres -c "DROP DATABASE IF EXISTS ${POSTGRES_DB}; CREATE DATABASE ${POSTGRES_DB};"
```

### 步骤 2: 安装同步数据库驱动

Alembic 需要同步数据库驱动（psycopg2），而项目使用异步驱动（asyncpg）。

**编辑 `requirements.txt`**，添加：

```txt
psycopg2-binary==2.9.9
```

**重新构建镜像**：

```bash
docker compose build api
docker compose up -d --force-recreate api
```

### 步骤 3: 初始化 Alembic

在容器内执行：

```bash
docker compose exec api alembic init migrations
```

这会在项目根目录创建：
- `alembic.ini` - Alembic 配置文件
- `migrations/` 目录
  - `versions/` - 存放迁移文件
  - `env.py` - 迁移环境配置
  - `script.py.mako` - 迁移文件模板

### 步骤 4: 配置 `alembic.ini`

**编辑 `alembic.ini`**，注释掉默认的数据库 URL：

```ini
# sqlalchemy.url = driver://user:pass@localhost/dbname
# 使用环境变量 DATABASE_URL，在 env.py 中读取
```

### 步骤 5: 配置 `migrations/env.py`

这是**最关键**的配置文件，需要修改以下部分：

#### 5.1 添加项目路径和导入

在文件开头添加：

```python
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 导入配置和模型
from app.core.config import settings
from app.core.db import Base
from app.models import User, Role, Permission, RefreshToken  # 导入所有模型
```

#### 5.2 配置数据库 URL

找到 `config = context.config` 之后，添加：

```python
# 从配置中读取数据库 URL
# Alembic 需要同步连接，将异步 URL 转换为同步格式
database_url = settings.DATABASE_URL
if database_url.startswith("postgresql+asyncpg://"):
    # 转换为 postgresql+psycopg2:// 格式（Alembic 使用同步驱动）
    database_url = database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
config.set_main_option("sqlalchemy.url", database_url)
```

#### 5.3 设置 target_metadata

找到 `target_metadata = None`，改为：

```python
target_metadata = Base.metadata
```

### 步骤 6: 配置 Docker Compose 挂载

**编辑 `docker-compose.yml`**，确保迁移文件持久化：

```yaml
volumes:
  - ./app:/code/app
  - ./scripts:/code/scripts
  - ./alembic.ini:/code/alembic.ini
  - ./migrations:/code/migrations
```

重启容器使挂载生效：

```bash
docker compose restart api
```

### 步骤 7: 创建表结构迁移（自动生成）

**这是实际工作中最常用的方式**：

```bash
docker compose exec api alembic revision --autogenerate -m "Create initial tables"
```

这会自动检测 `app/models/` 中的所有模型，生成创建表的迁移文件。

**检查生成的迁移文件**（位于 `migrations/versions/`）：

- 打开生成的文件，检查 SQL 语句是否正确
- 确认所有表、索引、外键都已包含
- 如有问题，手动调整

### 步骤 8: 创建数据迁移（手动编写）

数据迁移无法自动生成，需要手动创建和编写。

#### 8.1 创建空的数据迁移文件

```bash
docker compose exec api alembic revision -m "Initialize RBAC permissions and roles"
```

这会创建一个空的迁移文件，你需要手动编写 `upgrade()` 和 `downgrade()` 函数。

#### 8.2 编写数据迁移逻辑

**打开生成的迁移文件**（例如 `migrations/versions/5392d8862baa_initialize_rbac_permissions_and_roles.py`），编写数据插入逻辑：

```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

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
            perm
        )
        row = result.fetchone()
        if row:
            permissions_map[row[1]] = row[0]
    
    # 2. 插入角色并分配权限
    # ... 更多逻辑
    
    connection.commit()

def downgrade() -> None:
    """删除 RBAC 权限和角色"""
    # 编写回退逻辑
    pass
```

**关键点**：
- 使用 `op.get_bind()` 获取数据库连接
- 使用 `text()` 执行 SQL 语句
- 使用 `ON CONFLICT DO NOTHING` 避免重复插入
- 必须实现 `downgrade()` 函数用于回退

#### 8.3 创建超级用户迁移

同样方式创建：

```bash
docker compose exec api alembic revision -m "Create initial superuser"
```

在迁移文件中硬编码超级用户信息：

```python
# 超级用户配置（硬编码在迁移文件中）
SUPERUSER_USERNAME = "admin"
SUPERUSER_EMAIL = "admin@example.com"
SUPERUSER_PASSWORD = "password123"

from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def upgrade() -> None:
    """创建初始超级用户"""
    connection = op.get_bind()
    hashed_password = pwd_context.hash(SUPERUSER_PASSWORD)
    # ... 插入或更新用户逻辑
```

### 步骤 9: 应用迁移

**检查迁移历史**：

```bash
docker compose exec api alembic history
```

**应用所有迁移**：

```bash
docker compose exec api alembic upgrade head
```

**验证迁移状态**：

```bash
docker compose exec api alembic current
```

### 步骤 10: 验证数据

验证数据是否正确创建：

```bash
# 检查表是否创建
docker compose exec db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "\dt"

# 检查权限数据
docker compose exec db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "SELECT COUNT(*) FROM permissions;"

# 检查角色数据
docker compose exec db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "SELECT COUNT(*) FROM roles;"

# 检查超级用户
docker compose exec db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "SELECT username, email, is_superuser FROM users WHERE is_superuser = TRUE;"
```

## ⚠️ 重要注意事项

### 1. 迁移文件持久化

- **必须**在 `docker-compose.yml` 中挂载 `alembic.ini` 和 `migrations/` 目录
- 否则容器重启或重建后，迁移文件会丢失

### 2. 数据库 URL 转换

- 项目使用异步驱动 `postgresql+asyncpg://`
- Alembic 需要同步驱动 `postgresql+psycopg2://`
- 必须在 `env.py` 中自动转换

### 3. 模型导入

- **必须**在 `env.py` 中导入所有模型
- 否则 `--autogenerate` 无法检测到表结构变化
- 每次添加新模型后，记得更新导入

### 4. 数据迁移最佳实践

- 使用 `ON CONFLICT DO NOTHING` 避免重复插入
- 使用 `RETURNING` 获取插入的 ID
- 必须实现 `downgrade()` 函数
- 敏感信息（如密码）可以硬编码在迁移文件中

### 5. 迁移顺序

- 表结构迁移必须在数据迁移之前
- 使用 `down_revision` 确保正确的迁移顺序
- 不要手动修改已应用的迁移文件

## 📚 参考文件

- 表结构迁移：`migrations/versions/b7c392398361_create_initial_tables.py`
- RBAC 数据迁移：`migrations/versions/5392d8862baa_initialize_rbac_permissions_and_roles.py`
- 超级用户迁移：`migrations/versions/bad358e26d5e_create_initial_superuser.py`
- 配置文件：`migrations/env.py`
- Alembic 配置：`alembic.ini`

## 🐛 常见问题

### 问题 1: 迁移文件在容器内但宿主机看不到

**原因**：没有挂载迁移目录

**解决**：在 `docker-compose.yml` 中添加挂载：
```yaml
volumes:
  - ./migrations:/code/migrations
  - ./alembic.ini:/code/alembic.ini
```

### 问题 2: 无法连接数据库

**原因**：数据库 URL 格式错误或驱动未安装

**解决**：
1. 检查 `env.py` 中的 URL 转换逻辑
2. 确认 `psycopg2-binary` 已安装
3. 重新构建镜像

### 问题 3: 检测不到模型变化

**原因**：模型未导入或 `target_metadata` 未设置

**解决**：
1. 检查 `env.py` 中是否导入了所有模型
2. 确认 `target_metadata = Base.metadata`

## 🔗 相关文档

- [日常迁移操作指南](./migration.md) - 日常开发中的迁移操作
- [数据库文档索引](./README.md)

