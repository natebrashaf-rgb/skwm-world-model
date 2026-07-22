#!/usr/bin/env python3
"""
Railway 部署入口 —— SKWM 世界模型 API
"""
import sys, os, json
from pathlib import Path

BACKEND = Path(__file__).parent / "skwm_platform" / "backend"
DATA_DIR = Path(__file__).parent / "data"
if DATA_DIR.exists():
    os.environ["SKWM_DATA_DIR"] = str(DATA_DIR)

try:
    import fastapi, uvicorn
    sys.path.insert(0, str(BACKEND))
    os.chdir(str(BACKEND))
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("api:app", host="0.0.0.0", port=port)
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from app_legacy import main as legacy_main
    legacy_main()
