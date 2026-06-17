"""
TaskM 系统托盘模块
启动后最小化到托盘，右击弹出菜单：打开浏览器 / 退出
支持开发版和打包版
"""
import os
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Callable

import pystray
from PIL import Image, ImageDraw, ImageFont


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
    """加载托盘图标（优先使用 backend/taskm.ico，不存在则生成占位图标）"""
    ico_path = BACKEND_DIR / "taskm.ico"
    if ico_path.exists():
        return Image.open(str(ico_path))

    # fallback：生成 64x64 蓝色 "T" 占位图标
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
    """退出应用"""
    from .process_manager import shutdown_service
    # 直接自毁式退出
    shutdown_service()


def start_tray(on_setup: Callable[[pystray.Icon], None] | None = None):
    """
    启动系统托盘（阻塞运行，通常放子线程）
    on_setup: 图标创建完毕后的回调（可用于设置菜单等）
    """
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
