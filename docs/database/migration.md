# PostgreSQL 数据库迁移指南

本项目使用 **Alembic** 管理 PostgreSQL 数据库迁移。

## 📋 前置条件

### 1. 安装 Alembic

```bash
# 使用 uv
uv add alembic

# 或使用 pip
pip install alembic
```

### 2. 确保数据库服务运行

```bash
# 启动 Docker Compose 服务
docker-compose up -d db

# 或启动所有服务
docker-compose up -d
```

## 🚀 初始化 Alembic

### 在项目根目录执行

```bash
alembic init migrations
```

这会在项目根目录创建：
- `migrations/` 目录（存放迁移文件）
- `alembic.ini` 配置文件

## ⚙️ 配置 Alembic

### 1. 配置数据库连接

编辑 `alembic.ini`，找到 `sqlalchemy.url` 行：

```ini
# 方式 1: 直接使用环境变量（推荐）
sqlalchemy.url = ${DATABASE_URL}

# 方式 2: 硬编码（不推荐，仅用于测试）
# sqlalchemy.url = postgresql+asyncpg://user:password@localhost:5432/dbname
```

**注意**: 如果使用 `${DATABASE_URL}`，需要确保环境变量已设置。

### 2. 配置迁移环境

编辑 `migrations/env.py`，进行以下修改：

#### a) 导入 Base 和所有模型

在文件顶部添加：

```python
from app.core.db import Base
from app.models import User  # 导入所有模型，确保 Alembic 能检测到
# 添加其他模型导入...
```

**重要**: 必须导入所有模型，否则 Alembic 无法检测到表结构变化。

#### b) 设置 target_metadata

找到 `target_metadata = None`，改为：

```python
target_metadata = Base.metadata
```

#### c) 配置数据库 URL（从环境变量读取）

找到 `config.get_main_option("sqlalchemy.url")` 部分，可以改为：

```python
from app.core.config import settings

# 使用项目配置中的数据库 URL
url = settings.DATABASE_URL
```

或者保持使用 `alembic.ini` 中的配置。

## 🐳 Docker 环境说明

### 数据库连接配置

在 Docker 环境中，数据库服务名是 `db`（在 docker-compose.yml 中定义）。

**`.env` 文件中的配置**:
```bash
# Docker 网络内使用服务名
DATABASE_URL=postgresql+asyncpg://fastapi_user:password@db:5432/fastapi_db
```

**本地运行时的配置**:
```bash
# 本地运行时使用 localhost
DATABASE_URL=postgresql+asyncpg://fastapi_user:password@localhost:5432/fastapi_db
```

### 执行迁移的方式

#### 方式 1: 在 Docker 容器内执行（推荐）

```bash
# 进入应用容器
docker-compose exec api bash

# 在容器内执行迁移命令
alembic upgrade head
alembic revision --autogenerate -m "描述"
```

**优势**:
- 环境一致，避免本地环境差异
- 数据库连接使用服务名 `db`，配置简单

#### 方式 2: 在本地执行

```bash
# 确保数据库端口已映射（docker-compose.yml 中已配置 5432:5432）
# 使用 localhost 连接

# 执行迁移
alembic upgrade head
```

**前提条件**:
- `.env` 中的 `DATABASE_URL` 使用 `localhost` 而不是 `db`
- 或者临时修改 `alembic.ini` 中的连接字符串

## 📝 创建迁移

### 自动生成迁移（推荐）

```bash
# 自动检测模型变化并生成迁移
alembic revision --autogenerate -m "描述信息"

# 示例
alembic revision --autogenerate -m "Create users table"
alembic revision --autogenerate -m "Add email field to users"
```

**工作原理**:
1. Alembic 比较当前模型（`app/models/`）和数据库结构
2. 自动生成迁移脚本
3. 需要手动检查生成的迁移文件，确保正确

### 手动创建迁移

```bash
# 创建空的迁移文件
alembic revision -m "描述信息"
```

然后手动编辑生成的迁移文件（位于 `migrations/versions/`）。

## 🔄 应用迁移

### 在 Docker 容器内执行（推荐）

```bash
# 进入应用容器
docker-compose exec api bash

# 应用到最新版本
alembic upgrade head

# 应用到指定版本
alembic upgrade <revision_id>

# 回退一个版本
alembic downgrade -1

# 回退到指定版本
alembic downgrade <revision_id>

# 查看当前版本
alembic current

# 查看迁移历史
alembic history
```

### 在本地执行

```bash
# 确保数据库服务运行且端口已映射
docker-compose up -d db

# 执行迁移命令
alembic upgrade head
```

## 📂 迁移文件位置

迁移文件位于 `migrations/versions/` 目录下，命名格式为: `{revision_id}_{描述}.py`

示例:
- `001_create_users_table.py`
- `002_add_email_to_users.py`

## ⚠️ 注意事项

### 1. 模型导入

- **必须**在 `migrations/env.py` 中导入所有模型
- 否则 Alembic 无法检测到表结构变化
- 每次添加新模型后，确保导入

### 2. 数据库连接

- **Docker 环境**: 使用服务名 `db` 作为主机名
- **本地环境**: 使用 `localhost` 作为主机名
- 确保 `.env` 文件中的 `DATABASE_URL` 配置正确

### 3. 迁移顺序

- **不要**手动修改已应用的迁移文件
- 如果需要修改，创建新的迁移
- 迁移文件应该按顺序应用

### 4. 生产环境

- 在生产环境应用迁移前，**必须**先在测试环境验证
- 建议在应用迁移前备份数据库
- 使用 `alembic upgrade head --sql` 预览 SQL（不实际执行）

### 5. 异步支持

- 项目使用 SQLAlchemy 异步引擎
- Alembic 默认使用同步连接
- 需要在 `migrations/env.py` 中配置异步支持（如果使用异步特性）

## 🔧 常用命令

### 查看状态

```bash
# 查看当前数据库版本
alembic current

# 查看所有迁移历史
alembic history

# 查看迁移历史（详细）
alembic history --verbose
```

### 生成迁移

```bash
# 自动生成迁移
alembic revision --autogenerate -m "描述"

# 手动创建迁移
alembic revision -m "描述"
```

### 应用迁移

```bash
# 升级到最新版本
alembic upgrade head

# 升级到指定版本
alembic upgrade <revision_id>

# 升级一个版本
alembic upgrade +1

# 预览 SQL（不实际执行）
alembic upgrade head --sql
```

### 回退迁移

```bash
# 回退一个版本
alembic downgrade -1

# 回退到指定版本
alembic downgrade <revision_id>

# 回退到基础版本
alembic downgrade base
```

## 🐛 故障排查

### 问题 1: 无法连接到数据库

**症状**: `alembic: error: Can't locate revision identified by 'head'`

**解决方案**:
1. 检查数据库服务是否运行: `docker-compose ps`
2. 检查 `.env` 中的 `DATABASE_URL` 配置
3. 在 Docker 环境内执行时，确保使用服务名 `db`
4. 在本地执行时，确保使用 `localhost` 且端口已映射

### 问题 2: 检测不到模型变化

**症状**: `alembic revision --autogenerate` 没有生成迁移

**解决方案**:
1. 检查 `migrations/env.py` 中是否导入了所有模型
2. 确保 `target_metadata = Base.metadata` 已设置
3. 检查模型类是否正确继承 `Base`

### 问题 3: 迁移文件冲突

**症状**: 多个迁移文件指向同一个版本

**解决方案**:
1. 检查迁移文件的 `down_revision` 是否正确
2. 确保迁移文件按顺序创建
3. 使用 `alembic history` 查看迁移链

## 📚 参考资源

- [Alembic 官方文档](https://alembic.sqlalchemy.org/)
- [SQLAlchemy 异步支持](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [项目数据库配置](../README.md#数据库迁移)

