# 数据库迁移操作指南

本文档介绍日常开发中的数据库迁移操作，适用于已经完成初始化的项目。

> **首次初始化**：如果是新项目或需要重新初始化，请参考 [数据库初始化指南](./initialization.md)。

## 📋 前置条件

1. **Alembic 已初始化**（已有 `migrations/` 目录和 `alembic.ini`）
2. **迁移环境已配置**（`migrations/env.py` 已正确配置）
3. **数据库服务已运行**

## 🔄 日常迁移工作流程

### 场景 1: 修改表结构（最常见）

当你修改了 `app/models/` 中的模型后：

#### 步骤 1: 自动生成迁移

```bash
docker compose exec api alembic revision --autogenerate -m "描述变更内容"
```

**示例**：
```bash
# 添加新字段
docker compose exec api alembic revision --autogenerate -m "Add phone field to users"

# 创建新表
docker compose exec api alembic revision --autogenerate -m "Create posts table"

# 修改字段类型
docker compose exec api alembic revision --autogenerate -m "Change email to nullable"
```

#### 步骤 2: 检查生成的迁移文件

**打开生成的迁移文件**（位于 `migrations/versions/`），检查：

- ✅ SQL 语句是否正确
- ✅ 是否包含所有变更
- ✅ 是否有不必要的操作
- ✅ 索引、外键是否正确

**常见需要手动调整的情况**：
- 重命名字段（Alembic 可能生成 DROP + CREATE，需要改为 ALTER）
- 修改字段类型（可能需要数据转换逻辑）
- 删除字段（确认数据已备份）

#### 步骤 3: 应用迁移

```bash
docker compose exec api alembic upgrade head
```

#### 步骤 4: 验证

```bash
# 查看当前迁移版本
docker compose exec api alembic current

# 检查表结构
docker compose exec db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "\d table_name"
```

### 场景 2: 数据迁移

需要插入、更新或删除数据时：

#### 步骤 1: 创建空迁移

```bash
docker compose exec api alembic revision -m "描述数据变更"
```

#### 步骤 2: 编写迁移逻辑

**打开生成的迁移文件**，编写 `upgrade()` 和 `downgrade()` 函数：

```python
from alembic import op
from sqlalchemy import text

def upgrade() -> None:
    """执行数据迁移"""
    connection = op.get_bind()
    
    # 示例：批量更新数据
    connection.execute(
        text("UPDATE users SET status = 'active' WHERE status IS NULL")
    )
    
    # 示例：插入默认数据
    connection.execute(
        text("""
            INSERT INTO settings (key, value)
            VALUES ('default_language', 'zh-CN')
            ON CONFLICT (key) DO NOTHING
        """)
    )
    
    connection.commit()

def downgrade() -> None:
    """回退数据迁移"""
    connection = op.get_bind()
    
    # 编写回退逻辑
    connection.execute(
        text("DELETE FROM settings WHERE key = 'default_language'")
    )
    
    connection.commit()
```

#### 步骤 3: 应用迁移

```bash
docker compose exec api alembic upgrade head
```

### 场景 3: 回退迁移

如果需要撤销最近的迁移：

```bash
# 回退一个版本
docker compose exec api alembic downgrade -1

# 回退到指定版本
docker compose exec api alembic downgrade <revision_id>

# 回退到基础版本（删除所有表）
docker compose exec api alembic downgrade base
```

**⚠️ 警告**：回退操作会删除数据，生产环境请谨慎使用！

## 🔧 常用命令

### 查看状态

```bash
# 查看当前数据库版本
docker compose exec api alembic current

# 查看所有迁移历史
docker compose exec api alembic history

# 查看迁移历史（详细，包含分支信息）
docker compose exec api alembic history --verbose
```

### 生成迁移

```bash
# 自动生成迁移（检测模型变化）
docker compose exec api alembic revision --autogenerate -m "描述"

# 手动创建空迁移
docker compose exec api alembic revision -m "描述"
```

### 应用迁移

```bash
# 升级到最新版本
docker compose exec api alembic upgrade head

# 升级到指定版本
docker compose exec api alembic upgrade <revision_id>

# 升级一个版本
docker compose exec api alembic upgrade +1

# 预览 SQL（不实际执行，用于审核）
docker compose exec api alembic upgrade head --sql
```

### 回退迁移

```bash
# 回退一个版本
docker compose exec api alembic downgrade -1

# 回退到指定版本
docker compose exec api alembic downgrade <revision_id>

# 回退到基础版本
docker compose exec api alembic downgrade base
```

## 📝 最佳实践

### 1. 迁移文件命名

使用清晰的描述性名称：

```bash
# ✅ 好的命名
alembic revision --autogenerate -m "Add phone field to users"
alembic revision --autogenerate -m "Create posts table"
alembic revision -m "Migrate user roles to new structure"

# ❌ 不好的命名
alembic revision --autogenerate -m "update"
alembic revision --autogenerate -m "fix"
```

### 2. 检查生成的迁移

**每次自动生成迁移后，必须检查**：

1. 打开生成的迁移文件
2. 检查 `upgrade()` 函数中的 SQL 操作
3. 确认是否符合预期
4. 如有问题，手动修改

### 3. 添加新模型后

**必须更新 `migrations/env.py`**：

```python
from app.models import (
    User,
    Role,
    Permission,
    RefreshToken,
    Post,  # 新增的模型
    Comment,  # 新增的模型
)
```

### 4. 数据迁移注意事项

- ✅ 使用 `ON CONFLICT DO NOTHING` 避免重复插入
- ✅ 使用事务确保数据一致性
- ✅ 必须实现 `downgrade()` 函数
- ✅ 大数据量迁移考虑分批处理
- ❌ 不要在迁移中执行耗时操作（如 API 调用）

### 5. 生产环境部署

**部署前必须**：

1. ✅ 在测试环境验证迁移
2. ✅ 备份数据库
3. ✅ 使用 `--sql` 预览 SQL
4. ✅ 在维护窗口期执行
5. ✅ 监控迁移执行过程

## 🐳 Docker 环境说明

### 执行迁移

**推荐方式**：在容器内执行

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic revision --autogenerate -m "描述"
```

**优势**：
- 环境一致
- 数据库连接使用服务名 `db`，配置简单
- 迁移文件自动同步到宿主机（已挂载）

### 数据库连接配置

- **容器内**：使用服务名 `db`（`DATABASE_URL` 中使用 `db:5432`）
- **宿主机**：使用 `localhost`（`DATABASE_URL` 中使用 `localhost:5432`）

## ⚠️ 注意事项

### 1. 不要修改已应用的迁移文件

- 已应用的迁移文件是历史记录，不应修改
- 如果需要修改，创建新的迁移文件

### 2. 迁移顺序

- 迁移文件通过 `down_revision` 形成链式结构
- Alembic 会自动处理顺序，但创建时要注意依赖关系

### 3. 模型导入

- **每次添加新模型后**，更新 `migrations/env.py` 中的导入
- 否则 `--autogenerate` 无法检测到新表

### 4. 冲突处理

如果多个开发者同时创建迁移：

```bash
# 查看迁移历史，确认顺序
docker compose exec api alembic history

# 如果有冲突，手动调整 down_revision
# 编辑迁移文件，修改 down_revision 指向正确的版本
```

## 🐛 故障排查

### 问题 1: 检测不到模型变化

**症状**：`alembic revision --autogenerate` 没有生成迁移

**解决方案**：
1. 检查 `migrations/env.py` 中是否导入了新模型
2. 确认 `target_metadata = Base.metadata` 已设置
3. 检查模型类是否正确继承 `Base`
4. 确认模型文件已保存

### 问题 2: 迁移文件冲突

**症状**：多个迁移文件指向同一个 `down_revision`

**解决方案**：
1. 查看迁移历史：`alembic history`
2. 编辑冲突的迁移文件，修改 `down_revision`
3. 确保迁移链是连续的

### 问题 3: 迁移失败

**症状**：`alembic upgrade head` 执行失败

**解决方案**：
1. 查看错误信息，定位问题
2. 如果是数据问题，先修复数据
3. 如果是迁移逻辑问题，修复迁移文件
4. 如果已部分执行，可能需要手动修复数据库状态

### 问题 4: 无法连接到数据库

**症状**：`alembic: error: Can't locate revision identified by 'head'`

**解决方案**：
1. 检查数据库服务是否运行：`docker compose ps`
2. 检查 `.env` 中的 `DATABASE_URL` 配置
3. 在容器内执行时，确保使用服务名 `db`
4. 检查 `migrations/env.py` 中的 URL 转换逻辑

### 问题 5: Target database is not up to date

**症状**：执行 `alembic revision --autogenerate` 时出现错误：
```
ERROR [alembic.util.messaging] Target database is not up to date.
FAILED: Target database is not up to date.
```

**原因**：
数据库的当前版本与迁移文件不一致。通常发生在：
- 数据库版本落后于最新的迁移文件
- 迁移文件被修改或删除后重新生成
- 数据库版本号与迁移历史链不匹配

**诊断步骤**：

1. **查看当前数据库版本**：
```bash
docker compose exec api alembic current
```

2. **查看迁移历史**：
```bash
docker compose exec api alembic history
```

3. **查看最新迁移版本**：
```bash
docker compose exec api alembic heads
```

**解决方案**：

#### 方案 1: 应用缺失的迁移（推荐）

如果数据库版本落后，先应用缺失的迁移：

```bash
# 升级到最新版本
docker compose exec api alembic upgrade head

# 验证版本
docker compose exec api alembic current
```

#### 方案 2: 标记数据库为最新版本（谨慎使用）

如果确认数据库结构已经是最新的（例如迁移是数据迁移，已经手动执行过），可以标记数据库版本：

```bash
# 标记数据库为最新版本（不执行迁移，仅更新版本号）
docker compose exec api alembic stamp head

# 验证版本
docker compose exec api alembic current
```

**⚠️ 警告**：`alembic stamp` 命令不会执行迁移，只是更新版本号。只有在确认数据库结构已经是最新状态时才使用。

#### 方案 3: 标记到特定版本

如果需要标记到特定版本（不是最新版本）：

```bash
# 标记到指定版本
docker compose exec api alembic stamp <revision_id>

# 例如：标记到某个中间版本
docker compose exec api alembic stamp 5392d8862baa
```

**完整示例**：

假设遇到以下情况：
- 数据库当前版本：`5392d8862baa`
- 最新迁移版本：`bad358e26d5e`
- 错误：`Target database is not up to date`

解决步骤：

```bash
# 1. 检查当前状态
docker compose exec api alembic current
# 输出: 5392d8862baa

docker compose exec api alembic heads
# 输出: bad358e26d5e (head)

# 2. 如果 bad358e26d5e 是数据迁移且已手动执行，标记版本
docker compose exec api alembic stamp head

# 或者，如果迁移未执行，先执行迁移
docker compose exec api alembic upgrade head

# 3. 验证版本已更新
docker compose exec api alembic current
# 输出: bad358e26d5e (head)

# 4. 现在可以创建新迁移
docker compose exec api alembic revision --autogenerate -m "add_new_field"
```

**预防措施**：

1. ✅ 每次执行迁移后，验证版本：`alembic current`
2. ✅ 使用版本控制管理迁移文件，避免手动修改已应用的迁移
3. ✅ 团队协作时，先拉取最新代码，确保迁移文件同步
4. ✅ 生产环境部署前，在测试环境验证迁移流程

## 📚 参考资源

- [数据库初始化指南](./initialization.md) - 首次初始化流程
- [Alembic 官方文档](https://alembic.sqlalchemy.org/)
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
