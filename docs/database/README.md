# 数据库文档

本目录包含数据库相关的文档。

## 📚 文档索引

### [数据库迁移](./migration.md)
PostgreSQL 数据库迁移完整指南，包括：
- Alembic 安装和初始化
- 配置说明（包括 Docker 环境）
- 创建和应用迁移
- 常用命令和故障排查

## 🔍 相关资源

- 数据库连接配置: `app/core/db.py`
- 数据库模型: `app/models/`
- 环境变量配置: `.env` 文件中的 `DATABASE_URL`

## 📝 快速参考

### 在 Docker 容器内执行迁移

```bash
# 进入容器
docker-compose exec api bash

# 应用迁移
alembic upgrade head

# 生成迁移
alembic revision --autogenerate -m "描述"
```

### 在本地执行迁移

```bash
# 确保数据库服务运行
docker-compose up -d db

# 执行迁移
alembic upgrade head
```

