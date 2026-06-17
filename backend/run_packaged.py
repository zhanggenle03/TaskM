#!/usr/bin/env python3
"""TaskM 打包版本入口（PyInstaller 用）—— 生产环境直接启动"""
import os
import sys

# ── 确定前端 dist 路径（必须先于 from app.main import app） ──
# main.py 在模块加载时会读取 TASKM_FRONTEND_DIST 环境变量来决定
# 是挂载前端静态文件（生产模式）还是返回 API JSON（开发模式）。
# PyInstaller 打包后将前端资源放在 _internal/frontend_dist/ 下
if getattr(sys, "_MEIPASS", None):
    FRONTEND_DIST = os.path.join(sys._MEIPASS, "frontend_dist")
else:
    # 开发/调试模式：从项目根目录下的 frontend/dist 查找
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")

if os.path.isdir(FRONTEND_DIST):
    os.environ["TASKM_FRONTEND_DIST"] = FRONTEND_DIST
    print(f"[打包入口] 前端静态资源路径: {FRONTEND_DIST}", flush=True)
else:
    print(f"[打包入口] 警告：前端资源目录不存在 ({FRONTEND_DIST})，将仅以 API 模式运行", flush=True)

# ============================================================
# 导入 app 主模块（PyInstaller 据此静态追踪依赖）
# 此时 TASKM_FRONTEND_DIST 已就绪，main.py 可正确读取
# ============================================================
from app.main import app

# ── 后端工作目录（确保数据库/上传目录相对于打包后的位置） ──
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BACKEND_DIR)


# ── 启动 uvicorn 生产服务 ──
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,                    # 直接传 app 对象，不再用字符串
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
