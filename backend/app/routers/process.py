"""
进程管理路由
提供服务状态检测、Windows 开机自启动管理、服务关闭
"""
import os
import socket
import subprocess
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..settings_manager import load_settings, save_settings

router = APIRouter(prefix="/process", tags=["process"])

# ── 项目根目录 ──
ROOT = Path(__file__).resolve().parents[3]
AUTOSTART_VBS_BACKEND = ROOT / "autostart_backend.vbs"
AUTOSTART_VBS_FULL = ROOT / "autostart_full.vbs"
PID_FILE = ROOT / "taskm.pid"
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_NAME = "TaskM Backend"


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


def _read_registry() -> str | None:
    """读取开机自启动配置，返回 'backend' / 'full' / None"""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, REG_NAME)
        winreg.CloseKey(key)

        if not isinstance(val, str):
            return None

        vl = val.lower()
        if "autostart_full.vbs" in vl:
            return "full"
        if "autostart_backend.vbs" in vl:
            return "backend"
        if "pythonw" in vl and "run.py" in vl:
            return "backend"
        return None
    except (ImportError, FileNotFoundError, OSError):
        return None


def _ensure_vbs_scripts():
    """确保自启动 VBS 脚本存在"""
    import shutil

    run_py = str(ROOT / "backend" / "run.py")
    frontend_dir = str(ROOT / "frontend")

    # 自动检测 pythonw 路径
    pythonw_path = shutil.which("pythonw")
    if not pythonw_path:
        # 常见安装位置 fallback
        for p in [
            r"D:\python310\pythonw.exe",
            r"C:\python310\pythonw.exe",
            r"C:\Python310\pythonw.exe",
            r"C:\Program Files\Python310\pythonw.exe",
            r"C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\pythonw.exe",
        ]:
            expanded = os.path.expandvars(p)
            if os.path.exists(expanded):
                pythonw_path = expanded
                break
    if not pythonw_path:
        pythonw_path = "pythonw"  # 找不到就用系统 PATH

    # 检测 npx 路径
    npx_path = shutil.which("npx.cmd") or shutil.which("npx") or "npx.cmd"

    # VBS 中用 "" 转义内部的双引号
    vbs_pythonw_cmd = pythonw_path + ' "' + run_py + '"'
    vbs_pythonw_escaped = vbs_pythonw_cmd.replace('"', '""')
    vbs_frontend_cmd = f'cmd /c cd /d "{frontend_dir}" && "{npx_path}" vite'
    vbs_frontend_escaped = vbs_frontend_cmd.replace('"', '""')

    # 始终重新生成 VBS 脚本（确保内容最新）
    # backend 版本：启动后端+前端，不打开浏览器
    lines = [
        "' TaskM Auto-Start (both services, no browser)",
        "Set WshShell = CreateObject(\"WScript.Shell\")",
        "' Start backend",
        'WshShell.Run "' + vbs_pythonw_escaped + '", 0, False',
        "' Start frontend",
        'WshShell.Run "' + vbs_frontend_escaped + '", 0, False',
        "",
    ]
    AUTOSTART_VBS_BACKEND.write_text("\r\n".join(lines), encoding="utf-8")

    # full 版本：启动后端+前端，然后打开浏览器
    lines = [
        "' TaskM Auto-Start (both services with browser)",
        "Set WshShell = CreateObject(\"WScript.Shell\")",
        "' Start backend",
        'WshShell.Run "' + vbs_pythonw_escaped + '", 0, False',
        "' Start frontend",
        'WshShell.Run "' + vbs_frontend_escaped + '", 0, False',
        "' Wait for services to be ready",
        "WScript.Sleep 10000",
        "' Open browser",
        'WshShell.Run "http://localhost:5173/", 1, False',
        "",
    ]
    AUTOSTART_VBS_FULL.write_text("\r\n".join(lines), encoding="utf-8")


def _write_registry(mode: str | None):
    """写入/删除自启动注册表项"""
    import winreg

    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)

    if mode is None:
        try:
            winreg.DeleteValue(key, REG_NAME)
        except OSError:
            pass
    else:
        _ensure_vbs_scripts()
        if mode == "backend":
            cmd = 'wscript.exe "' + str(AUTOSTART_VBS_BACKEND) + '"'
        else:
            cmd = 'wscript.exe "' + str(AUTOSTART_VBS_FULL) + '"'
        winreg.SetValueEx(key, REG_NAME, 0, winreg.REG_SZ, cmd)

    winreg.CloseKey(key)


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
    """获取当前开机自启动配置"""
    _ensure_vbs_scripts()
    mode = _read_registry()
    return {"enabled": mode is not None, "mode": mode or "off"}


@router.put("/autostart")
def set_autostart(body: AutostartMode):
    """设置开机自启动
    mode: 'backend' / 'full' / 'off'
    """
    if body.mode not in ("backend", "full", "off"):
        raise HTTPException(400, "mode 必须为 backend / full / off")

    try:
        if body.mode == "off":
            _write_registry(None)
        else:
            _write_registry(body.mode)
    except Exception as e:
        raise HTTPException(500, f"设置开机自启动失败: {e}")

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
