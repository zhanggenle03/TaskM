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
    print(f"[TaskM] 前端资源: {FRONTEND_DIST}", flush=True)
else:
    print(f"[TaskM] 前端资源不存在 ({FRONTEND_DIST})，仅 API 模式", flush=True)

# ============================================================
# 导入 app 主模块（PyInstaller 据此静态追踪依赖）
# 此时 TASKM_FRONTEND_DIST 已就绪，main.py 可正确读取
# ============================================================
from app.main import app

# ── 后端工作目录（确保数据库/上传目录相对于打包后的位置） ──
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BACKEND_DIR)


# ── 隐藏控制台窗口 ──
def _hide_console():
    """通过 Windows API 隐藏当前进程的控制台窗口"""
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass


# ── 启动 uvicorn 生产服务 ──
if __name__ == "__main__":
    import threading
    import webbrowser
    import uvicorn

    # 打包模式：自动弹出浏览器，服务就绪后隐藏控制台
    if getattr(sys, "frozen", False) and os.environ.get("TASKM_FRONTEND_DIST"):
        def _startup_tasks():
            import time
            time.sleep(1.5)  # 等 uvicorn 完全就绪
            _hide_console()   # 隐藏控制台窗口
            webbrowser.open("http://localhost:8000")

        threading.Thread(target=_startup_tasks, daemon=True).start()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
