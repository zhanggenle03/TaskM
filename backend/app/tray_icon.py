"""
TaskM 系统托盘模块
启动后最小化到托盘，右击弹出菜单：打开浏览器 / 打开工作目录 / 退出
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
_BACKEND_DIR = Path(__file__).resolve().parent.parent          # backend/
if getattr(sys, "frozen", False):
    # 打包版：sys.executable 指向 exe，其父目录为项目根目录
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    # 开发版：从 __file__ 层级推断项目根目录
    PROJECT_ROOT = _BACKEND_DIR.parent                          # TaskM/


def _is_standalone() -> bool:
    return bool(os.environ.get("TASKM_FRONTEND_DIST"))


def _get_frontend_url() -> str:
    """打包版：backend_port（前后端同端口）；开发版：frontend_port（Vite 代理）"""
    from .settings_manager import get_port
    bp = get_port("backend_port", 8000)
    fp = get_port("frontend_port", 5173)
    if _is_standalone():
        return f"http://localhost:{bp}/"
    return f"http://localhost:{fp}/"


def _get_icon_image():
    """
    加载托盘图标
    开发版：backend/taskm.ico；打包版：优先 _MEIPASS/，其次 exe 同目录
    找不到则用 PIL 画占位图标
    """
    from PIL import Image

    candidates = [_BACKEND_DIR / "taskm.ico"]
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


def _open_workspace():
    """在资源管理器中打开工作文件夹并激活窗口"""
    import ctypes
    workspace = os.path.normpath(str(PROJECT_ROOT))
    ctypes.windll.shell32.ShellExecuteW(None, "explore", workspace, None, None, 1)


def _quit_app():
    """退出应用：统一走 trigger_shutdown（2 秒后杀进程树自毁）。

    与设置页「关闭服务」行为一致——先释放前端端口（仅开发版），
    延迟 2 秒让前端检测到后端消失并弹出遮罩，再杀掉整个后端进程树。
    """
    from .routers.process import trigger_shutdown
    trigger_shutdown()


def start_tray(on_setup: Callable | None = None):
    """
    启动系统托盘（阻塞运行，通常放子线程）
    on_setup: 图标创建完毕后的回调（可用于设置菜单等）
    """
    import pystray

    img = _get_icon_image()
    menu = pystray.Menu(
        pystray.MenuItem("打开浏览器", lambda: _open_browser(), default=True),
        pystray.MenuItem("打开工作目录", lambda: _open_workspace()),
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


def open_workspace_action():
    """供外部调用的打开工作目录"""
    _open_workspace()


def quit_action():
    """供外部调用的退出"""
    _quit_app()
