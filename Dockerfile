# ------------------------------------------------------------
# 阶段 1: 基础环境与构建阶段 (Build Stage)
# 目的: 安装依赖和构建任何 C 扩展，保持最终镜像整洁。
# ------------------------------------------------------------
FROM python:3.12-slim as builder

# 设置核心环境变量
# PYTHONUNBUFFERED=1 确保日志立即输出 (极其重要)
# PIP_NO_CACHE_DIR=1 减小镜像体积
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Shanghai

# 设置工作目录
WORKDIR /code

# 安装系统依赖 (用于编译 Python 库中底层 C 代码)
# 包含 gcc 用于编译、postgresql-client 用于调试
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制并安装 Python 依赖 (利用 Docker 缓存机制)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------
# 阶段 2: 最终运行阶段 (Final Stage)
# 目的: 只包含运行时必要的组件，进一步减小镜像体积和攻击面。
# ------------------------------------------------------------
# 从一个更小的、只包含运行库的 Python 镜像开始
FROM python:3.12-slim

# 设置时区和工作目录（与构建阶段保持一致）
# 重要：在最终阶段也需要设置这些环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

WORKDIR /code

# 安装时区数据包（支持 TZ 环境变量）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tzdata \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制安装好的 Python 依赖 (这是多阶段构建的关键!)
# 它只复制最终编译和安装好的文件，不复制中间的编译工具链 (如gcc)
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# 复制你的应用源码
# 这是白名单复制，只包含应用的核心代码
COPY ./app /code/app

# (可选) 如果你需要执行本地脚本（如自动化模块），可以添加一个 scripts 目录
# COPY ./scripts /code/scripts 

# 声明容器暴露的端口
EXPOSE 8000

# 最终启动命令
# 1. 开发时: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# 2. 生产时: gunicorn -k uvicorn.workers.UvicornWorker -c config/gunicorn.py main:app
# 默认使用 Uvicorn 作为启动命令，方便你本地开发和调试。
# 在 docker-compose.yml 中，我们可以轻松地覆盖它为生产级的 Gunicorn。
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
