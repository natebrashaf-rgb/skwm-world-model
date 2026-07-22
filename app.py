#!/usr/bin/env python3
"""
Railway 部署入口 —— 优先启动 SKWM FastAPI，失败则回退到 http.server
自动加载位于 data/ 的全部知识库数据
"""
import sys, os, json
from pathlib import Path

BACKEND = Path(__file__).parent / "skwm_platform" / "backend"

# 确保数据目录可访问
DATA_DIR = Path(__file__).parent / "data"
if DATA_DIR.exists():
    os.environ["SKWM_DATA_DIR"] = str(DATA_DIR)
    print(f"📂 数据目录: {DATA_DIR}")

# 尝试导入 FastAPI 启动
try:
    import fastapi
    import uvicorn
    
    sys.path.insert(0, str(BACKEND))
    os.chdir(str(BACKEND))
    
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 启动 FastAPI 服务 (端口 {port})")
    uvicorn.run("api:app", host="0.0.0.0", port=port)

except ImportError as e:
    print(f"⚠️ FastAPI 未安装 ({e}), 回退到 http.server...")
    
    # 回退到我们原有的 http.server 版本
    sys.path.insert(0, str(Path(__file__).parent))
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs
    
    # 直接导入原有的 Engine
    exec(open(Path(__file__).parent / "app_legacy.py").read())
    
    port = int(os.environ.get("PORT", 8080))
    print(f"🌐 启动 http.server 回退模式 (端口 {port})")
    server = HTTPServer(('0.0.0.0', port), Handler)
    try: server.serve_forever()
    except KeyboardInterrupt: print("\n已停止"); server.server_close()
