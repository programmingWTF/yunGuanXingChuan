FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
# - 换用国内镜像源（国内服务器/ NAS 访问 deb.debian.org 极慢，会导致 apt 卡死）
# - libgomp1: faiss-cpu 运行时需要
# - fonts-noto-cjk: PDF 导出中文字体（换源后在线安装即可）
RUN sed -i -e 's|deb.debian.org|mirrors.aliyun.com|g' -e 's|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（使用阿里云 PyPI 镜像，国内服务器/NAS 访问 pypi.org 极慢）
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

# 复制项目代码（.dockerignore 排除不必要的文件）
COPY . .

# ADMIN_MODE=true：tzb-admin 独立管理后台镜像（使用 dist-admin 前端产物；
# 后端只挂 /api/admin/* 且不校验身份，认证交给 Cloudflare Access）
ARG ADMIN_MODE=false
RUN if [ "$ADMIN_MODE" = "true" ]; then \
      rm -rf frontend/dist && mv frontend/dist-admin frontend/dist; \
    fi

# 暴露端口
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
