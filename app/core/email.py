"""
邮件发送服务模块

支持发送验证邮件和密码重置邮件.
使用 SMTP 协议, 支持任何 SMTP 服务器（Gmail、Outlook、自定义服务器等）.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from loguru import logger

from app.core.config import settings


class EmailService:
    """邮件发送服务"""

    @staticmethod
    def _get_smtp_server():
        """
        获取 SMTP 服务器连接

        Returns:
            SMTP 服务器连接对象
        """
        if not settings.SMTP_HOST:
            raise ValueError("SMTP 配置未设置, 请配置 SMTP_HOST 等环境变量")

        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            # 去除密码首尾空格和换行符（避免配置错误）
            smtp_user = str(settings.SMTP_USER).strip()
            # Gmail 应用专用密码可能是 "xxxx xxxx xxxx xxxx" 格式, 需要去除所有空格
            smtp_password = str(settings.SMTP_PASSWORD).strip().replace(" ", "")

            # 记录调试信息（不记录完整密码）
            logger.debug(
                f"SMTP 登录: user={smtp_user}, "
                f"password_length={len(smtp_password)}, "
                f"password_starts_with={smtp_password[:2] if len(smtp_password) >= 2 else 'N/A'}"
            )

            server.login(smtp_user, smtp_password)
        return server

    @staticmethod
    def _send_email(
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """
        发送邮件

        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            html_content: HTML 格式的邮件内容
            text_content: 纯文本格式的邮件内容（可选）

        Returns:
            bool: 是否发送成功
        """
        try:
            if not settings.SMTP_HOST:
                logger.error("SMTP 配置未设置, 无法发送邮件")
                return False

            # 创建邮件消息
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = (
                f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL or settings.SMTP_USER}>"
            )
            msg["To"] = to_email

            # 添加文本内容（如果有）
            if text_content:
                text_part = MIMEText(text_content, "plain", "utf-8")
                msg.attach(text_part)

            # 添加 HTML 内容
            html_part = MIMEText(html_content, "html", "utf-8")
            msg.attach(html_part)

            # 发送邮件
            server = EmailService._get_smtp_server()
            server.send_message(msg)
            server.quit()

            logger.info(f"邮件发送成功: to={to_email}, subject={subject}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            error_msg = str(e)
            logger.error(
                f"邮件发送失败: SMTP 认证失败 - to={to_email}, subject={subject}, "
                f"error={error_msg}"
            )
            # 提供更详细的错误提示
            if (
                "Application-specific password" in error_msg
                or "InvalidSecondFactor" in error_msg
            ):
                logger.error(
                    "提示: Gmail 需要使用应用专用密码, 请访问 "
                    "https://myaccount.google.com/apppasswords 生成应用专用密码. "
                    "确保密码是 16 位字符（不含空格）"
                )
            return False
        except Exception as e:
            logger.error(f"邮件发送失败: to={to_email}, subject={subject}, error={e}")
            return False

    @staticmethod
    def send_verification_email(
        email: str, username: str, verification_token: str
    ) -> bool:
        """
        发送邮箱验证邮件

        Args:
            email: 收件人邮箱
            username: 用户名
            verification_token: 验证 Token

        Returns:
            bool: 是否发送成功
        """
        # 生成验证链接
        # 如果FRONTEND_URL包含"/api/v1"或者是后端地址，直接使用后端API
        # 否则使用前端页面
        frontend_url: str = str(settings.FRONTEND_URL)
        if (
            "/api/v1" in frontend_url
            or "localhost:8000" in frontend_url
            or ":8000" in frontend_url
        ):
            # 直接使用后端API（不需要前端）
            # 规范化URL：移除末尾的斜杠和 /api/v1
            base_url = frontend_url.rstrip("/").replace("/api/v1", "")
            base_url = base_url.rstrip("/")
            verification_url = (
                f"{base_url}/api/v1/auth/verify-email?token={verification_token}"
            )
        else:
            # 使用前端页面（需要前端配合）
            verification_url = (
                f"{frontend_url.rstrip('/')}/verify-email?token={verification_token}"
            )

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .button:hover {{ background-color: #0056b3; }}
                .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>欢迎注册 {settings.APP_NAME}!</h2>
                <p>您好, {username}!</p>
                <p>感谢您注册我们的服务。请点击下面的按钮验证您的邮箱地址:</p>
                <p><a href="{verification_url}" class="button">验证邮箱</a></p>
                <p>如果按钮无法点击, 请复制以下链接到浏览器中打开:</p>
                <p style="word-break: break-all; color: #666;">{verification_url}</p>
                <p>此链接将在 24 小时后过期。</p>
                <div class="footer">
                    <p>如果您没有注册此账户, 请忽略此邮件。</p>
                    <p>此邮件由系统自动发送, 请勿回复。</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        欢迎注册 {settings.APP_NAME}!

        您好, {username}!

        感谢您注册我们的服务。请访问以下链接验证您的邮箱地址:

        {verification_url}

        此链接将在 24 小时后过期。

        如果您没有注册此账户, 请忽略此邮件。
        """

        return EmailService._send_email(
            to_email=email,
            subject=f"请验证您的邮箱 - {settings.APP_NAME}",
            html_content=html_content,
            text_content=text_content,
        )

    @staticmethod
    def send_password_reset_email(email: str, username: str, reset_token: str) -> bool:
        """
        发送密码重置邮件

        Args:
            email: 收件人邮箱
            username: 用户名
            reset_token: 重置 Token

        Returns:
            bool: 是否发送成功
        """
        # 生成重置链接
        # 如果FRONTEND_URL包含"/api/v1"或者是后端地址，直接使用后端API
        # 否则使用前端页面
        frontend_url: str = str(settings.FRONTEND_URL)
        if (
            "/api/v1" in frontend_url
            or "localhost:8000" in frontend_url
            or ":8000" in frontend_url
        ):
            # 直接使用后端API（不需要前端）
            # 规范化URL：移除末尾的斜杠和 /api/v1
            base_url = frontend_url.rstrip("/").replace("/api/v1", "")
            base_url = base_url.rstrip("/")
            reset_url = (
                f"{base_url}/api/v1/auth/reset-password-page?token={reset_token}"
            )
        else:
            # 使用前端页面（需要前端配合）
            reset_url = f"{frontend_url.rstrip('/')}/reset-password?token={reset_token}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #dc3545; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .button:hover {{ background-color: #c82333; }}
                .warning {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 20px 0; }}
                .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>密码重置请求</h2>
                <p>您好, {username}!</p>
                <p>我们收到了您的密码重置请求。请点击下面的按钮重置您的密码:</p>
                <p><a href="{reset_url}" class="button">重置密码</a></p>
                <p>如果按钮无法点击, 请复制以下链接到浏览器中打开:</p>
                <p style="word-break: break-all; color: #666;">{reset_url}</p>
                <div class="warning">
                    <strong>安全提示:</strong>
                    <ul>
                        <li>此链接将在 1 小时后过期</li>
                        <li>如果您没有请求重置密码, 请忽略此邮件</li>
                        <li>您的密码不会被更改, 除非您点击上面的链接并设置新密码</li>
                    </ul>
                </div>
                <div class="footer">
                    <p>此邮件由系统自动发送, 请勿回复。</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        密码重置请求

        您好, {username}!

        我们收到了您的密码重置请求。请访问以下链接重置您的密码:

        {reset_url}

        安全提示:
        - 此链接将在 1 小时后过期
        - 如果您没有请求重置密码, 请忽略此邮件
        - 您的密码不会被更改, 除非您访问上面的链接并设置新密码

        此邮件由系统自动发送, 请勿回复。
        """

        return EmailService._send_email(
            to_email=email,
            subject=f"密码重置 - {settings.APP_NAME}",
            html_content=html_content,
            text_content=text_content,
        )


# 创建全局实例
email_service = EmailService()
