# ============================================================
# SeaArt AI - 容器镜像
# 适用于 Render / Railway / Fly.io (均支持 Docker 部署)
# 应用通过环境变量 PORT 监听 (平台自动注入)，默认 5000
# ============================================================
FROM python:3.12-slim

WORKDIR /app

# 先装依赖，利用镜像层缓存
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# 拷贝后端与前端
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# 应用监听 0.0.0.0:${PORT}，PORT 由平台注入
EXPOSE 5000

CMD ["python", "backend/app.py"]
