# 鉴权系统使用示例

## 一、已实现的功能

✅ **基础认证系统**
- 用户注册 (`POST /api/v1/auth/register`)
- 用户登录 (`POST /api/v1/auth/login`) - **支持 Cookie 和 Header 双重认证**
- 获取当前用户信息 (`GET /api/v1/users/me`)
- JWT Token 生成和验证
- 密码加密存储（bcrypt）
- **Cookie 认证支持**（Web 应用自动携带）

✅ **RBAC 权限系统**
- 角色管理 API
- 权限管理 API
- 用户角色分配
- Redis 权限缓存
- **缓存自动更新机制**（角色/权限变化时自动清除）

✅ **依赖注入系统**
- 用户级别：`get_current_user`, `get_current_active_user`, `require_superuser`
- **新增**：`get_userinfo` - 从 request.state 获取用户信息（性能优化）
- 角色级别：`require_role(role_name)`
- 权限级别：`require_permission(permission_name)`
- **路由级依赖** - 整个路由组统一鉴权，减少重复代码

✅ **性能优化**
- **request.state.userinfo** - 请求级用户信息缓存（自动更新）
- Redis 权限缓存（1小时，自动清除机制）
- **全局认证中间件** - 统一认证，避免重复查询数据库

✅ **全局认证中间件**
- 强制所有接口都需要认证（除了白名单）
- 自动设置 `request.state.userinfo`
- 与依赖注入系统协作，性能优化

✅ **邮箱验证和密码重置**
- 邮箱验证功能（注册时自动发送验证邮件）
- 密码重置功能（忘记密码，通过邮箱重置）
- 支持纯后端完成（不需要前端）
- 支持前端页面配合（可选）

## 二、使用示例

### 1. 用户注册

```bash
POST /api/v1/auth/register
Content-Type: application/json

{
  "username": "testuser",
  "email": "test@example.com",
  "password": "password123",
  "full_name": "Test User"
}
```

**响应**:
```json
{
  "id": 1,
  "username": "testuser",
  "email": "test@example.com",
  "full_name": "Test User",
  "is_active": true,
  "is_superuser": false,
  "created_at": "2024-01-01T00:00:00"
}
```

### 2. 用户登录

```bash
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=testuser&password=password123
```

**响应**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**新特性**：登录接口现在会**同时设置 Cookie**，方便 Web 应用使用。

**Cookie 属性**：
- 名称：`token`
- HttpOnly：`True`（防止 JavaScript 访问，提高安全性）
- Secure：生产环境启用（只在 HTTPS 下传输）
- SameSite：`Lax`（防止 CSRF 攻击）

**使用方式**：
1. **Web 应用**：浏览器会自动携带 Cookie，无需手动设置 Header
   ```javascript
   // 登录后，后续请求自动携带 Cookie
   fetch('/api/v1/users/me', {
     credentials: 'include'  // 自动携带 Cookie
   })
   ```

2. **API 调用**：仍然可以使用 Header 方式
   ```javascript
   fetch('/api/v1/users/me', {
     headers: {
       'Authorization': 'Bearer ' + token
     }
   })
   ```

### 3. 访问需要认证的接口

```bash
GET /api/v1/auth/me
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**响应**:
```json
{
  "id": 1,
  "username": "testuser",
  "email": "test@example.com",
  "full_name": "Test User",
  "is_active": true,
  "is_superuser": false,
  "created_at": "2024-01-01T00:00:00"
}
```

## 三、依赖注入完整指南

系统提供了三类依赖注入，可以在任意接口中灵活组合使用。

### 1. 用户级别（认证）

#### `get_current_user` - 需要登录
验证 JWT Token，获取当前登录用户。如果用户未激活，会返回 403。

**新特性**：
- ✅ 支持从 **Cookie** 和 **Header** 两种方式获取 Token（优先级：Cookie > Header）
- ✅ 自动设置 `request.state.userinfo`，包含用户完整信息

```python
from app.dependencies.auth import get_current_user
from app.models.user import User

@router.get("/profile")
async def get_profile(
    current_user: User = Depends(get_current_user)
):
    return {"username": current_user.username}
```

**Token 获取方式**：
1. **Cookie**（Web 应用推荐）：浏览器自动携带
   ```javascript
   // 前端登录后，浏览器会自动携带 Cookie
   fetch('/api/v1/users/me', {
     credentials: 'include'  // 自动携带 Cookie
   })
   ```

2. **Header**（API 调用推荐）：手动设置 Authorization
   ```javascript
   // 前端手动设置 Header
   fetch('/api/v1/users/me', {
     headers: {
       'Authorization': 'Bearer your_token_here'
     }
   })
   ```

#### `get_current_active_user` - 需要登录且激活
在 `get_current_user` 基础上，额外确保用户已激活。

```python
from app.dependencies.auth import get_current_active_user

@router.get("/active-only")
async def active_only_route(
    current_user: User = Depends(get_current_active_user)
):
    # 只有激活用户才能访问
    pass
```

#### `require_superuser` - 需要超级用户
要求用户必须是超级用户（`is_superuser=True`）。

```python
from app.dependencies.auth import require_superuser

@router.delete("/system/reset")
async def reset_system(
    current_user: User = Depends(require_superuser)
):
    # 只有超级用户才能访问
    pass
```

#### `get_userinfo` - 从 request.state 获取用户信息（性能优化）
从 `request.state.userinfo` 获取用户信息，无需再查询数据库。

**使用前提**：必须先调用过 `get_current_user`（或其他会设置 `request.state.userinfo` 的依赖）

**优势**：
- ⚡ **性能更好**：不需要再查询数据库
- 📦 **信息完整**：包含用户ID、用户名、邮箱、是否超级用户等

```python
from app.dependencies.auth import get_userinfo

@router.get("/my-data")
async def get_my_data(userinfo: dict = Depends(get_userinfo)):
    # 直接使用，不需要再查询数据库
    user_id = userinfo["user_id"]
    username = userinfo["username"]
    email = userinfo["email"]
    is_superuser = userinfo["is_superuser"]
    
    return {
        "user_id": user_id,
        "username": username,
        "email": email,
        "is_superuser": is_superuser
    }
```

**userinfo 包含的字段**：
```python
{
    "user": User对象,        # 完整的 User 对象
    "user_id": int,          # 用户ID
    "username": str,         # 用户名
    "email": str,            # 邮箱
    "full_name": str | None, # 全名
    "is_active": bool,       # 是否激活
    "is_superuser": bool,    # 是否超级用户
}
```

### 2. 角色级别

#### `require_role(role_name)` - 需要特定角色
检查用户是否拥有指定角色。超级用户自动通过。

```python
from app.dependencies.permissions import require_role

@router.post("/admin/action")
async def admin_action(
    current_user: User = Depends(require_role("admin"))
):
    # 只有拥有 admin 角色的用户才能访问
    pass
```

### 3. 权限级别

#### `require_permission(permission_name)` - 需要特定权限
检查用户是否拥有指定权限。权限格式：`资源:操作`。超级用户和超级管理员角色自动通过。

```python
from app.dependencies.permissions import require_permission

@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: int,
    current_user: User = Depends(require_permission("posts:delete"))
):
    # 只有拥有 posts:delete 权限的用户才能访问
    pass
```

### 4. 组合使用

依赖注入支持链式调用，`require_permission` 和 `require_role` 内部已调用 `get_current_user`，因此会自动验证用户登录。

```python
# 需要登录 + 特定权限
@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    current_user: User = Depends(require_permission("users:write"))
):
    # require_permission 内部已调用 get_current_user
    pass

# 需要登录 + 特定角色
@router.get("/admin/dashboard")
async def admin_dashboard(
    current_user: User = Depends(require_role("admin"))
):
    pass
```

### 5. 路由级依赖（简化鉴权代码）

路由级依赖可以让整个路由组自动需要认证或权限，减少重复代码。

#### 示例 1：整个路由组都需要认证

```python
from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_user

# 所有这个路由下的接口都需要认证
protected_router = APIRouter(
    prefix="/protected",
    dependencies=[Depends(get_current_user)]  # 路由级依赖
)

@protected_router.get("/data")
async def get_data():
    # 不需要再写 Depends(get_current_user)
    return {"data": "protected data"}

@protected_router.post("/create")
async def create_data(data: dict):
    # 同样不需要写 Depends(get_current_user)
    return {"message": "created"}
```

#### 示例 2：需要特定权限的路由组

```python
from app.dependencies.permissions import require_permission

# 所有内容管理接口都需要 content:read 权限
content_router = APIRouter(
    prefix="/content",
    dependencies=[Depends(require_permission("content:read"))]
)

@content_router.get("/list")
async def list_content():
    # 自动需要 content:read 权限
    return {"contents": []}
```

#### 示例 3：混合使用（路由级 + 接口级）

```python
# 路由级：所有接口都需要登录
admin_router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(get_current_user)]  # 路由级：需要登录
)

@admin_router.get("/dashboard")
async def get_dashboard():
    # 只需要登录（路由级已处理）
    return {"dashboard": "data"}

@admin_router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    _: None = Depends(require_permission("users:delete"))  # 接口级：额外需要权限
):
    # 需要登录（路由级）+ 特定权限（接口级）
    return {"message": "deleted"}
```

#### 示例 4：使用 get_userinfo（性能优化）

```python
# 路由级：设置 userinfo
user_router = APIRouter(
    prefix="/users",
    dependencies=[Depends(get_current_user)]  # 这会设置 request.state.userinfo
)

@user_router.get("/my-data")
async def get_my_data(userinfo: dict = Depends(get_userinfo)):
    # 从 request.state 获取，无需再查数据库
    user_id = userinfo["user_id"]
    username = userinfo["username"]
    return {"user_id": user_id, "username": username}
```

**路由级依赖的优势**：
- ✅ **减少重复代码**：不需要在每个接口都写 `Depends(get_current_user)`
- ✅ **统一管理**：路由组级别的权限控制更清晰
- ✅ **灵活组合**：路由级 + 接口级可以组合使用

### 6. 公开接口（无需任何限制）

```python
@router.get("/public/posts")
async def get_public_posts():
    # 无需任何依赖注入
    return {"posts": []}
```

### 7. 资源所有权验证

```python
@router.put("/posts/{post_id}")
async def update_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 查询资源
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    
    if post is None:
        raise HTTPException(404, "资源不存在")
    
    # 验证所有权（或使用权限检查）
    if post.author_id != current_user.id:
        # 或者检查权限
        # if "posts:write" not in await get_user_permissions(current_user, db, redis):
        raise HTTPException(403, "无权访问此资源")
    
    # 更新逻辑
    pass
```

### 8. 自定义组合依赖

如果需要更复杂的逻辑，可以创建自定义依赖：

```python
# 在 dependencies 中创建
async def require_admin_or_editor(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """需要 admin 或 editor 角色"""
    if current_user.is_superuser:
        return current_user
    
    from app.dependencies.permissions import get_user_roles
    roles = await get_user_roles(current_user, db)
    role_names = {role.name for role in roles}
    
    if "admin" in role_names or "editor" in role_names:
        return current_user
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="需要 admin 或 editor 角色"
    )

# 使用
@router.post("/content/publish")
async def publish_content(
    current_user: User = Depends(require_admin_or_editor)
):
    pass
```

### 依赖注入总结表

| 依赖函数 | 类型 | 说明 | 自动验证登录 | 新特性 |
|---------|------|------|------------|--------|
| `get_current_user` | 用户 | 需要登录 | ✅ | ✅ Cookie/Header 双重支持<br>✅ 自动设置 userinfo<br>⚡ 性能优化（复用中间件结果） |
| `get_current_active_user` | 用户 | 需要登录且激活 | ✅ | ⚠️ 全局中间件已检查，提供更明确的语义 |
| `require_superuser` | 用户 | 需要超级用户 | ✅ | ✅ 异步函数 |
| `get_userinfo` | 用户信息 | 从 request.state 获取 | ✅ | ⚡ 性能优化<br>📦 无需再查数据库 |
| `require_role("role_name")` | 角色 | 需要特定角色 | ✅ | - |
| `require_permission("perm")` | 权限 | 需要特定权限 | ✅ | - |

**注意**：
- 所有依赖都会自动验证用户登录（通过 `get_current_user` 或全局中间件）
- 超级用户（`is_superuser=True`）自动拥有所有权限和角色
- 超级管理员角色（`is_super_admin=True`）自动拥有所有权限（`*`）
- `get_current_user` 支持从 **Cookie** 和 **Header** 获取 Token（优先级：Cookie > Header）
- `get_userinfo` 使用前提：必须先调用过 `get_current_user` 或全局中间件已设置 `request.state.userinfo`
- **性能优化**：如果全局中间件已经认证，`get_current_user` 会直接复用 `request.state.userinfo`，不重复查询数据库

## 五、全局认证中间件

系统已启用全局认证中间件，强制所有接口都需要认证（除了白名单）。

### 工作原理

1. **全局中间件先执行**：所有请求（除了白名单）都会经过认证检查
2. **自动设置 userinfo**：认证成功后，自动设置 `request.state.userinfo`
3. **依赖注入复用**：`get_current_user` 会检查 `request.state.userinfo`，如果存在则直接复用

### 白名单路径

以下路径不需要认证：
- `/` - 根路径
- `/health` - 健康检查
- `/docs`, `/openapi.json`, `/redoc` - API 文档
- `/api/v1/auth/*` - 认证相关接口（登录、注册等）

### 使用方式

**方式 1：直接使用 request.state.userinfo（最简单）**

```python
@router.get("/my-data")
async def get_my_data(request: Request):
    # 全局中间件已经认证并设置了 userinfo
    userinfo = request.state.userinfo
    user_id = userinfo["user_id"]
    username = userinfo["username"]
    return {"user_id": user_id, "username": username}
```

**方式 2：使用 Depends(get_userinfo)（推荐）**

```python
from app.dependencies.auth import get_userinfo

@router.get("/my-data")
async def get_my_data(userinfo: dict = Depends(get_userinfo)):
    # 从 request.state 获取，有错误处理
    user_id = userinfo["user_id"]
    return {"user_id": user_id}
```

**方式 3：使用 Depends(get_current_user)（如果需要完整 User 对象）**

```python
from app.dependencies.auth import get_current_user

@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    # 如果中间件已认证，不会重复查询数据库
    return current_user
```

### 性能优势

- ✅ **认证一次，全局复用**：全局中间件认证后，所有依赖都复用结果
- ✅ **避免重复查询**：`get_current_user` 会检查 `request.state.userinfo`，避免重复查询数据库
- ✅ **统一管理**：所有接口统一认证，无需在每个路由写依赖

### 禁用全局中间件

如果需要禁用全局中间件（例如某些接口不需要认证），可以：

1. **修改白名单**：在 `app/middleware/global_auth.py` 中添加路径到 `NO_AUTH_PATHS` 或 `NO_AUTH_PREFIXES`
2. **注释中间件**：在 `app/main.py` 中注释掉 `app.add_middleware(GlobalAuthMiddleware)`


## 四、RBAC 管理操作

### 创建权限

```bash
POST /api/v1/permissions/
{
  "name": "posts:read",
  "resource": "posts",
  "action": "read",
  "description": "查看文章"
}
```

### 创建角色

```bash
POST /api/v1/roles/
{
  "name": "author",
  "description": "作者",
  "is_super_admin": false,
  "permission_ids": [1, 2, 3]
}
```

### 给用户分配角色

```bash
POST /api/v1/users/{user_id}/roles
{
  "role_ids": [1, 2]
}
```

### 给角色分配权限

```bash
POST /api/v1/roles/{role_id}/permissions/{permission_id}
```

## 五、待实现的功能

❌ **高级功能**
- Refresh Token
- Token 黑名单（登出）
- 密码重置
- 邮箱验证
- 登录历史记录
- 速率限制（Rate Limiting）

❌ **安全增强**
- 登录失败次数限制
- IP 白名单/黑名单
- 设备指纹识别
- 异常登录检测

## 六、测试

### 使用 curl 测试

```bash
# 1. 注册用户
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123",
    "full_name": "Test User"
  }'

# 2. 登录
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=password123"

# 3. 获取用户信息（使用返回的 token）
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## 三、邮箱验证和密码重置示例

### 1. 邮箱验证流程

#### 注册时自动发送验证邮件

用户注册后，系统会自动发送验证邮件到用户邮箱。

```bash
# 1. 用户注册
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123",
    "full_name": "Test User"
  }'

# 响应: 用户创建成功，验证邮件已发送
```

#### 验证邮箱（GET方式 - 直接通过浏览器访问）

用户点击邮件中的验证链接，浏览器直接访问后端API：

```bash
# 用户点击邮件中的链接:
# http://localhost:8000/api/v1/auth/verify-email?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# 浏览器自动访问，后端返回HTML页面显示验证结果
```

#### 验证邮箱（POST方式 - 前端API调用）

前端页面可以调用API验证邮箱：

```bash
curl -X POST "http://localhost:8000/api/v1/auth/verify-email" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }'

# 响应:
# {
#   "message": "邮箱验证成功"
# }
```

#### 重新发送验证邮件

如果用户没有收到验证邮件，可以重新发送：

```bash
curl -X POST "http://localhost:8000/api/v1/auth/resend-verification-email" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"

# 响应:
# {
#   "message": "验证邮件已发送，请查收邮箱"
# }
```

### 2. 密码重置流程

#### 忘记密码（发送重置邮件）

用户忘记密码时，请求发送重置邮件：

```bash
curl -X POST "http://localhost:8000/api/v1/auth/forgot-password" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com"
  }'

# 响应（无论邮箱是否存在都返回成功，防止邮箱枚举）:
# {
#   "message": "如果该邮箱已注册, 密码重置邮件已发送，请查收邮箱"
# }
```

#### 密码重置页面（GET方式 - 显示表单）

用户点击邮件中的重置链接，浏览器打开重置表单页面：

```bash
# 用户点击邮件中的链接:
# http://localhost:8000/api/v1/auth/reset-password-page?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# 浏览器自动访问，后端返回HTML表单页面
# 用户在表单中输入新密码并提交
```

#### 重置密码（POST方式 - 提交新密码）

用户提交新密码：

```bash
curl -X POST "http://localhost:8000/api/v1/auth/reset-password" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "new_password": "newpassword123"
  }'

# 响应:
# {
#   "message": "密码重置成功，请使用新密码登录"
# }
```

### 3. 配置SMTP服务

在使用邮箱验证和密码重置功能前，需要在`.env`文件中配置SMTP服务：

```env
# Gmail 示例配置
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Gmail应用专用密码
SMTP_FROM_EMAIL=your-email@gmail.com
SMTP_FROM_NAME=FastAPI Server
SMTP_USE_TLS=true
FRONTEND_URL=http://localhost:8000  # 或你的前端地址
```

**Gmail配置步骤**：
1. 启用两步验证
2. 生成应用专用密码：https://myaccount.google.com/apppasswords
3. 使用应用专用密码作为 `SMTP_PASSWORD`

### 使用 FastAPI 文档测试

访问 `http://localhost:8000/docs`，在 Swagger UI 中测试接口。

