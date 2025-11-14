# FastServer

FastAPI 后端服务项目

## 📁 项目结构

```
FastServer/
├── app/                          # Python 源代码目录
│   ├── __init__.py
│   ├── main.py                   # FastAPI 应用入口，注册路由和中间件
│   │
│   ├── core/                     # 核心配置和基础设施
│   │   ├── __init__.py
│   │   ├── config.py             # 应用配置（从环境变量读取）
│   │   ├── db.py                 # PostgreSQL 数据库连接和会话管理
│   │   ├── mongodb.py            # MongoDB 客户端连接管理
│   │   ├── redis.py              # Redis 客户端连接管理
│   │   └── security.py           # 安全工具（JWT、密码加密）
│   │
│   ├── models/                   # SQLAlchemy 数据库模型（ORM）
│   │   ├── __init__.py           # 导入所有模型，确保 SQLAlchemy 识别
│   │   ├── user.py               # 用户模型
│   │   ├── role.py               # 角色模型
│   │   ├── permission.py          # 权限模型
│   │   ├── association.py        # 关联表模型（用户-角色、角色-权限）
│   │   └── *.py                  # 其他业务模型（如 post.py, comment.py）
│   │
│   ├── schemas/                  # Pydantic 模型（请求/响应验证）
│   │   ├── __init__.py
│   │   ├── auth.py               # 认证相关的请求/响应模型
│   │   ├── user.py               # 用户相关的请求/响应模型
│   │   ├── role.py               # 角色相关的请求/响应模型
│   │   ├── permission.py         # 权限相关的请求/响应模型
│   │   └── *.py                  # 其他业务相关的请求/响应模型
│   │
│   ├── routers/                  # API 路由（业务接口）
│   │   ├── __init__.py
│   │   ├── auth.py               # 认证路由（注册、登录）
│   │   ├── users.py              # 用户管理路由
│   │   ├── roles.py              # 角色管理路由
│   │   ├── permissions.py        # 权限管理路由
│   │   ├── info_hub.py           # 信息聚合中心模块
│   │   └── *.py                  # 其他业务模块路由
│   │
│   ├── dependencies/             # FastAPI 依赖注入
│   │   ├── __init__.py
│   │   ├── auth.py               # 认证依赖（获取当前用户、超级用户检查）
│   │   ├── permissions.py        # 权限检查依赖（权限验证、角色验证）
│   │   └── *.py                  # 其他共享依赖
│   │
│   ├── utils/                    # 工具模块（框架服务，与业务无关）
│   │   ├── __init__.py
│   │   ├── cache.py              # 缓存管理工具
│   │   ├── token.py              # Token 管理工具
│   │   └── *.py                  # 其他框架工具
│   │
│   └── services/                 # 业务逻辑层（与业务、数据、用户相关）
│       ├── __init__.py
│       ├── crawler.py            # 爬虫服务（信息中心业务）
│       └── *.py                  # 其他业务服务
│
├── docs/                         # 项目文档
│   ├── README.md                 # 文档索引
│   ├── auth/                     # 认证模块文档
│   │   ├── README.md
│   ├── rbac/                     # RBAC 权限管理文档
│   │   ├── README.md
│   │   ├── overview.md            # 概览
│   │   ├── flow.md                # 系统流程
│   │   └── examples.md            # 使用示例
│   └── database/                 # 数据库文档
│       ├── README.md
│       └── migration.md           # 数据库迁移指南
│
├── scripts/                      # 管理脚本
│   ├── __init__.py
│   ├── create_superuser.py       # 创建超级用户脚本
│   └── init_rbac.py              # 初始化 RBAC 系统（创建默认角色和权限）
│
├── .env                          # 环境变量配置（不提交到 Git）
├── .env.example                  # 环境变量模板（可选）
├── docker-compose.yml            # Docker Compose 配置
├── Dockerfile                    # Docker 镜像构建文件
├── pyproject.toml                # Python 项目配置和依赖
├── uv.lock                       # 依赖锁定文件
└── README.md                     # 本文件
```

## 📂 目录说明

### `app/` - 源代码目录

所有 Python 源代码都在这里。

#### `app/main.py`
- **用途**: FastAPI 应用入口
- **应该包含**:
  - FastAPI 应用实例创建
  - 中间件配置（CORS、日志等）
  - 路由注册
  - 应用生命周期管理（可选）

#### `app/core/` - 核心基础设施

**用途**: 存放应用的基础设施代码，不包含业务逻辑

- **`config.py`**: 
  - 应用配置类（从环境变量读取）
  - 数据库连接字符串、密钥等配置
  
- **`db.py`**: 
  - PostgreSQL 数据库引擎和会话管理
  - `get_db()` 依赖注入函数
  
- **`mongodb.py`**: 
  - MongoDB 客户端连接管理
  - `get_mongodb_client()` 等函数
  
- **`redis.py`**: 
  - Redis 客户端连接管理
  - `get_redis()` 依赖注入函数
  
- **`security.py`**: 
  - JWT Token 生成和验证
  - 密码加密和验证
  - 其他安全工具函数

#### `app/models/` - 数据库模型（ORM）

**用途**: SQLAlchemy 数据库模型，对应数据库表结构

- **命名规范**: 使用单数形式，如 `user.py`, `post.py`
- **应该包含**:
  - SQLAlchemy `Base` 继承的模型类
  - 表结构定义（字段、索引、关系等）
- **注意**: 
  - 在 `__init__.py` 中导入所有模型，确保 SQLAlchemy 能识别
  - 模型类名使用单数形式（如 `User`, `Post`）

#### `app/schemas/` - 请求/响应模型

**用途**: Pydantic 模型，用于请求验证和响应序列化

- **命名规范**: 
  - 请求模型: `XxxCreate`, `XxxUpdate`
  - 响应模型: `XxxResponse`
  - 内部模型: `XxxBase`
- **应该包含**:
  - API 请求参数验证
  - API 响应数据格式
  - 数据转换逻辑

#### `app/routers/` - API 路由

**用途**: FastAPI 路由定义，处理 HTTP 请求

- **命名规范**: 使用小写加下划线，如 `info_hub.py`, `user_management.py`
- **应该包含**:
  - 路由装饰器（`@router.get`, `@router.post` 等）
  - 请求处理逻辑
  - 调用 services 层的业务逻辑
- **注意**:
  - 路由函数应该简洁，复杂逻辑放在 `services/` 层
  - 使用依赖注入获取数据库连接和当前用户

#### `app/dependencies/` - 依赖注入

**用途**: FastAPI 依赖注入函数，可复用的依赖逻辑

- **命名规范**: 描述依赖的用途，如 `auth.py`, `database.py`
- **应该包含**:
  - 认证相关的依赖（获取当前用户、权限检查）
  - 数据库连接依赖（如果需要特殊处理）
  - 其他可复用的依赖逻辑

#### `app/utils/` - 工具模块（框架服务）

**用途**: 提供框架服务相关的工具函数和类，与业务逻辑无关

- **命名规范**: 使用工具名称，如 `cache.py`, `token.py`
- **应该包含**:
  - 缓存管理工具（`cache.py`）
  - Token 管理工具（`token.py`）
  - 其他框架级别的工具函数
- **特点**:
  - 与业务逻辑无关，纯粹的技术工具
  - 可以被多个业务模块复用
  - 不依赖具体的业务模型

#### `app/services/` - 业务逻辑层

**用途**: 可复用的业务逻辑服务，与业务、数据、用户相关

- **命名规范**: 使用服务名称，如 `crawler.py`, `email_service.py`
- **应该包含**:
  - 复杂的业务逻辑
  - 外部 API 调用（业务相关）
  - 数据处理和转换（业务相关）
  - 用户相关的业务服务
- **注意**:
  - 服务应该是可测试的（不依赖 FastAPI）
  - 可以被多个路由复用
  - 与 `utils/` 的区别：`services/` 包含业务逻辑，`utils/` 是框架工具

### `docs/` - 项目文档

**用途**: 存放项目技术文档

- **结构**: 按功能模块组织子目录
- **每个模块包含**:
  - `README.md`: 模块索引
  - `overview.md`: 概览文档
  - `flow.md`: 流程说明
  - `examples.md`: 使用示例

### `scripts/` - 管理脚本

**用途**: 存放管理工具脚本

- **`create_superuser.py`**: 创建或升级超级用户
  - 使用方法: `python scripts/create_superuser.py <username> <email> <password>`
  - 如果用户已存在，会升级为超级用户
  - 如果用户不存在，会创建新的超级用户

## 🚀 快速开始

### 1. 环境准备

```bash
# 复制环境变量文件
cp .env.example .env  # 如果存在

# 编辑 .env 文件，配置数据库连接等信息
```

### 2. 安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -r requirements.txt
```

### 3. 数据库迁移

参考 [数据库迁移文档](./docs/database/migration.md) 初始化数据库。

### 4. 启动服务

```bash
# 使用 Docker Compose（推荐）
docker-compose up -d

# 或本地运行
uvicorn app.main:app --reload
```

### 5. 访问文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc


## 📝 开发规范

### 文件命名

- **Python 文件**: 使用小写加下划线（`snake_case`）
- **模型文件**: 使用单数形式（`user.py`, `post.py`）
- **路由文件**: 描述功能（`info_hub.py`, `user_management.py`）

### 代码组织

1. **路由层** (`routers/`): 只处理 HTTP 请求，调用服务层和工具层
2. **服务层** (`services/`): 实现业务逻辑（与业务、数据、用户相关）
3. **工具层** (`utils/`): 提供框架服务工具（与业务无关）
4. **模型层** (`models/`): 数据库模型
5. **模式层** (`schemas/`): 请求/响应验证
6. **依赖注入层** (`dependencies/`): FastAPI 依赖注入函数

### 依赖注入使用

- 使用 `Depends()` 获取数据库连接和当前用户
- 避免在路由中直接创建数据库连接
- 依赖函数应该放在 `dependencies/` 目录

## 📚 相关文档

- [项目文档索引](./docs/README.md)
- [认证与授权文档](./docs/auth/README.md)
- [数据库迁移文档](./docs/database/migration.md)

## 🔧 技术栈

- **框架**: FastAPI
- **数据库**: PostgreSQL (SQLAlchemy), MongoDB (Motor), Redis
- **认证**: JWT (python-jose)
- **密码加密**: bcrypt (passlib)
- **数据库迁移**: Alembic
- **容器化**: Docker, Docker Compose
- **依赖管理**: uv / pip

## 📌 重要提示

1. **环境变量**: 所有敏感配置都在 `.env` 文件中，不要提交到 Git
2. **数据库迁移**: 使用 Alembic 管理数据库迁移，参考 [数据库迁移文档](./docs/database/migration.md)
3. **代码规范**: 遵循 PEP 8，使用类型提示
4. **测试**: 编写单元测试和集成测试（待实现）
