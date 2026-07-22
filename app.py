#!/usr/bin/env python3
"""
Railway 部署入口 —— 启动完整版 SKWM API
直接导入 skwm_platform/backend/api.py
"""
import sys, os
from pathlib import Path

# 把后端目录加进导入路径
BACKEND = Path(__file__).parent / "skwm_platform" / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(str(BACKEND))

# 启动 uvicorn
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api:app", host="0.0.0.0", port=port)
