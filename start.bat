@echo off
chcp 65001 >nul
cd /d %~dp0
echo [SeaArt] 安装依赖 (flask / flask-cors / requests / zhipuai)...
python -m pip install -r backend/requirements.txt
echo.
echo [SeaArt] 默认绘图后端：智谱 AI (DRAW_BACKEND=zhipu)
echo [SeaArt] 如需切换 Agnes AI，请将下方 DRAW_BACKEND 改为 agnes，
echo          并在 backend/.env 中配置 AGNES_API_KEY / AGNES_MODEL（agnes-image-* 图像模型）
set DRAW_BACKEND=zhipu
echo [SeaArt] 启动服务： http://127.0.0.1:5000
python backend/app.py
pause
