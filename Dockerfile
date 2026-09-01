# ============================================================
# 云观星传 — 多阶段构建：镜像内自动构建前端 + 后端
# 用法：docker compose up -d --build （clone 后即可一键运行）
#   ADMIN_MODE=true → 构建 tzb-admin 独立管理后台镜像
# ============================================================

# ── 阶段一：前端构建（普通版 + admin 版）────────────────────
FROM node:20-alpine AS frontend-build
WORKDIR /fe
# 先只拷贝依赖清单，利用 Docker layer 缓存
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --registry=https://registry.npmmirror.com
# 拷贝前端源码并构建
COPY frontend/ ./
# 普通版（科研工作台）
RUN npm run build
# admin 版（VITE_ADMIN_MODE=true 分流，main.tsx 渲染 AdminConsole）
# 注意：先保留普通版产物，再构建 admin 版并改名，两版都要留给运行时阶段
RUN mv dist dist-main && \
    VITE_ADMIN_MODE=true npm run build && mv dist dist-admin && mv dist-main dist

# ── 阶段二：后端运行时 ─────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（国内镜像源，NAS 访问 deb.debian.org 极慢）
# - libgomp1: faiss-cpu 运行时需要
# - fonts-noto-cjk: PDF 导出中文字体
RUN sed -i -e 's|deb.debian.org|mirrors.aliyun.com|g' -e 's|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（阿里云 PyPI 镜像）
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

# 复制项目代码（.dockerignore 排除不必要的文件）
COPY . .

# 用镜像内构建的前端产物覆盖（保证 clone 后一定有 dist / dist-admin）
COPY --from=frontend-build /fe/dist /app/frontend/dist
COPY --from=frontend-build /fe/dist-admin /app/frontend/dist-admin

# 确保 PDF 中文字体可用：若 config/fonts/ 下无字体，
# 从系统字体目录（fonts-noto-cjk 已安装）复制一份到项目内嵌路径
RUN if [ ! -f config/fonts/NotoSansSC-Regular.ttf ]; then \
      mkdir -p config/fonts && \
      find /usr/share/fonts -name "NotoSansCJK-Regular.ttc" -o -name "NotoSansSC-Regular.otf" -o -name "NotoSansSC-Regular.ttf" 2>/dev/null | head -1 | xargs -I{} cp "{}" config/fonts/NotoSansSC-Regular.ttc 2>/dev/null || true; \
    fi

# ADMIN_MODE=true：tzb-admin 独立管理后台镜像（使用 dist-admin 前端产物；
# 后端只挂 /api/admin/* 且不校验身份，认证交给 Cloudflare Access）
ARG ADMIN_MODE=false
RUN if [ "$ADMIN_MODE" = "true" ]; then \
      rm -rf frontend/dist && mv frontend/dist-admin frontend/dist; \
    fi

# 暴露端口
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]