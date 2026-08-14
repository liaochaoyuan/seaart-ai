#!/bin/bash
cd "$(dirname "$0")"
echo "[SeaArt] 安装依赖..."
pip install -r backend/requirements.txt
echo "[SeaArt] 默认绘图后端：智谱 AI (DRAW_BACKEND=zhipu)"
echo "[SeaArt] 切换 Agnes AI: export DRAW_BACKEND=agnes 并在 backend/.env 配置 AGNES_API_KEY / AGNES_MODEL"
export DRAW_BACKEND=zhipu
echo "[SeaArt] 启动服务： http://127.0.0.1:5000"
python3 backend/app.py
