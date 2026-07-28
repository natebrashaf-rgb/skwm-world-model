#!/bin/bash
# start.sh — Railway 启动脚本（纯后端模式）
echo "🚀 启动 SKWM 后端..."
cd /app
pip install fastapi uvicorn networkx chromadb -q 2>/dev/null
python -m uvicorn skwm_platform.backend.wm_server:app --host 0.0.0.0 --port 8000 --log-level info
