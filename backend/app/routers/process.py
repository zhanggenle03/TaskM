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
from ..settings_manager import load_settings, save_settings

router = APIRouter(prefix="/process", tags=["process"])

# ── 项目根目录 ──
ROOT = Path(__file__).resolve().parents[3]
PID_FILE = ROOT / "taskm.pid"

# ── 自启动路径 ──
AUTOSTART_DIR = ROOT
STARTUP_FOLDER = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
STARTUP_BAT_NAME = "TaskM_Autostart.bat"
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
    """检测开发版组件路径：pythonw / npx — 优先使用 D:\python310"""
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
    npx_path = shutil.which("npx.cmd") or shutil.which("npx") or "npx.cmd"
    return pythonw_path, npx_path


def _generate_autostart_bat() -> str:
    """生成自启动批处理内容（仅启动服务，不打开浏览器——托盘接管）"""
    import shutil
    project_root = str(ROOT)

    if _is_standalone():
        exe = str(Path(sys.executable).resolve())
        return f'@echo off\r\nstart "" /b "{exe}"\r\n'
    else:
        pythonw_path, npx_path = _detect_components()
        frontend_dir = str(ROOT / "frontend")
        return (
            f'@echo off\r\n'
            f'cd /d "{project_root}"\r\n'
            f'start "" /b "{pythonw_path}" -X utf8 backend\\run.py\r\n'
            f'start "" /b cmd /c cd /d "{frontend_dir}" && "{npx_path}" vite\r\n'
        )


def _check_startup_bat() -> bool:
    """检查启动文件夹中是否有自启动批处理文件"""
    return (STARTUP_FOLDER / STARTUP_BAT_NAME).exists()


def _enable_autostart():
    """在启动文件夹创建自启动批处理文件"""
    dst = STARTUP_FOLDER / STARTUP_BAT_NAME
    STARTUP_FOLDER.mkdir(parents=True, exist_ok=True)
    dst.write_text(_generate_autostart_bat(), encoding="utf-8")
    print(f"[autostart] Created {dst}", flush=True)


def _disable_autostart():
    """删除启动文件夹中的自启动批处理文件"""
    bat = STARTUP_FOLDER / STARTUP_BAT_NAME
    if bat.exists():
        bat.unlink()
        print(f"[autostart] Removed {bat}", flush=True)
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
    backend_up = _port_open(8000)
    if _is_standalone():
        return {
            "backend": backend_up,
            "frontend": backend_up,
            "standalone": True,
        }
    return {
        "backend": backend_up,
        "frontend": _port_open(5173),
        "standalone": False,
    }


@router.get("/autostart")
def get_autostart():
    """获取当前开机自启动状态（基于启动文件夹批处理文件）"""
    enabled = _check_startup_bat()
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
    """更新通用设置（仅传入需要修改的字段）"""
    data = {}
    if body.max_file_size_mb is not None:
        if body.max_file_size_mb < 1 or body.max_file_size_mb > 500:
            raise HTTPException(400, "max_file_size_mb 必须在 1~500 之间")
        data["max_file_size_mb"] = body.max_file_size_mb
    return save_settings(data)


@router.post("/shutdown")
def shutdown():
    """关闭 TaskM 服务（开发版同时 kill 前端端口，2 秒后退出进程）"""
    if not _is_standalone():
        _kill_port(5173)
    from app.process_manager import shutdown_service
    threading.Timer(2.0, shutdown_service).start()
    return {"status": "shutting_down"}
