#!/bin/bash
# start.sh — Railway 启动脚本
# 同时运行 FastAPI 后端 + Next.js 前端

echo "🚀 安装依赖..."
cd skwm_platform/next_app && npm install --include=dev 2>/dev/null | tail -1

echo "🏗️ 构建 Next.js..."
npx next build 2>/dev/null | tail -3 &

echo "🐍 安装 Python 依赖..."
cd /app
pip install fastapi uvicorn networkx chromadb sentence-transformers 2>/dev/null | tail -1

echo "🎯 启动 FastAPI (端口 8000)..."
cd /app
python -m uvicorn skwm_platform.backend.wm_server:app --host 0.0.0.0 --port 8000 --log-level warning &

sleep 3

echo "🌐 启动 Next.js (端口 3000)..."
cd /app/skwm_platform/next_app
npx next start -p 3000 &

# 等待任一进程退出
wait
