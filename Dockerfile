FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
# - libgomp1: faiss-cpu 运行时需要
# - fonts-noto-cjk: PDF 导出中文字体需要
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码（.dockerignore 排除不必要的文件）
COPY . .

# 暴露端口
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
