"""
认证路由
- 用户注册
- 用户登录
- 获取当前用户信息
"""

from datetime import timedelta
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
    Query,
    Form,
)
from fastapi.responses import HTMLResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.db import get_db
from app.core.redis import get_redis_client
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    hash_token,
    decode_refresh_token,
    create_email_verification_token,
    decode_email_verification_token,
    create_password_reset_token,
    decode_password_reset_token,
)
from app.dependencies.auth import get_current_user, require_superuser
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import (
    Token,
    TokenRefresh,
    TokenRefreshResponse,
    LogoutResponse,
    UserRegister,
    DeviceListResponse,
    RevokeDeviceResponse,
    RefreshTokenInfo,
    EmailVerificationRequest,
    EmailVerificationResponse,
    ResendVerificationEmailResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TestEmailRequest,
    TestEmailResponse,
)
from app.schemas.user import UserResponse
from app.utils.token import TokenService
from app.core.email import email_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    """
    用户注册

    - **username**: 用户名(3-50个字符)
    - **email**: 邮箱地址
    - **password**: 密码(至少6个字符)
    - **full_name**: 全名(可选)
    """
    # 检查用户名是否已存在（只检查活跃用户，忽略已被拉黑的用户）
    result = await db.execute(
        select(User).where(
            User.username == user_data.username,
            User.is_active,  # 只检查活跃用户
        )
    )
    if result.scalar_one_or_none() is not None:
        logger.warning(f"用户注册失败: 用户名已存在 - {user_data.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在"
        )

    # 检查邮箱是否已存在（只检查活跃用户，忽略已被拉黑的用户）
    result = await db.execute(
        select(User).where(
            User.email == user_data.email,
            User.is_active,  # 只检查活跃用户
        )
    )
    if result.scalar_one_or_none() is not None:
        logger.warning(f"用户注册失败: 邮箱已被注册 - {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被注册"
        )

    # 创建新用户
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        is_active=True,
        is_superuser=False,
    )

    db.add(db_user)
    await db.commit()

    # 给新用户分配默认角色 "viewer" (查看者, 拥有基本的阅读权限)
    try:
        result = await db.execute(select(Role).where(Role.name == "viewer"))
        default_role = result.scalar_one_or_none()

        if default_role:
            # 重新查询用户以获取完整对象
            result = await db.execute(
                select(User)
                .where(User.id == db_user.id)
                .options(selectinload(User.roles))
            )
            user = result.scalar_one_or_none()

            if user:
                user.roles.append(default_role)
                await db.commit()
                logger.info(
                    f"已为新用户分配默认角色: user_id={user.id}, username={user.username}, role=viewer"
                )
            else:
                logger.error(f"用户注册后查询失败: user_id={db_user.id}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="用户注册失败, 请重试",
                )
        else:
            logger.warning("默认角色 'viewer' 不存在, 跳过角色分配")
            # 即使没有默认角色, 用户注册仍然成功
            result = await db.execute(
                select(User)
                .where(User.id == db_user.id)
                .options(selectinload(User.roles))
            )
            user = result.scalar_one_or_none()

            if user is None:
                logger.error(f"用户注册后查询失败: user_id={db_user.id}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="用户注册失败, 请重试",
                )
    except Exception as e:
        logger.error(f"分配默认角色失败: user_id={db_user.id}, error={e}")
        # 角色分配失败不影响用户注册, 但记录错误日志
        # 重新查询用户以返回响应
        result = await db.execute(
            select(User).where(User.id == db_user.id).options(selectinload(User.roles))
        )
        user = result.scalar_one_or_none()

        if user is None:
            logger.error(f"用户注册后查询失败: user_id={db_user.id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="用户注册失败, 请重试",
            )

    # 发送邮箱验证邮件
    try:
        verification_token = create_email_verification_token(user.id, user.email)
        email_sent = email_service.send_verification_email(
            email=user.email,
            username=user.username,
            verification_token=verification_token,
        )
        if email_sent:
            logger.info(
                f"用户注册成功: {user.username} (ID: {user.id}), 验证邮件已发送"
            )
        else:
            logger.warning(
                f"用户注册成功: {user.username} (ID: {user.id}), 但验证邮件发送失败, "
                f"请检查 SMTP 配置或稍后使用重新发送验证邮件功能"
            )
    except Exception as e:
        logger.error(f"发送验证邮件失败: user_id={user.id}, error={e}")
        # 邮件发送失败不影响注册流程

    logger.info(f"用户注册成功: {user.username} (ID: {user.id})")
    return user


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    response: Response,
    username: str = Form(..., description="用户名或邮箱"),
    password: str = Form(..., min_length=6, description="密码"),
    db: AsyncSession = Depends(get_db),
):
    """
    用户登录

    使用表单格式提交用户名和密码
    返回 JWT Access Token 和 Refresh Token, 同时设置 Cookie(用于 Web 应用)

    注意:
    - Access Token 和 Refresh Token 会同时通过响应体和 Cookie 返回
    - Cookie 名称: "token" (Access Token), "refresh_token" (Refresh Token)
    - Cookie 属性: HttpOnly=True, Secure=True (生产环境), SameSite=Lax
    """
    # 查询用户(支持用户名或邮箱登录)
    result = await db.execute(
        select(User).where((User.username == username) | (User.email == username))
    )
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning(f"登录失败: 用户不存在 - {username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 验证密码
    password_match = verify_password(password, user.hashed_password)
    logger.debug(
        f"密码验证: username={user.username}, user_id={user.id}, "
        f"验证结果={password_match}, hashed_password前10位={user.hashed_password[:10]}..."
    )

    if not password_match:
        logger.warning(f"登录失败: 密码错误 - {user.username} (ID: {user.id})")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 检查用户是否激活
    if not user.is_active:
        logger.warning(f"登录失败: 用户已被禁用 - {user.username} (ID: {user.id})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用"
        )

    # 创建 Access Token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # 创建 Refresh Token
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token_value = create_refresh_token(
        data={"sub": user.username, "user_id": user.id},
        expires_delta=refresh_token_expires,
    )

    # 获取设备信息
    user_agent = request.headers.get("user-agent", "")
    ip_address = request.client.host if request.client else None

    # 解析设备信息
    device_info = None
    device_type = "web"
    if user_agent:
        # 简单的设备类型判断
        user_agent_lower = user_agent.lower()
        if (
            "mobile" in user_agent_lower
            or "android" in user_agent_lower
            or "iphone" in user_agent_lower
        ):
            device_type = "mobile"
        elif "tablet" in user_agent_lower or "ipad" in user_agent_lower:
            device_type = "tablet"
        elif (
            "windows" in user_agent_lower
            or "mac" in user_agent_lower
            or "linux" in user_agent_lower
        ):
            device_type = "desktop"

        device_info = {
            "type": device_type,
            "name": user_agent[:100],  # 限制长度
            "user_agent": user_agent,
        }

    # 存储 Refresh Token
    redis = await get_redis_client()
    await TokenService.store_refresh_token(
        token=refresh_token_value,
        user_id=user.id,
        username=user.username,
        redis=redis,
        db=db,
        device_info=device_info,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # 设置 Cookie（用于 Web 应用自动携带）
    # HttpOnly: 防止 JavaScript 访问，提高安全性
    # Secure: 只在 HTTPS 下传输（生产环境建议开启）
    # SameSite: 防止 CSRF 攻击
    access_token_max_age = int(access_token_expires.total_seconds())
    refresh_token_max_age = int(refresh_token_expires.total_seconds())

    response.set_cookie(
        key="token",
        value=access_token,
        max_age=access_token_max_age,
        httponly=True,
        secure=not settings.DEBUG,  # 生产环境启用 Secure
        samesite="lax",
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token_value,
        max_age=refresh_token_max_age,
        httponly=True,
        secure=not settings.DEBUG,  # 生产环境启用 Secure
        samesite="lax",
    )

    logger.info(
        f"用户登录成功: {user.username} (ID: {user.id}), 设备类型: {device_type}, IP: {ip_address}"
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token_value,
        "token_type": "bearer",
        "expires_in": access_token_max_age,
    }


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_access_token(
    request: Request,
    response: Response,
    token_data: Optional[TokenRefresh] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    刷新 Access Token

    使用 Refresh Token 获取新的 Access Token
    Refresh Token 可以从请求体或 Cookie 中获取

    注意:
    - Refresh Token 必须有效且未被撤销
    - 返回新的 Access Token
    - Refresh Token 保持不变
    """
    # 从请求体或 Cookie 获取 Refresh Token
    refresh_token_value = None
    if token_data and token_data.refresh_token:
        refresh_token_value = token_data.refresh_token
    else:
        refresh_token_value = request.cookies.get("refresh_token")

    if not refresh_token_value:
        logger.warning("刷新 Token 失败: 未提供 Refresh Token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供 Refresh Token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 解码 Refresh Token
    payload = decode_refresh_token(refresh_token_value)
    if payload is None:
        logger.warning("刷新 Token 失败: 无效的 Refresh Token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Refresh Token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 验证 Refresh Token 是否在黑名单中
    token_hash = hash_token(refresh_token_value)
    redis = await get_redis_client()
    token_info = await TokenService.get_refresh_token(token_hash, redis)
    if not token_info:
        logger.warning("刷新 Token 失败: Refresh Token 已失效")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh Token 已失效",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 获取用户信息
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Refresh Token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 查询用户
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        logger.warning(f"刷新 Token 失败: 用户不存在或已被禁用 - {username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 创建新的 Access Token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # 更新 Cookie
    access_token_max_age = int(access_token_expires.total_seconds())
    response.set_cookie(
        key="token",
        value=access_token,
        max_age=access_token_max_age,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
    )

    logger.info(f"Token 刷新成功: {user.username} (ID: {user.id})")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": access_token_max_age,
    }


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    用户登出

    撤销当前的 Refresh Token, 清除 Cookie

    注意:
    - 需要提供有效的 Refresh Token
    - 登出后, Refresh Token 将被加入黑名单
    """
    # 从 Cookie 获取 Refresh Token
    refresh_token_value = request.cookies.get("refresh_token")

    if refresh_token_value:
        # 撤销 Refresh Token
        token_hash = hash_token(refresh_token_value)
        redis = await get_redis_client()
        await TokenService.revoke_refresh_token(token_hash, redis, db)
        logger.info(f"用户登出: Token 已撤销 (hash: {token_hash[:16]}...)")

    # 清除 Cookie
    response.delete_cookie(key="token", httponly=True, samesite="lax")
    response.delete_cookie(key="refresh_token", httponly=True, samesite="lax")

    return LogoutResponse(message="登出成功")


@router.get("/devices", response_model=DeviceListResponse)
async def get_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户的所有登录设备

    返回所有有效的 Refresh Token 信息, 包括设备信息、IP地址、登录时间等
    """
    tokens = await TokenService.get_user_tokens(
        current_user.id, db, include_revoked=False
    )

    logger.debug(
        f"查询设备列表: user_id={current_user.id}, 找到 {len(tokens)} 个 Token"
    )

    devices = [
        RefreshTokenInfo(
            id=token.id,
            device_name=token.device_name,
            device_type=token.device_type,
            ip_address=token.ip_address,
            created_at=token.created_at,  # BaseResponseModel 会自动序列化 datetime
            expires_at=token.expires_at,  # BaseResponseModel 会自动序列化 datetime
            revoked=token.revoked,
        )
        for token in tokens
    ]

    return DeviceListResponse(devices=devices, total=len(devices))


@router.delete("/devices/{device_id}", response_model=RevokeDeviceResponse)
async def revoke_device(
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    撤销指定设备的登录

    撤销后, 该设备的 Refresh Token 将失效, 需要重新登录
    """
    # 查询 Token
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.id == device_id, RefreshToken.user_id == current_user.id
        )
    )
    token = result.scalar_one_or_none()

    if token is None:
        logger.warning(
            f"撤销设备失败: 设备不存在 - device_id={device_id}, user_id={current_user.id}"
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")

    if token.revoked:
        logger.warning(
            f"撤销设备失败: 设备已被撤销 - device_id={device_id}, user_id={current_user.id}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="设备已被撤销"
        )

    # 撤销 Token
    redis = await get_redis_client()
    await TokenService.revoke_refresh_token(token.token_hash, redis, db)

    logger.info(
        f"设备已撤销: device_id={device_id}, user_id={current_user.id}, device_name={token.device_name}"
    )
    return RevokeDeviceResponse(message="设备已撤销")


@router.post("/devices/revoke-all", response_model=LogoutResponse)
async def revoke_all_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    撤销所有设备的登录(除了当前设备)

    撤销后, 所有其他设备的 Refresh Token 将失效, 需要重新登录
    当前设备的 Token 不受影响
    """
    redis = await get_redis_client()
    revoked_count = await TokenService.revoke_all_user_tokens(
        current_user.id, redis, db
    )

    logger.info(
        f"已撤销所有设备登录: user_id={current_user.id}, 撤销数量={revoked_count}"
    )
    return LogoutResponse(message=f"已撤销 {revoked_count} 个设备的登录")


# 注意：/me 端点已移至 users 路由，这里保留是为了向后兼容
# 实际实现请使用 /api/v1/users/me


@router.get("/verify-email", response_class=HTMLResponse)
async def verify_email_get(
    token: str = Query(..., description="验证 Token"),
    db: AsyncSession = Depends(get_db),
):
    """
    验证邮箱 (GET方式, 直接通过浏览器访问)

    用户点击邮件中的验证链接后, 直接访问此接口完成验证.
    返回HTML页面显示验证结果.
    """
    # 解码验证 Token
    payload = decode_email_verification_token(token)

    if payload is None:
        logger.warning("邮箱验证失败: 无效的验证 Token")
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>邮箱验证失败</title>
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                    .error { color: #dc3545; }
                </style>
            </head>
            <body>
                <h1 class="error">邮箱验证失败</h1>
                <p>验证链接无效或已过期，请重新申请验证邮件。</p>
            </body>
            </html>
            """,
            status_code=400,
        )

    user_id = payload.get("user_id")
    email = payload.get("email")

    if not user_id or not email:
        logger.warning("邮箱验证失败: Token 中缺少必要信息")
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>邮箱验证失败</title>
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                    .error { color: #dc3545; }
                </style>
            </head>
            <body>
                <h1 class="error">邮箱验证失败</h1>
                <p>验证链接无效，请重新申请验证邮件。</p>
            </body>
            </html>
            """,
            status_code=400,
        )

    # 查询用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning(f"邮箱验证失败: 用户不存在 - user_id={user_id}")
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>邮箱验证失败</title>
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                    .error { color: #dc3545; }
                </style>
            </head>
            <body>
                <h1 class="error">邮箱验证失败</h1>
                <p>用户不存在，请检查验证链接。</p>
            </body>
            </html>
            """,
            status_code=404,
        )

    # 验证邮箱是否匹配
    if user.email != email:
        logger.warning(
            f"邮箱验证失败: 邮箱不匹配 - user_id={user_id}, token_email={email}, user_email={user.email}"
        )
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>邮箱验证失败</title>
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                    .error { color: #dc3545; }
                </style>
            </head>
            <body>
                <h1 class="error">邮箱验证失败</h1>
                <p>邮箱不匹配，请使用正确的验证链接。</p>
            </body>
            </html>
            """,
            status_code=400,
        )

    # 检查是否已经验证过
    if user.email_verified:
        logger.info(f"邮箱已验证: user_id={user_id}, email={email}")
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>邮箱已验证</title>
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                    .success {{ color: #28a745; }}
                </style>
            </head>
            <body>
                <h1 class="success">邮箱已验证</h1>
                <p>您的邮箱 {email} 已经验证过了。</p>
            </body>
            </html>
            """
        )

    # 更新验证状态
    user.email_verified = True
    await db.commit()

    logger.info(f"邮箱验证成功: user_id={user_id}, email={email}")
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>邮箱验证成功</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                .success {{ color: #28a745; }}
            </style>
        </head>
        <body>
            <h1 class="success">✓ 邮箱验证成功</h1>
            <p>您的邮箱 {email} 已验证成功！</p>
            <p>现在可以使用所有功能了。</p>
        </body>
        </html>
        """
    )


@router.post("/verify-email", response_model=EmailVerificationResponse)
async def verify_email_post(
    verification_data: EmailVerificationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    验证邮箱 (POST方式, 供前端API调用)

    前端页面可以调用此接口验证邮箱.
    """
    # 解码验证 Token
    payload = decode_email_verification_token(verification_data.token)
    if payload is None:
        logger.warning("邮箱验证失败: 无效的验证 Token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="无效的验证链接"
        )

    user_id = payload.get("user_id")
    email = payload.get("email")

    if not user_id or not email:
        logger.warning("邮箱验证失败: Token 中缺少必要信息")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="无效的验证链接"
        )

    # 查询用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning(f"邮箱验证失败: 用户不存在 - user_id={user_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 验证邮箱是否匹配
    if user.email != email:
        logger.warning(
            f"邮箱验证失败: 邮箱不匹配 - user_id={user_id}, token_email={email}, user_email={user.email}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱不匹配"
        )

    # 检查是否已经验证过
    if user.email_verified:
        logger.info(f"邮箱已验证: user_id={user_id}, email={email}")
        return EmailVerificationResponse(message="邮箱已验证")

    # 更新验证状态
    user.email_verified = True
    await db.commit()

    logger.info(f"邮箱验证成功: user_id={user_id}, email={email}")
    return EmailVerificationResponse(message="邮箱验证成功")


@router.post(
    "/resend-verification-email", response_model=ResendVerificationEmailResponse
)
async def resend_verification_email(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    重新发送验证邮件

    如果用户没有收到验证邮件, 可以调用此接口重新发送.
    """
    # 检查是否已经验证
    if current_user.email_verified:
        logger.info(f"邮箱已验证, 无需重新发送: user_id={current_user.id}")
        return ResendVerificationEmailResponse(message="邮箱已验证, 无需重新发送")

    # 生成新的验证 Token
    verification_token = create_email_verification_token(
        current_user.id, current_user.email
    )

    # 发送验证邮件
    success = email_service.send_verification_email(
        email=current_user.email,
        username=current_user.username,
        verification_token=verification_token,
    )

    if success:
        logger.info(
            f"重新发送验证邮件成功: user_id={current_user.id}, email={current_user.email}"
        )
        return ResendVerificationEmailResponse(message="验证邮件已发送，请查收邮箱")
    else:
        logger.error(
            f"重新发送验证邮件失败: user_id={current_user.id}, email={current_user.email}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="发送验证邮件失败，请稍后重试",
        )


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    forgot_data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    忘记密码

    发送密码重置邮件到用户邮箱.
    出于安全考虑, 无论邮箱是否存在, 都返回成功消息.
    """
    # 查询用户
    result = await db.execute(select(User).where(User.email == forgot_data.email))
    user = result.scalar_one_or_none()

    # 出于安全考虑, 无论用户是否存在都返回成功消息
    # 这样可以防止恶意用户通过此接口枚举邮箱
    if user is None:
        logger.warning(f"忘记密码请求: 邮箱不存在 - {forgot_data.email}")
        return ForgotPasswordResponse(
            message="如果该邮箱已注册, 密码重置邮件已发送，请查收邮箱"
        )

    # 检查用户是否激活
    if not user.is_active:
        logger.warning(
            f"忘记密码请求: 用户已被禁用 - user_id={user.id}, email={forgot_data.email}"
        )
        return ForgotPasswordResponse(
            message="如果该邮箱已注册, 密码重置邮件已发送，请查收邮箱"
        )

    # 生成重置 Token
    reset_token = create_password_reset_token(user.id, user.email)

    # 发送重置邮件
    success = email_service.send_password_reset_email(
        email=user.email,
        username=user.username,
        reset_token=reset_token,
    )

    if success:
        logger.info(f"密码重置邮件已发送: user_id={user.id}, email={user.email}")
    else:
        logger.error(f"发送密码重置邮件失败: user_id={user.id}, email={user.email}")

    return ForgotPasswordResponse(
        message="如果该邮箱已注册, 密码重置邮件已发送，请查收邮箱"
    )


@router.get("/reset-password-page", response_class=HTMLResponse)
async def reset_password_page_get(
    token: str = Query(..., description="重置 Token"),
):
    """
    密码重置页面 (GET方式, 直接通过浏览器访问)

    用户点击邮件中的重置链接后, 显示密码重置表单页面.
    """
    # 先验证Token是否有效
    payload = decode_password_reset_token(token)

    if payload is None:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>密码重置失败</title>
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                    .error { color: #dc3545; }
                </style>
            </head>
            <body>
                <h1 class="error">密码重置失败</h1>
                <p>重置链接无效或已过期，请重新申请密码重置。</p>
            </body>
            </html>
            """,
            status_code=400,
        )

    # 返回密码重置表单页面
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>重置密码</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 400px; margin: 50px auto; padding: 20px; }}
                .form-group {{ margin-bottom: 20px; }}
                label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
                input[type="password"] {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }}
                button {{ width: 100%; padding: 12px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }}
                button:hover {{ background-color: #0056b3; }}
                .error {{ color: #dc3545; margin-top: 10px; }}
                .success {{ color: #28a745; margin-top: 10px; }}
            </style>
        </head>
        <body>
            <h2>重置密码</h2>
            <form id="resetForm">
                <div class="form-group">
                    <label for="newPassword">新密码:</label>
                    <input type="password" id="newPassword" name="newPassword" minlength="6" required>
                </div>
                <div class="form-group">
                    <label for="confirmPassword">确认密码:</label>
                    <input type="password" id="confirmPassword" name="confirmPassword" minlength="6" required>
                </div>
                <button type="submit">重置密码</button>
                <div id="message"></div>
            </form>
            <script>
                document.getElementById('resetForm').addEventListener('submit', async function(e) {{
                    e.preventDefault();
                    const newPassword = document.getElementById('newPassword').value;
                    const confirmPassword = document.getElementById('confirmPassword').value;
                    const messageDiv = document.getElementById('message');
                    
                    if (newPassword !== confirmPassword) {{
                        messageDiv.innerHTML = '<p class="error">两次输入的密码不一致</p>';
                        return;
                    }}
                    
                    if (newPassword.length < 6) {{
                        messageDiv.innerHTML = '<p class="error">密码长度至少6位</p>';
                        return;
                    }}
                    
                    try {{
                        const response = await fetch('/api/v1/auth/reset-password', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{
                                token: '{token}',
                                new_password: newPassword
                            }})
                        }});
                        
                        const data = await response.json();
                        
                        if (response.ok) {{
                            messageDiv.innerHTML = '<p class="success">密码重置成功！请使用新密码登录。</p>';
                            document.getElementById('resetForm').style.display = 'none';
                        }} else {{
                            messageDiv.innerHTML = '<p class="error">' + (data.detail || '密码重置失败') + '</p>';
                        }}
                    }} catch (error) {{
                        messageDiv.innerHTML = '<p class="error">网络错误，请稍后重试</p>';
                    }}
                }});
            </script>
        </body>
        </html>
        """
    )


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password_post(
    reset_data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    重置密码 (POST方式, 供前端API调用)

    用户点击邮件中的重置链接后, 调用此接口重置密码.
    """
    # 解码重置 Token
    payload = decode_password_reset_token(reset_data.token)
    if payload is None:
        logger.warning("密码重置失败: 无效的重置 Token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="无效的重置链接或链接已过期"
        )

    user_id = payload.get("user_id")
    email = payload.get("email")

    if not user_id or not email:
        logger.warning("密码重置失败: Token 中缺少必要信息")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="无效的重置链接"
        )

    # 查询用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning(f"密码重置失败: 用户不存在 - user_id={user_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 验证邮箱是否匹配
    if user.email != email:
        logger.warning(
            f"密码重置失败: 邮箱不匹配 - user_id={user_id}, token_email={email}, user_email={user.email}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱不匹配"
        )

    # 更新密码
    user.hashed_password = get_password_hash(reset_data.new_password)
    await db.commit()

    # 撤销所有 Refresh Token, 强制用户重新登录
    redis = await get_redis_client()
    try:
        revoked_count = await TokenService.revoke_all_user_tokens(user.id, redis, db)
        logger.info(f"密码重置成功: user_id={user_id}, 已撤销 {revoked_count} 个 Token")
    except Exception as e:
        logger.error(f"撤销 Token 失败: user_id={user_id}, error={e}")

    logger.info(f"密码重置成功: user_id={user_id}, email={email}")
    return ResetPasswordResponse(message="密码重置成功，请使用新密码登录")


@router.post("/test-email", response_model=TestEmailResponse)
async def test_email(
    test_data: TestEmailRequest,
    _: None = Depends(require_superuser),
):
    """
    测试邮件发送功能（需要超级用户权限）

    用于测试 SMTP 配置是否正确, 可以发送测试邮件到指定邮箱.

    - **to_email**: 收件人邮箱地址
    - **subject**: 邮件主题（可选, 默认为"测试邮件"）
    - **content**: 邮件内容（可选, 默认为"这是一封测试邮件"）
    """
    # 检查 SMTP 配置
    smtp_password = str(settings.SMTP_PASSWORD).strip().replace(" ", "") if settings.SMTP_PASSWORD else None
    smtp_user = str(settings.SMTP_USER).strip() if settings.SMTP_USER else None

    smtp_config_status = {
        "smtp_host": settings.SMTP_HOST if settings.SMTP_HOST else None,
        "smtp_port": settings.SMTP_PORT,
        "smtp_user": smtp_user,
        "smtp_password_set": bool(smtp_password),
        "smtp_password_length": len(smtp_password) if smtp_password else 0,
        "smtp_password_format_hint": (
            "✅ 密码长度符合 Gmail 应用专用密码格式（16位）"
            if smtp_password and len(smtp_password.replace(" ", "")) == 16
            else "⚠️ 密码长度不符合 Gmail 应用专用密码格式（应为16位，不含空格）"
            if smtp_password
            else None
        ),
        "smtp_from_email": settings.SMTP_FROM_EMAIL
        if settings.SMTP_FROM_EMAIL
        else None,
        "smtp_from_name": settings.SMTP_FROM_NAME,
        "smtp_use_tls": settings.SMTP_USE_TLS,
    }

    # 检查必要的配置
    if not settings.SMTP_HOST:
        return TestEmailResponse(
            success=False,
            message="SMTP 配置未设置, 请配置 SMTP_HOST 等环境变量",
            smtp_config_status=smtp_config_status,
        )

    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        return TestEmailResponse(
            success=False,
            message="SMTP 用户名或密码未设置, 请配置 SMTP_USER 和 SMTP_PASSWORD",
            smtp_config_status=smtp_config_status,
        )

    # 发送测试邮件
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .success {{ background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px; margin: 20px 0; }}
            .info {{ background-color: #d1ecf1; border-left: 4px solid #17a2b8; padding: 15px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>测试邮件</h2>
            <div class="success">
                <strong>✅ 邮件发送功能正常!</strong>
            </div>
            <div class="info">
                <p><strong>邮件内容:</strong></p>
                <p>{test_data.content}</p>
            </div>
            <p>如果您收到这封邮件, 说明 SMTP 配置正确, 邮件发送功能正常工作.</p>
            <hr>
            <p style="font-size: 12px; color: #666;">
                此邮件由 {settings.APP_NAME} 自动发送, 用于测试邮件发送功能.
            </p>
        </div>
    </body>
    </html>
    """

    text_content = f"""
    测试邮件
    
    ✅ 邮件发送功能正常!
    
    邮件内容:
    {test_data.content}
    
    如果您收到这封邮件, 说明 SMTP 配置正确, 邮件发送功能正常工作.
    
    ---
    此邮件由 {settings.APP_NAME} 自动发送, 用于测试邮件发送功能.
    """

    success = email_service._send_email(
        to_email=test_data.to_email,
        subject=test_data.subject,
        html_content=html_content,
        text_content=text_content,
    )

    if success:
        logger.info(f"测试邮件发送成功: to={test_data.to_email}")
        return TestEmailResponse(
            success=True,
            message=f"测试邮件已成功发送到 {test_data.to_email}, 请查收邮箱",
            smtp_config_status=smtp_config_status,
        )
    else:
        logger.error(f"测试邮件发送失败: to={test_data.to_email}")
        return TestEmailResponse(
            success=False,
            message="测试邮件发送失败, 请检查 SMTP 配置和日志",
            smtp_config_status=smtp_config_status,
        )
