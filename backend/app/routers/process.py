"""
进程管理路由
提供服务状态检测、Windows 开机自启动管理、服务关闭
"""
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..settings_manager import get_port, load_settings, save_settings

router = APIRouter(prefix="/process", tags=["process"])

# ── 端口配置 ──
_BACKEND_PORT = get_port("backend_port", 8000)
_FRONTEND_PORT = get_port("frontend_port", 5173)

# ── 项目根目录 ──
ROOT = Path(__file__).resolve().parents[3]
PID_FILE = ROOT / "taskm.pid"

# ── 自启动路径 ──
AUTOSTART_DIR = ROOT
STARTUP_FOLDER = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
STARTUP_SCRIPT_NAME = "TaskM_Autostart.vbs"
AUTOSTART_SETTINGS_KEY = "autostart"
AUTOSTART_LEGACY_LNK = "TaskM.lnk"  # 旧版快捷方式，清理用


# ── 辅助方法 ──

def _is_standalone() -> bool:
    """检测是否为打包版（前后端合并到同一端口）"""
    return bool(os.environ.get("TASKM_FRONTEND_DIST"))


def _port_open(port: int) -> bool:
    """检查本地端口是否正在监听（支持 IPv4 和 IPv6）"""
    for host, family in [("127.0.0.1", socket.AF_INET), ("::1", socket.AF_INET6)]:
        try:
            s = socket.socket(family, socket.SOCK_STREAM)
            s.settimeout(0.5)
            result = s.connect_ex((host, port))
            s.close()
            if result == 0:
                return True
        except Exception:
            continue
    return False


def _kill_port(port: int):
    """根据端口号杀死监听进程及其子进程树（Windows）"""
    try:
        result = subprocess.run(
            f'netstat -ano | findstr ":{port} " | findstr LISTENING',
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


def _detect_components():
    """检测开发版组件路径：pythonw / node 目录 — 优先使用已知可靠路径"""
    if _is_standalone():
        return None, None
    import shutil
    # 优先指定路径（避免 WorkBuddy 管理的 Python 路径被误用）
    pythonw_path = None
    for p in [r"D:\python310\pythonw.exe", r"C:\python310\pythonw.exe",
              r"C:\Python310\pythonw.exe", r"C:\Program Files\Python310\pythonw.exe",
              r"C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\pythonw.exe"]:
        expanded = os.path.expandvars(p)
        if os.path.exists(expanded):
            pythonw_path = expanded
            break
    if not pythonw_path:
        pythonw_path = shutil.which("pythonw") or "pythonw"

    # 检测可靠的 Node.js 目录（优先 WorkBuddy 管理的 Node 22，避免开机自启时系统 PATH 中的旧版 Node）
    node_dir = None
    preferred_nodes = [
        r"C:\Users\zhk\.workbuddy\binaries\node\versions\22.22.2",
        r"D:\python310\Scripts",
    ]
    for d in preferred_nodes:
        if os.path.isdir(d) and os.path.isfile(os.path.join(d, "node.exe")) and os.path.isfile(os.path.join(d, "npm.cmd")):
            node_dir = d
            break
    if not node_dir:
        # fallback：取系统 PATH 中的 npx 所在目录
        npx_path = shutil.which("npx.cmd") or shutil.which("npx") or "npx.cmd"
        node_dir = os.path.dirname(os.path.abspath(npx_path))
    return pythonw_path, node_dir


def _generate_autostart_vbs() -> str:
    """生成自启动 VBS 脚本（WScript 静默运行，无控制台窗口）"""
    if _is_standalone():
        exe = str(Path(sys.executable).resolve())
        return f'CreateObject("WScript.Shell").Run "{exe}", 0, False\r\n'
    else:
        pythonw_path, node_dir = _detect_components()
        project_root = str(ROOT)
        frontend_dir = str(ROOT / "frontend")

        # 后端：cd 到项目根目录再启动 pythonw
        backend_cmd_inner = f'cd /d {project_root} && {pythonw_path} -X utf8 backend\\run.py'
        backend_cmd_vbs = f'cmd /c "{backend_cmd_inner}"'.replace('"', '""')

        # 前端：cd 到 frontend 目录，置入可靠 Node 到 PATH，传入端口环境变量，启动 npm
        frontend_cmd_inner = (
            f'cd /d {frontend_dir}'
            f' && set PATH={node_dir};%PATH%'
            f' && set VITE_API_TARGET=http://localhost:{_BACKEND_PORT}'
            f' && set VITE_FRONTEND_PORT={_FRONTEND_PORT}'
            f' && npm run dev'
        )
        frontend_cmd_vbs = f'cmd /c "{frontend_cmd_inner}"'.replace('"', '""')

        # 窗口样式 0 = 隐藏
        return (
            f'CreateObject("WScript.Shell").Run "{backend_cmd_vbs}", 0, False\r\n'
            f'CreateObject("WScript.Shell").Run "{frontend_cmd_vbs}", 0, False\r\n'
        )


def _check_startup_script() -> bool:
    """检查启动文件夹中是否有自启动脚本"""
    return (STARTUP_FOLDER / STARTUP_SCRIPT_NAME).exists()


def _enable_autostart():
    """在启动文件夹创建自启动 VBS 脚本"""
    # 清理旧版 .bat 残留
    old_bat = STARTUP_FOLDER / "TaskM_Autostart.bat"
    if old_bat.exists():
        try: old_bat.unlink()
        except Exception: pass
    dst = STARTUP_FOLDER / STARTUP_SCRIPT_NAME
    STARTUP_FOLDER.mkdir(parents=True, exist_ok=True)
    dst.write_text(_generate_autostart_vbs(), encoding="utf-8")
    print(f"[autostart] Created {dst}", flush=True)


def _disable_autostart():
    """删除启动文件夹中的自启动脚本"""
    script = STARTUP_FOLDER / STARTUP_SCRIPT_NAME
    if script.exists():
        script.unlink()
        print(f"[autostart] Removed {script}", flush=True)
    # 也清理旧 .bat
    old_bat = STARTUP_FOLDER / "TaskM_Autostart.bat"
    if old_bat.exists():
        try: old_bat.unlink()
        except Exception: pass
    _cleanup_legacy()


def _cleanup_legacy():
    """清理旧版自启动残留（.lnk 快捷方式 + 注册表 Run 键 + VBS）"""
    # 旧 lnk
    lnk = STARTUP_FOLDER / AUTOSTART_LEGACY_LNK
    if lnk.exists():
        try: lnk.unlink()
        except Exception: pass
    # 旧注册表
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_SET_VALUE)
        try: winreg.DeleteValue(key, "TaskM Backend")
        except OSError: pass
        winreg.CloseKey(key)
    except Exception:
        pass
    # 旧 VBS
    for vbs in [ROOT / "autostart_backend.vbs", ROOT / "autostart_full.vbs",
                ROOT / "taskm_autostart.bat", ROOT / "taskm_autostart_full.bat"]:
        if vbs.exists():
            try: vbs.unlink()
            except Exception: pass


# ── API ──

class AutostartMode(BaseModel):
    mode: str


@router.get("/status")
def get_status():
    """查询各服务运行状态（打包版前后端合并为同一端口）"""
    backend_up = _port_open(_BACKEND_PORT)
    if _is_standalone():
        return {
            "backend": backend_up,
            "frontend": backend_up,
            "standalone": True,
        }
    return {
        "backend": backend_up,
        "frontend": _port_open(_FRONTEND_PORT),
        "standalone": False,
    }


@router.get("/autostart")
def get_autostart():
    """获取当前开机自启动状态（基于启动文件夹批处理文件）"""
    enabled = _check_startup_script()
    if not enabled:
        saved = load_settings().get(AUTOSTART_SETTINGS_KEY, {})
        saved_mode = saved.get("mode", "off")
        if saved_mode != "off":
            return {"enabled": False, "mode": saved_mode, "saved": True, "pending": True}
    return {"enabled": enabled, "mode": "on" if enabled else "off"}


@router.put("/autostart")
def set_autostart(body: AutostartMode):
    """设置开机自启动：mode = 'on' / 'off'（兼容 'backend'/'full'/'off'）"""
    mode = body.mode
    if mode in ("backend", "full"):
        mode = "on"
    if mode not in ("on", "off"):
        raise HTTPException(400, "mode 必须为 on / off")

    save_settings({AUTOSTART_SETTINGS_KEY: {"mode": mode}})
    try:
        if mode == "off":
            _disable_autostart()
        else:
            _enable_autostart()
    except Exception as e:
        print(f"[autostart] 写入启动文件夹失败（偏好已保存）: {e}", flush=True)
    return get_autostart()


class SettingsUpdate(BaseModel):
    max_file_size_mb: int | None = None
    holiday_overrides: dict | None = None
    entry_date: str | None = None
    backend_port: int | None = None
    frontend_port: int | None = None


class UserSettingsUpdate(BaseModel):
    """用户通用设置（节假日覆盖 + 入职日期）"""
    holiday_overrides: dict | None = None
    entry_date: str | None = None


@router.get("/workspace")
def get_workspace_path():
    """返回项目工作目录的绝对路径"""
    return {"path": os.path.normpath(str(ROOT))}


@router.post("/open-workspace")
def open_workspace():
    """在资源管理器中打开工作文件夹并激活窗口"""
    import ctypes
    workspace = os.path.normpath(str(ROOT))
    # ShellExecuteW with nShowCmd=1 (SW_SHOWNORMAL) 确保窗口弹出到前台
    ctypes.windll.shell32.ShellExecuteW(None, "explore", workspace, None, None, 1)
    return {"status": "ok", "path": workspace}


@router.get("/settings")
def get_settings():
    """获取所有通用设置"""
    return load_settings()


@router.put("/settings")
def update_settings(body: SettingsUpdate):
    """更新通用设置"""
    data = {}
    if body.max_file_size_mb is not None:
        if body.max_file_size_mb < 1 or body.max_file_size_mb > 500:
            raise HTTPException(400, "max_file_size_mb 必须在 1~500 之间")
        data["max_file_size_mb"] = body.max_file_size_mb
    if body.holiday_overrides is not None:
        data["holiday_overrides"] = body.holiday_overrides
    if body.entry_date is not None:
        data["entry_date"] = body.entry_date
    if body.backend_port is not None:
        if body.backend_port < 1024 or body.backend_port > 65535:
            raise HTTPException(400, "backend_port 必须在 1024~65535 之间")
        data["backend_port"] = body.backend_port
    if body.frontend_port is not None:
        if body.frontend_port < 1024 or body.frontend_port > 65535:
            raise HTTPException(400, "frontend_port 必须在 1024~65535 之间")
        data["frontend_port"] = body.frontend_port
    return save_settings(data)


@router.put("/settings/user")
def update_user_settings(body: UserSettingsUpdate):
    """更新用户级设置（节假日覆盖 + 入职日期）"""
    data = {}
    if body.holiday_overrides is not None:
        if not isinstance(body.holiday_overrides, dict):
            raise HTTPException(400, "holiday_overrides 必须为对象")
        data["holiday_overrides"] = body.holiday_overrides
    if body.entry_date is not None:
        if body.entry_date and (not isinstance(body.entry_date, str) or len(body.entry_date) != 10):
            raise HTTPException(400, "entry_date 格式必须为 YYYY-MM-DD")
        data["entry_date"] = body.entry_date
    return save_settings(data)


@router.post("/shutdown")
def shutdown():
    """关闭 TaskM 服务（开发版同时 kill 前端端口，2 秒后退出进程）"""
    if not _is_standalone():
        _kill_port(_FRONTEND_PORT)
    from app.process_manager import shutdown_service
    threading.Timer(2.0, shutdown_service).start()
    return {"status": "shutting_down"}
