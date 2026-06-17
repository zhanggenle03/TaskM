"""
TaskM 系统托盘模块
启动后最小化到托盘，右击弹出菜单：打开浏览器 / 退出
支持开发版和打包版

依赖 pystray + Pillow（可选——缺失时托盘不工作但不影响主程序）
"""
import os
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Callable


# ── 路径 ──
BACKEND_DIR = Path(__file__).resolve().parent.parent          # backend/
PROJECT_ROOT = BACKEND_DIR.parent                              # TaskM/


def _is_standalone() -> bool:
    return bool(os.environ.get("TASKM_FRONTEND_DIST"))


def _get_frontend_url() -> str:
    """打包版：8000（前后端同端口）；开发版：5173（Vite 代理）"""
    if _is_standalone():
        return "http://localhost:8000/"
    return "http://localhost:5173/"


def _get_icon_image():
    """
    加载托盘图标
    开发版：backend/taskm.ico；打包版：优先 _MEIPASS/，其次 exe 同目录
    找不到则用 PIL 画占位图标
    """
    from PIL import Image

    candidates = [BACKEND_DIR / "taskm.ico"]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent / "taskm.ico")

    for p in candidates:
        if p.exists():
            return Image.open(str(p))

    # fallback：生成 64x64 蓝色 "T" 占位图标
    from PIL import ImageDraw, ImageFont
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=14,
        fill=(39, 112, 237),
    )
    try:
        font = ImageFont.truetype("msyh.ttc", 36)
    except OSError:
        font = ImageFont.load_default()
    draw.text((size // 2, size // 2), "T", fill="white", font=font, anchor="mm")
    return img


def _open_browser():
    """打开浏览器"""
    url = _get_frontend_url()
    webbrowser.open(url)


def _quit_app():
    """退出应用：先杀前端端口，再自毁退出"""
    import subprocess
    # 杀前端端口 5173（开发版 Vite）
    try:
        result = subprocess.run(
            'netstat -ano | findstr ":5173 " | findstr LISTENING',
            shell=True, capture_output=True, text=True,
        )
        pids = set()
        for line in result.stdout.strip().splitlines():
            parts = line.strip().split()
            if parts:
                pids.add(parts[-1])
        for pid in pids:
            subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, capture_output=True)
    except Exception:
        pass
    from .process_manager import shutdown_service
    shutdown_service()


def start_tray(on_setup: Callable | None = None):
    """
    启动系统托盘（阻塞运行，通常放子线程）
    on_setup: 图标创建完毕后的回调（可用于设置菜单等）
    """
    import pystray

    img = _get_icon_image()
    menu = pystray.Menu(
        pystray.MenuItem("打开浏览器", lambda: _open_browser(), default=True),
        pystray.MenuItem("退出", lambda: _quit_app()),
    )

    icon = pystray.Icon(
        "TaskM",
        img,
        "TaskM — 任务管理系统",
        menu,
    )

    if on_setup:
        on_setup(icon)

    icon.run()


def open_browser_action():
    """供外部（前端/API）调用的打开浏览器"""
    _open_browser()


def quit_action():
    """供外部调用的退出"""
    _quit_app()
