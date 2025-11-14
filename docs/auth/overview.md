# 后端鉴权体系完整说明

## 一、核心概念

### 1. 认证（Authentication）- "你是谁"
**目的**: 验证用户身份，确认用户是否已登录

**常见方式**:
- **JWT (JSON Web Token)**: 无状态，适合分布式系统
- **Session**: 有状态，服务器存储会话信息
- **OAuth 2.0**: 第三方登录（Google, GitHub等）
- **API Key**: 简单的服务间认证

### 2. 授权（Authorization）- "你能做什么"
**目的**: 控制用户能访问哪些资源，执行哪些操作

**常见模型**:
- **RBAC (Role-Based Access Control)**: 基于角色的访问控制
- **ABAC (Attribute-Based Access Control)**: 基于属性的访问控制
- **ACL (Access Control List)**: 访问控制列表
- **权限位**: 使用位掩码表示权限

## 二、完整的鉴权体系组件

### 1. 用户管理
- ✅ 用户注册
- ✅ 用户登录（用户名/密码、邮箱/密码）
- ✅ 密码加密存储（bcrypt）
- ✅ 用户信息管理
- ✅ **邮箱验证**（注册时自动发送验证邮件，24小时有效期）
- ✅ **密码重置**（忘记密码，通过邮箱重置，1小时有效期）

### 2. 认证机制
- ✅ JWT Token 生成和验证
- ✅ **Cookie 和 Header 双重认证支持**（优先级：Cookie > Header）
- ✅ **request.state.userinfo**（请求级用户信息缓存，自动更新）
- ✅ **全局认证中间件**（强制所有接口都需要认证，除了白名单）
- ✅ **性能优化**（全局中间件和依赖注入协作，避免重复查询数据库）
- ✅ **Token 刷新机制（Refresh Token）**（双 Token 机制，Access Token 短期 + Refresh Token 长期）
- ✅ **Token 黑名单**（登出时使Token失效，Redis 存储）
- ✅ **多设备登录管理**（查看设备列表、撤销特定设备、撤销所有设备）
- ✅ **登录历史记录**（记录设备信息、IP地址、登录时间等）

### 3. 权限控制（RBAC）
- ✅ 角色管理（Role）
- ✅ 权限管理（Permission）
- ✅ 角色-权限关联
- ✅ 用户-角色关联
- ✅ 接口权限依赖注入
- ✅ Redis 权限缓存优化
- ✅ 数据权限控制（用户只能访问自己的数据）

### 4. 接口保护
- ✅ 公开接口（无需认证）
- ✅ 需要登录的接口（需要Token）
- ✅ 需要特定权限的接口
- ✅ 需要特定角色的接口
- ✅ 资源所有权验证（用户只能访问自己的数据）
- ✅ **路由级依赖**（整个路由组统一鉴权，减少重复代码）

### 5. 安全机制
- ✅ 密码强度验证
- ✅ 登录失败次数限制（防暴力破解）
- ✅ 速率限制（Rate Limiting）
- ✅ CORS 配置
- ✅ CSRF 保护（如果使用Session）
- ✅ SQL 注入防护（ORM自动处理）
- ✅ XSS 防护（输入验证和输出转义）
- ✅ HTTPS 强制（生产环境）

### 6. 其他安全功能
- ✅ 操作日志记录（审计）
- ✅ 敏感操作二次验证
- ✅ IP 白名单/黑名单
- ✅ 设备指纹识别
- ✅ 异常登录检测

## 三、实现架构

### 目录结构
```
app/
├── core/
│   ├── security.py      # JWT、密码加密等安全工具
│   └── redis.py         # Redis 连接管理（权限缓存）
├── models/
│   ├── user.py          # 用户模型
│   ├── role.py          # 角色模型
│   ├── permission.py    # 权限模型
│   └── association.py  # 关联表（用户-角色、角色-权限）
├── schemas/
│   ├── auth.py          # 认证相关的 Pydantic 模型
│   ├── user.py          # 用户相关的 Pydantic 模型
│   ├── role.py          # 角色相关的 Pydantic 模型
│   └── permission.py    # 权限相关的 Pydantic 模型
├── routers/
│   ├── auth.py          # 认证路由（登录、注册）
│   ├── users.py         # 用户管理路由
│   ├── roles.py         # 角色管理路由
│   └── permissions.py   # 权限管理路由
└── dependencies/
    ├── auth.py          # 认证依赖注入（用户验证）
    ├── permissions.py   # 权限依赖注入（角色、权限检查）
    └── cache.py         # 缓存管理工具（清除用户权限缓存）
```

## 四、数据模型设计

### 用户表 (users)
- id: 主键
- username: 用户名（唯一）
- email: 邮箱（唯一）
- hashed_password: 加密后的密码
- is_active: 是否激活
- is_superuser: 是否超级用户
- **email_verified: 邮箱是否已验证**（新增字段）
- created_at: 创建时间
- updated_at: 更新时间

### 角色表 (roles)
- id: 主键
- name: 角色名称（唯一，如 "admin", "editor", "viewer"）
- description: 角色描述
- is_super_admin: 是否为超级管理员角色（拥有所有权限）
- created_at: 创建时间
- updated_at: 更新时间

### 权限表 (permissions)
- id: 主键
- name: 权限名称（唯一，格式：资源:操作，如 "users:read", "users:write"）
- resource: 资源名称（如 "users", "posts", "content"）
- action: 操作（如 "read", "write", "delete", "manage"）
- description: 权限描述
- created_at: 创建时间

### 关联表
- user_roles: 用户-角色关联表（多对多）
- role_permissions: 角色-权限关联表（多对多）

### 权限层级
1. **超级用户（is_superuser=True）**: 拥有所有权限，不受角色限制
2. **超级管理员角色（is_super_admin=True）**: 拥有所有权限（返回 `*` 通配符）
3. **普通角色**: 通过分配的权限获得访问能力

## 五、依赖注入系统

系统提供了完整的依赖注入机制，可以在任意接口中灵活组合使用。详见 [使用示例](./examples.md#依赖注入完整指南)。

### 可用的依赖注入函数

#### 用户级别（认证）
- `get_current_user` - 需要登录（验证 Token，支持 Cookie 和 Header）
  - 自动设置 `request.state.userinfo`，包含用户完整信息
  - 支持从 Cookie 和 Header (Authorization Bearer) 获取 Token
  - 优先级：Cookie > Header
  - **性能优化**：如果全局中间件已经认证，直接复用 `request.state.userinfo`，不重复查询数据库
- `get_current_active_user` - 需要登录且用户已激活（异步函数）
  - ⚠️ **注意**：全局中间件已检查 `is_active`，此函数提供更明确的语义
- `require_superuser` - 需要超级用户（`is_superuser=True`，异步函数）
- `get_userinfo` - 从 `request.state` 获取用户信息（性能优化，无需再查数据库）

#### 角色级别
- `require_role("role_name")` - 需要特定角色

#### 权限级别
- `require_permission("permission_name")` - 需要特定权限（格式：`资源:操作`）

### 全局认证中间件

系统已启用全局认证中间件（`GlobalAuthMiddleware`），强制所有接口都需要认证（除了白名单）。

**工作流程**：
1. 请求到达 → 检查是否在白名单中
2. 如果在白名单 → 直接通过，不进行认证
3. 如果不在白名单 → 获取 Token（Cookie 或 Header）
4. 验证 Token → 查询用户 → 检查用户状态
5. 认证成功 → 设置 `request.state.userinfo`
6. 继续处理请求 → 路由和依赖注入可以使用 `request.state.userinfo`

**与依赖注入的协作**：
- 全局中间件先执行认证，设置 `request.state.userinfo`
- `get_current_user` 检查 `request.state.userinfo` 是否存在
- 如果存在，直接复用，**不重复查询数据库**（性能优化）
- 如果不存在，执行认证并设置 `request.state.userinfo`

**白名单配置**：
- 完整路径：`/`, `/health`, `/docs`, `/openapi.json`, `/redoc`
- 路径前缀：`/docs/`, `/api/v1/auth/`（包括登录、注册、刷新 Token 等）

### Refresh Token 机制

系统实现了完整的 Refresh Token 机制，提供更安全的认证体验。

#### 双 Token 架构

- **Access Token（访问令牌）**：
  - 过期时间：默认 30 分钟（可通过 `ACCESS_TOKEN_EXPIRE_MINUTES` 配置）
  - 用途：用于访问受保护的 API 接口
  - 存储：Cookie（`token`）和响应体
  - 特点：短期有效，降低被盗用风险

- **Refresh Token（刷新令牌）**：
  - 过期时间：默认 30 天（可通过 `REFRESH_TOKEN_EXPIRE_DAYS` 配置）
  - 用途：用于刷新 Access Token
  - 存储：Cookie（`refresh_token`）和响应体
  - 特点：长期有效，但可以随时撤销

#### Token 刷新流程

1. Access Token 过期 → 客户端收到 401 错误
2. 客户端自动调用 `/api/v1/auth/refresh` 接口
3. 服务端验证 Refresh Token 有效性
4. 检查 Refresh Token 是否在黑名单中
5. 生成新的 Access Token
6. 返回新的 Access Token（Refresh Token 保持不变）

#### Token 存储机制

- **Redis 存储**（主要）：
  - Key: `refresh_token:{token_hash}`
  - Value: Token 信息（用户ID、用户名、设备信息等）
  - TTL: 与 Refresh Token 过期时间一致
  - 用途：快速验证和撤销

- **数据库存储**（持久化）：
  - 表：`refresh_tokens`
  - 字段：token_hash、user_id、设备信息、IP地址、登录时间等
  - 用途：登录历史记录、设备管理

#### Token 黑名单机制

- **存储位置**：Redis
- **Key 格式**：`token_blacklist:{token_hash}`
- **触发场景**：
  - 用户主动登出
  - 密码修改
  - 用户被禁用
  - 手动撤销设备

#### 多设备登录管理

系统支持多设备同时登录，并提供完整的管理功能：

- **查看所有设备**：`GET /api/v1/auth/devices`
  - 返回所有有效的登录设备信息
  - 包括设备类型、IP地址、登录时间等

- **撤销特定设备**：`DELETE /api/v1/auth/devices/{device_id}`
  - 撤销指定设备的 Refresh Token
  - 该设备需要重新登录

- **撤销所有设备**：`POST /api/v1/auth/devices/revoke-all`
  - 撤销所有设备的 Refresh Token
  - 用户需要重新登录

#### 登录历史记录

系统自动记录每次登录的详细信息：

- **设备信息**：
  - 设备类型（web、mobile、tablet、desktop）
  - 设备名称（User-Agent）
  - User-Agent 字符串

- **网络信息**：
  - IP 地址
  - 登录时间
  - 过期时间

- **状态信息**：
  - Token 是否已撤销
  - 撤销时间

#### 安全特性

1. **Token 哈希存储**：存储 Token 的 SHA256 哈希值，不存储明文
2. **独立密钥支持**：Refresh Token 可使用独立的密钥（`REFRESH_TOKEN_SECRET_KEY`）
3. **自动过期清理**：Redis 和数据库中的过期 Token 会自动清理
4. **密码修改保护**：修改密码时自动撤销所有 Refresh Token
5. **设备识别**：通过 User-Agent 和 IP 地址识别设备

#### API 接口

- `POST /api/v1/auth/login` - 登录（返回 Access Token + Refresh Token）
- `POST /api/v1/auth/refresh` - 刷新 Access Token
- `POST /api/v1/auth/logout` - 登出（撤销 Refresh Token）
- `GET /api/v1/auth/devices` - 获取设备列表
- `DELETE /api/v1/auth/devices/{device_id}` - 撤销指定设备
- `POST /api/v1/auth/devices/revoke-all` - 撤销所有设备
- `POST /api/v1/users/me/change-password` - 修改密码（自动撤销所有 Token）
- `GET /api/v1/auth/verify-email?token=xxx` - 验证邮箱（GET方式，直接通过浏览器访问）
- `POST /api/v1/auth/verify-email` - 验证邮箱（POST方式，供前端API调用）
- `POST /api/v1/auth/resend-verification-email` - 重新发送验证邮件
- `POST /api/v1/auth/forgot-password` - 忘记密码（发送重置邮件）
- `GET /api/v1/auth/reset-password-page?token=xxx` - 密码重置页面（GET方式，显示重置表单）
- `POST /api/v1/auth/reset-password` - 重置密码（POST方式，提交新密码）

### 权限检查流程

1. **超级用户检查**：如果用户是超级用户（`is_superuser=True`），直接通过
2. **Redis 缓存查询**：从缓存中查询用户权限（缓存 1 小时）
3. **数据库查询**：如果缓存未命中，从数据库查询用户的所有角色和权限
4. **超级管理员角色检查**：如果用户拥有超级管理员角色（`is_super_admin=True`），返回 `*`（所有权限）
5. **权限收集**：收集用户所有角色的权限
6. **权限验证**：检查用户是否拥有所需权限或 `*` 通配符

### 缓存更新机制

系统使用两种缓存机制来优化性能：

#### 1. request.state.userinfo（请求级缓存）
- **特点**：只在单个请求生命周期内有效，请求结束后自动清除
- **更新机制**：✅ **自动更新** - 每次请求都会重新查询数据库并设置
- **优势**：无需手动管理，总是最新的数据
- **使用场景**：在同一个请求中多次获取用户信息时，避免重复查询数据库

#### 2. Redis 权限缓存（持久化缓存）
- **特点**：存储在 Redis 中，跨请求持久化，默认缓存 1 小时
- **更新机制**：⚠️ **需要手动清除** - 在相关数据变化时清除缓存
- **缓存键**：`user_permissions:{user_id}`
- **自动清除场景**：
  - ✅ 用户角色变化（分配/移除角色）
  - ✅ 角色权限变化（分配/移除权限）
  - ✅ 角色信息更新（is_super_admin 等）
  - ✅ 角色删除
  - ✅ 用户状态变化（is_active）

**缓存清除函数**：
- `clear_user_permissions_cache(user_id, redis)` - 清除单个用户的权限缓存
- `clear_role_users_cache(role)` - 清除所有拥有指定角色的用户的权限缓存

## 六、最佳实践

1. **最小权限原则**: 默认拒绝，明确允许
2. **Token 过期时间**: 
   - Access Token：15-30分钟（高安全要求）或 30-60分钟（一般应用）
   - Refresh Token：7-30天（根据安全需求调整）
3. **密码策略**: 至少8位，包含大小写字母、数字、特殊字符
4. **日志记录**: 记录所有认证和授权相关的操作
5. **错误信息**: 不暴露敏感信息（如"用户不存在"vs"用户名或密码错误"）
6. **HTTPS**: 生产环境必须使用 HTTPS
7. **Token 存储**: 
   - Access Token：使用 httpOnly Cookie 或内存存储
   - Refresh Token：使用 httpOnly Cookie（推荐）或安全存储
   - 不要使用 localStorage 存储敏感 Token
8. **Token 刷新**: 客户端应在 Access Token 过期前自动刷新
9. **设备管理**: 定期检查和管理登录设备，及时撤销可疑设备
10. **密码安全**: 修改密码后会自动撤销所有 Token，确保安全性

## 六、RBAC 系统初始化

### 默认角色和权限

系统初始化时会创建以下默认角色和权限：

**默认权限**：
- 用户管理：`users:read`, `users:write`, `users:delete`, `users:manage`
- 角色管理：`roles:read`, `roles:write`, `roles:delete`, `roles:manage`
- 权限管理：`permissions:read`, `permissions:write`, `permissions:delete`, `permissions:manage`
- 内容管理：`content:read`, `content:write`, `content:delete`, `content:manage`
- 系统管理：`system:read`, `system:write`, `system:manage`

**默认角色**：
1. **super_admin**: 超级管理员（拥有所有权限）
2. **admin**: 管理员（拥有大部分管理权限）
3. **editor**: 编辑（可以管理内容）
4. **viewer**: 查看者（只能查看）

### 初始化步骤

```bash
# 1. 初始化 RBAC 系统（创建默认角色和权限）
python scripts/init_rbac.py

# 2. 创建超级用户
python scripts/create_superuser.py admin admin@example.com password123
```

## 七、邮箱验证和密码重置功能

### 邮箱验证功能

系统实现了完整的邮箱验证机制，确保用户邮箱的有效性。

#### 功能特点
- ✅ 注册时自动发送验证邮件
- ✅ 24小时有效期（Token过期时间）
- ✅ 支持重新发送验证邮件
- ✅ 支持纯后端完成（不需要前端）
- ✅ 支持前端页面配合（可选）

#### 工作流程
1. 用户注册 → 后端创建用户（`email_verified=False`）
2. 后端生成验证Token（包含user_id、email、type="email_verification"）
3. 后端通过SMTP发送验证邮件
4. 用户点击邮件中的验证链接
5. 后端验证Token，更新`email_verified=True`

#### 配置要求
需要在`.env`文件中配置SMTP相关环境变量：
```env
SMTP_HOST=smtp.gmail.com          # SMTP服务器地址
SMTP_PORT=587                     # SMTP端口
SMTP_USER=your-email@gmail.com    # SMTP用户名
SMTP_PASSWORD=your-app-password   # SMTP密码或应用专用密码
SMTP_FROM_EMAIL=your-email@gmail.com  # 发件人邮箱
SMTP_FROM_NAME=FastAPI Server     # 发件人名称
SMTP_USE_TLS=true                 # 是否使用TLS
FRONTEND_URL=http://localhost:8000  # 前端URL或后端API URL
```

#### API接口
- `GET /api/v1/auth/verify-email?token=xxx` - 验证邮箱（GET方式，返回HTML页面）
- `POST /api/v1/auth/verify-email` - 验证邮箱（POST方式，返回JSON）
- `POST /api/v1/auth/resend-verification-email` - 重新发送验证邮件

### 密码重置功能

系统实现了安全的密码重置机制，通过邮箱验证身份。

#### 功能特点
- ✅ 忘记密码时发送重置邮件
- ✅ 1小时有效期（Token过期时间，比验证Token更短）
- ✅ 重置后自动撤销所有登录Token（强制重新登录）
- ✅ 邮箱枚举防护（无论邮箱是否存在都返回成功消息）
- ✅ 支持纯后端完成（不需要前端）
- ✅ 支持前端页面配合（可选）

#### 工作流程
1. 用户请求重置密码 → 提供邮箱地址
2. 后端查询用户，生成重置Token（包含user_id、email、type="password_reset"）
3. 后端通过SMTP发送重置邮件
4. 用户点击邮件中的重置链接
5. 后端返回密码重置表单页面（HTML + JavaScript）
6. 用户输入新密码并提交
7. 后端验证Token，更新密码，撤销所有Refresh Token

#### 安全机制
- Token包含邮箱匹配验证，防止邮箱变更后的误用
- Token类型验证，防止验证Token被用于重置密码
- 重置后撤销所有Token，强制用户重新登录
- 邮箱枚举防护，防止恶意用户通过此接口枚举邮箱

#### API接口
- `POST /api/v1/auth/forgot-password` - 忘记密码（发送重置邮件）
- `GET /api/v1/auth/reset-password-page?token=xxx` - 密码重置页面（GET方式，显示表单）
- `POST /api/v1/auth/reset-password` - 重置密码（POST方式，提交新密码）

### 邮件服务配置

系统支持任何SMTP服务器，包括：
- **Gmail**: `smtp.gmail.com:587`（需要应用专用密码）
- **Outlook**: `smtp.office365.com:587`
- **QQ邮箱**: `smtp.qq.com:587`（需要授权码）
- **163邮箱**: `smtp.163.com:25`或`465`
- **第三方服务**: SendGrid、Mailgun、AWS SES等

详细配置说明请参考代码注释和配置文件。

## 八、当前项目状态

✅ **已实现**:
- 用户注册和登录
- JWT Token 生成和验证
- **Refresh Token 机制**（双 Token 架构）
- **Token 刷新接口**
- **Token 黑名单机制**（登出、密码修改时撤销）
- **多设备登录管理**（查看、撤销设备）
- **登录历史记录**（设备信息、IP地址、登录时间）
- 密码加密存储（bcrypt）
- **密码修改接口**（自动撤销所有 Token）
- **邮箱验证功能**（注册时自动发送验证邮件）
- **密码重置功能**（忘记密码，通过邮箱重置）
- RBAC 权限系统（角色、权限管理）
- 依赖注入系统（用户、角色、权限检查）
- Redis 权限缓存优化
- 用户、角色、权限管理 API

❌ **待实现**:
- 速率限制（Rate Limiting）
- 登录失败次数限制
- Token 刷新时的轮换机制（可选）

