# 认证系统运转详解

## 一、系统架构概览

```
┌─────────────┐
│   客户端     │ (浏览器/移动端/API客户端)
└──────┬──────┘
       │ HTTP 请求
       ▼
┌─────────────────────────────────────┐
│         FastAPI 应用层               │
│  ┌───────────────────────────────┐ │
│  │   路由层 (routers/auth.py)     │ │
│  │   - /register                  │ │
│  │   - /login                     │ │
│  │   - /me                        │ │
│  └───────────┬───────────────────┘ │
│              │                      │
│  ┌───────────▼───────────────────┐ │
│  │  依赖注入层 (dependencies)     │ │
│  │   - get_current_user           │ │
│  │   - get_current_active_user    │ │
│  │   - require_superuser          │ │
│  └───────────┬───────────────────┘ │
│              │                      │
│  ┌───────────▼───────────────────┐ │
│  │  安全工具层 (core/security)   │ │
│  │   - 密码加密/验证              │ │
│  │   - JWT 生成/验证               │ │
│  └───────────┬───────────────────┘ │
└──────────────┼─────────────────────┘
               │
       ┌───────┴───────┐
       │               │
       ▼               ▼
┌──────────┐    ┌──────────┐
│PostgreSQL│    │  Redis   │
│ 数据库    │    │  (可选)  │
└──────────┘    └──────────┘
```

## 二、核心组件说明

### 1. **安全工具层** (`app/core/security.py`)

这是系统的"安全工具箱"，提供三个核心功能：

#### a) 密码加密 (`get_password_hash`)
```python
# 使用 bcrypt 算法加密密码
hashed = get_password_hash("password123")
# 结果: "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5Gy..."
```

**工作原理**:
- 使用 `passlib` 库的 `bcrypt` 算法
- bcrypt 是单向哈希函数，无法逆向解密
- 每次加密结果都不同（因为使用了随机盐值）
- 即使密码相同，加密结果也不同

#### b) 密码验证 (`verify_password`)
```python
# 验证明文密码是否匹配加密后的密码
is_valid = verify_password("password123", hashed_password)
# 返回: True 或 False
```

**工作原理**:
- bcrypt 会提取加密字符串中的盐值
- 用相同的盐值加密输入的明文密码
- 比较结果是否一致

#### c) JWT Token 生成 (`create_access_token`)
```python
token = create_access_token(data={"sub": "username"})
# 结果: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**JWT Token 结构**:
```
Header.Payload.Signature

Header (头部):
{
  "alg": "HS256",  // 签名算法
  "typ": "JWT"     // Token 类型
}

Payload (载荷):
{
  "sub": "username",           // 用户名（subject）
  "exp": 1234567890,          // 过期时间（expiration）
  "iat": 1234567800           // 签发时间（issued at）
}

Signature (签名):
HMACSHA256(
  base64UrlEncode(header) + "." + base64UrlEncode(payload),
  SECRET_KEY
)
```

**工作原理**:
1. 将用户信息（用户名）编码到 Payload 中
2. 添加过期时间（默认30分钟）
3. 使用 `SECRET_KEY` 对 Header + Payload 进行签名
4. 签名确保 Token 未被篡改

#### d) JWT Token 验证 (`decode_access_token`)
```python
payload = decode_access_token(token)
# 返回: {"sub": "username", "exp": 1234567890, "iat": 1234567800}
# 或: None (如果 Token 无效)
```

**验证步骤**:
1. 解析 Token 的三个部分（Header.Payload.Signature）
2. 使用 `SECRET_KEY` 重新计算签名
3. 比较计算出的签名和 Token 中的签名
4. 检查过期时间（`exp`）
5. 如果签名匹配且未过期，返回 Payload；否则返回 None

### 2. **数据模型层** (`app/models/user.py`)

定义了用户数据库表结构：

```python
users 表:
- id: 主键
- username: 用户名（唯一索引）
- email: 邮箱（唯一索引）
- hashed_password: 加密后的密码
- full_name: 全名
- is_active: 是否激活
- is_superuser: 是否超级用户
- created_at: 创建时间
- updated_at: 更新时间
```

### 3. **请求/响应模型** (`app/schemas/auth.py`)

使用 Pydantic 进行数据验证：

- `UserRegister`: 注册请求（验证用户名长度、邮箱格式、密码长度）
- `UserResponse`: 用户响应（自动从数据库模型转换）
- `Token`: Token 响应格式

## 三、完整流程详解

### 流程 1: 用户注册

```
客户端请求
    │
    ▼
POST /api/v1/auth/register
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "password123",
  "full_name": "Alice Smith"
}
    │
    ▼
[路由层] app/routers/auth.py::register()
    │
    ├─► 1. 验证请求数据 (Pydantic)
    │      - 用户名长度 3-50
    │      - 邮箱格式正确
    │      - 密码长度 >= 6
    │
    ├─► 2. 检查用户名是否已存在
    │      SELECT * FROM users WHERE username = 'alice'
    │      └─► 如果存在 → 返回 400 错误
    │
    ├─► 3. 检查邮箱是否已存在
    │      SELECT * FROM users WHERE email = 'alice@example.com'
    │      └─► 如果存在 → 返回 400 错误
    │
    ├─► 4. 加密密码
    │      hashed_password = get_password_hash("password123")
    │      └─► 调用 security.py::get_password_hash()
    │          └─► 使用 bcrypt 加密
    │
    ├─► 5. 创建用户对象
    │      User(
    │        username="alice",
    │        email="alice@example.com",
    │        hashed_password="$2b$12$...",
    │        is_active=True,
    │        is_superuser=False
    │      )
    │
    ├─► 6. 保存到数据库
    │      db.add(user)
    │      db.commit()
    │      └─► INSERT INTO users VALUES (...)
    │
    └─► 7. 返回用户信息（不包含密码）
         {
           "id": 1,
           "username": "alice",
           "email": "alice@example.com",
           ...
         }
```

### 流程 2: 用户登录

```
客户端请求
    │
    ▼
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded
username=alice&password=password123
    │
    ▼
[路由层] app/routers/auth.py::login()
    │
    ├─► 1. FastAPI 自动解析表单数据
    │      form_data.username = "alice"
    │      form_data.password = "password123"
    │
    ├─► 2. 查询用户（支持用户名或邮箱）
    │      SELECT * FROM users 
    │      WHERE username = 'alice' OR email = 'alice'
    │      └─► 如果不存在 → 返回 401 错误
    │
    ├─► 3. 验证密码
    │      verify_password("password123", user.hashed_password)
    │      └─► 调用 security.py::verify_password()
    │          └─► 使用 bcrypt 验证
    │      └─► 如果不匹配 → 返回 401 错误
    │
    ├─► 4. 检查用户状态
    │      if not user.is_active:
    │          └─► 返回 403 错误（用户被禁用）
    │
    ├─► 5. 生成 JWT Token
    │      create_access_token(data={"sub": "alice"})
    │      └─► 调用 security.py::create_access_token()
    │          ├─► 创建 Payload: {"sub": "alice", "exp": ..., "iat": ...}
    │          ├─► 使用 SECRET_KEY 签名
    │          └─► 返回: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    │
    └─► 6. 返回 Token
         {
           "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
           "token_type": "bearer"
         }
```

### 流程 3: 访问受保护接口

```
客户端请求
    │
    ▼
GET /api/v1/auth/me
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    │
    ▼
[路由层] app/routers/auth.py::get_current_user_info()
    │
    ├─► 1. FastAPI 依赖注入系统启动
    │      current_user = Depends(get_current_active_user)
    │      │
    │      └─► 调用依赖链:
    │          get_current_active_user()
    │          └─► get_current_user()
    │              └─► oauth2_scheme (自动提取 Token)
    │
    ▼
[依赖注入层] app/dependencies/auth.py
    │
    ├─► 1. OAuth2PasswordBearer 自动提取 Token
    │      oauth2_scheme = OAuth2PasswordBearer(...)
    │      └─► 从请求头提取: Authorization: Bearer <token>
    │      └─► 如果没有 Token → 返回 401 错误
    │
    ├─► 2. 解码 Token
    │      decode_access_token(token)
    │      └─► 调用 security.py::decode_access_token()
    │          ├─► 验证签名（使用 SECRET_KEY）
    │          ├─► 检查过期时间
    │          └─► 返回 Payload 或 None
    │      └─► 如果无效 → 返回 401 错误
    │
    ├─► 3. 从 Token 中提取用户名
    │      username = payload.get("sub")
    │      └─► 如果不存在 → 返回 401 错误
    │
    ├─► 4. 从数据库查询用户
    │      SELECT * FROM users WHERE username = 'alice'
    │      └─► 如果不存在 → 返回 401 错误
    │
    ├─► 5. 检查用户状态
    │      if not user.is_active:
    │          └─► 返回 403 错误
    │
    ├─► 6. 返回用户对象
    │      return user
    │
    ▼
[路由层] 继续执行
    │
    └─► 7. 返回用户信息
         return current_user
         └─► FastAPI 自动转换为 UserResponse 格式
```

## 四、依赖注入系统详解

FastAPI 的依赖注入是这套系统的核心机制：

### 依赖链示例

```python
@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    return current_user
```

**执行顺序**:
```
1. FastAPI 看到 Depends(get_current_active_user)
2. 调用 get_current_active_user()
   │
   ├─► 发现它依赖 get_current_user
   │   └─► 调用 get_current_user()
   │       │
   │       ├─► 发现它依赖 oauth2_scheme
   │       │   └─► 调用 oauth2_scheme()
   │       │       └─► 从请求头提取 Token
   │       │
   │       ├─► 发现它依赖 get_db
   │       │   └─► 调用 get_db()
   │       │       └─► 创建数据库会话
   │       │
   │       └─► 验证 Token 并查询用户
   │
   └─► 检查用户是否激活
       └─► 返回用户对象
```

### 依赖注入的优势

1. **自动执行**: 无需手动调用，FastAPI 自动处理
2. **可复用**: 同一个依赖可以在多个路由中使用
3. **可组合**: 依赖可以依赖其他依赖
4. **类型安全**: 自动类型检查和 IDE 提示

## 五、安全机制

### 1. 密码安全
- ✅ 使用 bcrypt 加密（不可逆）
- ✅ 每次加密使用随机盐值
- ✅ 密码不存储在数据库中（只存储哈希值）

### 2. Token 安全
- ✅ 使用 HMAC-SHA256 签名（防止篡改）
- ✅ 包含过期时间（防止长期有效）
- ✅ 使用强密钥（SECRET_KEY）

### 3. 接口安全
- ✅ Token 验证（每个请求都验证）
- ✅ 用户状态检查（禁用用户无法访问）
- ✅ 权限检查（超级用户权限）

### 4. 数据验证
- ✅ Pydantic 自动验证请求数据
- ✅ 防止 SQL 注入（使用 ORM）
- ✅ 防止 XSS（输出转义）

## 六、关键设计决策

### 1. 为什么使用 JWT 而不是 Session？

**JWT 优势**:
- 无状态：服务器不需要存储会话
- 可扩展：适合分布式系统
- 跨域友好：可以在不同域名使用

**JWT 劣势**:
- 无法主动撤销（需要黑名单机制）
- Token 大小限制
- 安全性依赖密钥管理

### 2. 为什么使用 bcrypt 而不是 MD5/SHA？

**bcrypt 优势**:
- 专门为密码设计
- 计算慢（防止暴力破解）
- 自动加盐（防止彩虹表攻击）

### 3. 为什么使用依赖注入？

**优势**:
- 代码复用
- 易于测试（可以 mock 依赖）
- 清晰的依赖关系
- 自动处理错误

## 七、数据流转图

```
注册流程:
客户端 → 路由 → 验证 → 加密密码 → 数据库 → 返回用户

登录流程:
客户端 → 路由 → 查询用户 → 验证密码 → 生成Token → 返回Token

访问受保护接口:
客户端(Token) → 依赖注入 → 提取Token → 验证Token → 查询用户 → 返回用户 → 路由处理 → 返回结果
```

## 八、常见问题

### Q1: Token 过期了怎么办？
A: 需要重新登录获取新的 Token。未来可以实现 Refresh Token 机制。

### Q2: 如何登出？
A: 当前实现中，客户端删除 Token 即可。未来可以实现 Token 黑名单。

### Q3: 如何修改密码？
A: 需要实现密码修改接口，验证旧密码后更新 hashed_password。

### Q4: 如何实现权限系统？
A: 需要添加 Role 和 Permission 模型，在依赖注入中检查权限。

