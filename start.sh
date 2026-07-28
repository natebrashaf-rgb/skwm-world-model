#!/bin/bash
# start.sh — Railway 启动脚本（纯后端模式）
echo "🚀 启动 SKWM 后端..."
cd /app
PORT=${PORT:-8080}
exec python -m uvicorn skmw_platform.backend.wm_server:app --host 0.0.0.0 --port $PORT --log-level info
