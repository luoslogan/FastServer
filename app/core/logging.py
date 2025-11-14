"""
统一日志配置模块

功能:
1. 默认所有日志记录到 app.log 和 error.log
2. 支持为特定模块配置单独的日志文件
3. 支持 HTTP 访问日志 (access.log)

使用方式:
    # 在 main.py 中初始化
    from app.core.logging import setup_logging
    setup_logging(log_dir=settings.BASE_PATH / "logs", log_level="INFO")

    # 在其他文件中使用
    from loguru import logger
    logger.info("普通日志")  # 会记录到 app.log

    # 为特定模块配置单独日志文件
    from app.core.logging import register_module_logger
    register_module_logger("app.services.crawler", "crawler.log")
    # 之后 app.services.crawler 模块的日志会同时记录到 app.log 和 crawler.log
"""

from typing import Dict, Optional
from pathlib import Path
from loguru import logger
import sys


class LoggingManager:
    """日志管理器, 负责管理所有日志配置"""

    def __init__(self):
        self.log_dir: Optional[Path] = None
        self.module_loggers: Dict[str, str] = {}  # 模块名 -> 日志文件名映射
        self._initialized = False

    def setup(
        self,
        log_dir: Path,
        log_level: str = "INFO",
        enable_access_log: bool = True,
    ):
        """
        初始化日志系统

        Args:
            log_dir: 日志目录路径
            log_level: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
            enable_access_log: 是否启用 HTTP 访问日志
        """
        if self._initialized:
            # 在 reload 模式下, 模块会重新加载, _initialized 标志会重置
            # 所以这个检查主要用于防止在同一进程中的重复初始化
            logger.debug("日志系统已初始化, 跳过重复初始化")
            return

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 移除 loguru 的默认 handler
        logger.remove()

        # 1. 控制台输出 (所有日志, 带颜色)
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=log_level,
            colorize=True,
        )

        # 2. 应用主日志文件 (所有日志)
        logger.add(
            self.log_dir / "app.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=log_level,
            rotation="100 MB",
            retention="30 days",
            compression="zip",
            encoding="utf-8",
        )

        # 3. 错误日志文件 (ERROR 及以上级别)
        logger.add(
            self.log_dir / "error.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}\n{exception}",
            level="ERROR",
            rotation="50 MB",
            retention="90 days",
            compression="zip",
            encoding="utf-8",
        )

        # 4. HTTP 访问日志 (可选)
        if enable_access_log:

            def access_log_filter(record):
                """过滤访问日志: 检查 extra 中的 'access' 标识"""
                return record.get("extra", {}).get("access", False)

            logger.add(
                self.log_dir / "access.log",
                format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
                level="INFO",
                rotation="100 MB",
                retention="30 days",
                compression="zip",
                encoding="utf-8",
                # 只记录访问日志 (通过 extra 中的 'access' 标识)
                filter=access_log_filter,
            )

        self._initialized = True
        # 使用 DEBUG 级别, 避免在 reload 时产生过多 INFO 日志
        # reload 时会重新加载模块, 导致日志系统重新初始化, 这是正常行为
        logger.debug(f"日志系统初始化完成, 日志目录: {self.log_dir}")

    def register_module_logger(
        self, module_name: str, log_filename: str, log_level: str = "DEBUG"
    ):
        """
        为特定模块注册单独的日志文件

        Args:
            module_name: 模块名 (如 "app.services.crawler" 或 "app.routers.auth")
            log_filename: 日志文件名 (如 "crawler.log")
            log_level: 该模块的日志级别

        注意:
            - 模块日志会同时写入 app.log 和指定的单独文件
            - 如果模块名已存在, 会覆盖之前的配置
        """
        if not self._initialized:
            raise RuntimeError("日志系统尚未初始化, 请先调用 setup()")

        if not self.log_dir:
            raise RuntimeError("日志目录未设置")

        log_file_path = self.log_dir / log_filename

        # 创建过滤器函数, 只记录指定模块的日志
        def module_filter(record):
            return record["name"].startswith(module_name)

        # 添加模块专用日志文件
        logger.add(
            log_file_path,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}\n{exception}",
            level=log_level,
            rotation="50 MB",
            retention="30 days",
            compression="zip",
            encoding="utf-8",
            filter=module_filter,  # 只记录该模块的日志
        )

        self.module_loggers[module_name] = log_filename
        logger.info(f"已为模块 '{module_name}' 注册单独日志文件: {log_filename}")

    def get_access_logger(self):
        """
        获取 HTTP 访问日志专用的 logger

        使用方式:
            access_logger = logging_manager.get_access_logger()
            access_logger.info("GET /api/v1/users 200 1.23ms")
        """
        # 使用 extra 来标识访问日志, 这样过滤器可以正确匹配
        return logger.bind(access=True)


# 全局日志管理器实例
_logging_manager = LoggingManager()


def setup_logging(
    log_dir: Path,
    log_level: str = "INFO",
    enable_access_log: bool = True,
):
    """
    初始化日志系统 (便捷函数)

    Args:
        log_dir: 日志目录路径
        log_level: 日志级别
        enable_access_log: 是否启用访问日志
    """
    _logging_manager.setup(log_dir, log_level, enable_access_log)


def register_module_logger(
    module_name: str, log_filename: str, log_level: str = "DEBUG"
):
    """
    为特定模块注册单独的日志文件 (便捷函数)

    使用示例:
        # 在模块文件顶部或初始化代码中调用
        from app.core.logging import register_module_logger
        register_module_logger(__name__, "crawler.log")

        # 或者使用模块路径
        register_module_logger("app.services.crawler", "crawler.log")

    Args:
        module_name: 模块名 (可以使用 __name__ 或完整模块路径)
        log_filename: 日志文件名
        log_level: 日志级别
    """
    _logging_manager.register_module_logger(module_name, log_filename, log_level)


def get_access_logger():
    """
    获取 HTTP 访问日志专用的 logger

    使用示例:
        from app.core.logging import get_access_logger
        access_logger = get_access_logger()
        access_logger.info(f"{method} {path} {status_code} {duration}ms")
    """
    return _logging_manager.get_access_logger()
