"""
进程管理路由
提供服务状态检测、服务关闭（自毁模式）、Windows 开机自启动管理
"""
import os
import socket
import subprocess
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/process", tags=["process"])

# ── 项目根目录 ──
ROOT = Path(__file__).resolve().parents[3]
AUTOSTART_VBS_BACKEND = ROOT / "autostart_backend.vbs"
AUTOSTART_VBS_FULL = ROOT / "autostart_full.vbs"
PID_FILE = ROOT / "taskm.pid"
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_NAME = "TaskM Backend"


# ── 辅助方法 ──

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

    # VBS 中用 "" 转义内部的双引号
    vbs_cmd = pythonw_path + ' "' + run_py + '"'
    vbs_cmd_escaped = vbs_cmd.replace('"', '""')

    if not AUTOSTART_VBS_BACKEND.exists():
        lines = [
            "' TaskM Backend Auto-Start (backend only)",
            "Set WshShell = CreateObject(\"WScript.Shell\")",
            'WshShell.Run "' + vbs_cmd_escaped + '", 0, False',
            "",
        ]
        AUTOSTART_VBS_BACKEND.write_text("\r\n".join(lines), encoding="utf-8")

    if not AUTOSTART_VBS_FULL.exists():
        lines = [
            "' TaskM Backend Auto-Start (full)",
            "Set WshShell = CreateObject(\"WScript.Shell\")",
            'WshShell.Run "' + vbs_cmd_escaped + '", 0, False',
            "WScript.Sleep 8000",
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


def _kill_process_on_port(port: int):
    """根据端口号杀死进程及其子进程树（Windows）"""
    try:
        result = subprocess.run(
            f'netstat -ano | findstr ":{port} " | findstr LISTENING',
            shell=True, capture_output=True, text=True
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


def _kill_by_pid_file():
    """通过 PID 文件杀死后端进程（比端口反查更可靠）"""
    try:
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, capture_output=True)
            PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


# ── API ──

class AutostartMode(BaseModel):
    mode: str


@router.get("/status")
def get_status():
    """查询各服务运行状态"""
    return {
        "backend": _port_open(8000),
        "frontend": _port_open(5173),
    }


@router.get("/autostart")
def get_autostart():
    """获取当前开机自启动配置"""
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


# ── 停止服务（自毁模式） ──


@router.post("/stop-backend")
def stop_backend():
    """
    关闭后端服务（自毁模式）
    后端进程自己 os._exit(0) 退出，比外部 taskkill 更可靠
    """
    from app.process_manager import shutdown_service
    # 延迟 500ms 再自毁，让 HTTP 响应先发出去
    threading.Timer(0.5, shutdown_service).start()
    return {"status": "stopped", "service": "backend"}


@router.post("/stop-frontend")
def stop_frontend():
    """关闭前端服务"""
    _kill_process_on_port(5173)
    return {"status": "stopped", "service": "frontend"}


@router.post("/stop-all")
def stop_all():
    """一键关闭前后端服务"""
    _kill_process_on_port(5173)
    from app.process_manager import shutdown_service
    # 延迟 500ms 再自毁，让 HTTP 响应先发出去
    threading.Timer(0.5, shutdown_service).start()
    return {"status": "stopped", "services": ["backend", "frontend"]}
