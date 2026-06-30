#!/usr/bin/env python3
"""TaskM 打包版本入口（PyInstaller 用）—— 生产环境直接启动"""
import os
import sys
import socket as sock_mod
import time
import atexit
import subprocess
import threading

from app.settings_manager import get_port, save_settings

# ── 配置 ──
BACKEND_PORT = get_port("backend_port", 8000)
MAX_PORT_WAIT = 3  # 最多等待 3 秒释放端口

# ── 持久化当前端口配置到 settings.json（发行版前后端同端口，只存一个） ──
save_settings({"backend_port": BACKEND_PORT})


# ═══════════════════════════════════════════════
#  端口检测 & 释放（移植自 run.py）
#  目的：在 uvicorn 绑定端口前，确保端口空闲，
#  避免因旧进程残留或 TIME_WAIT 导致的 EADDRINUSE。
# ═══════════════════════════════════════════════

def port_has_listener(port):
    """检查端口上是否还有活动监听者"""
    try:
        s = sock_mod.socket(sock_mod.AF_INET, sock_mod.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(("127.0.0.1", port))
        s.close()
        return result == 0
    except Exception:
        return False


def wait_no_listener(port, timeout=MAX_PORT_WAIT):
    """等待端口上的监听者消失"""
    for _ in range(timeout):
        if not port_has_listener(port):
            return True
        print(f"[TaskM] 端口 {port} 仍被占用，等待释放...", flush=True)
        time.sleep(1)
    return not port_has_listener(port)


def kill_process(pid):
    """强制终止进程"""
    try:
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            capture_output=True, timeout=5,
        )
        return True
    except Exception:
        return False


def release_port_by_netstat(port):
    """通过 netstat 查找占用端口的进程并强制终止"""
    print(f"[TaskM] 端口 {port} 仍被占用，尝试通过 netstat 释放...", flush=True)
    try:
        r = subprocess.run(
            f'for /f "tokens=5" %p in (\'netstat -ano ^| findstr ":{port} " ^| findstr "LISTENING"\') do @echo %p',
            shell=True, capture_output=True, text=True, timeout=5,
        )
        pids = set()
        for line in r.stdout.strip().splitlines():
            line = line.strip()
            if line.isdigit():
                pids.add(int(line))
        for pid in pids:
            print(f"  -> 终止 PID={pid}", flush=True)
            kill_process(pid)
            time.sleep(0.5)
        return wait_no_listener(port, timeout=2)
    except Exception as e:
        print(f"  -> netstat 释放失败: {e}", flush=True)
        return False


def bind_server_socket(host, port):
    """创建配置了 SO_REUSEADDR 的服务器 socket（可绕过 TIME_WAIT）"""
    sock = sock_mod.socket(sock_mod.AF_INET, sock_mod.SOCK_STREAM)
    sock.setsockopt(sock_mod.SOL_SOCKET, sock_mod.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(128)
    sock.settimeout(None)
    print(f"[TaskM] socket 已绑定 {host}:{port}（SO_REUSEADDR=ON）", flush=True)
    return sock


# ═══════════════════════════════════════════════
#  PID 单实例保护（移植自 run.py）
#  目的：检查 taskm.pid 中的旧进程是否存活，
#  若存活则先 kill，再写入自身 PID，避免多实例冲突。
# ═══════════════════════════════════════════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR) if not getattr(sys, "frozen", False) else BASE_DIR
PID_FILE = os.path.join(PROJECT_ROOT, "taskm.pid")


def is_process_alive(pid):
    """检查 Windows 进程是否存活"""
    try:
        r = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True, timeout=3,
        )
        return str(pid) in r.stdout
    except Exception:
        return False


def ensure_single_instance():
    """启动时检查 PID 文件，杀死旧进程，然后写入自身 PID"""
    my_pid = os.getpid()
    if os.path.isfile(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                old_pid_str = f.read().strip()
            if old_pid_str:
                old_pid = int(old_pid_str)
                if old_pid != my_pid and is_process_alive(old_pid):
                    print(f"[TaskM] 发现旧进程 PID={old_pid}，正在终止...", flush=True)
                    kill_process(old_pid)
                    time.sleep(1)
        except (ValueError, OSError):
            pass
    try:
        with open(PID_FILE, "w") as f:
            f.write(str(my_pid))
        print(f"[TaskM] PID 已写入: {my_pid}", flush=True)
    except OSError as e:
        print(f"[警告] 无法写入 PID 文件: {e}", flush=True)


def cleanup_pid():
    """退出时清理 PID 文件"""
    try:
        if os.path.isfile(PID_FILE):
            with open(PID_FILE, "r") as f:
                content = f.read().strip()
            if content == str(os.getpid()):
                os.remove(PID_FILE)
                print(f"[TaskM] PID 文件已清理", flush=True)
    except Exception:
        pass


# ═══════════════════════════════════════════════
#  前端资源路径
# ═══════════════════════════════════════════════

if getattr(sys, "_MEIPASS", None):
    FRONTEND_DIST = os.path.join(sys._MEIPASS, "frontend_dist")
else:
    _BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    FRONTEND_DIST = os.path.join(_BASE, "frontend", "dist")

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
os.chdir(BASE_DIR)


# ── 隐藏控制台窗口（FreeConsole 彻底断开，非 SW_HIDE） ──
def _hide_console():
    """断开进程与控制台的连接，CMD 窗口立即关闭"""
    try:
        import ctypes
        log_path = os.path.join(BASE_DIR, "taskm.log")
        fh = open(log_path, "w", encoding="utf-8", buffering=1)
        sys.stdout = fh
        sys.stderr = fh
        print(f"[TaskM] 日志文件: {log_path}", flush=True)
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass


# ── 启动 uvicorn 生产服务 ──
if __name__ == "__main__":
    from uvicorn import Config, Server

    # ── 1) 单实例保护：杀旧进程 → 写自身 PID ──
    ensure_single_instance()
    atexit.register(cleanup_pid)

    # ── 2) 等待端口释放：检测端口占用 → 等待 → netstat 强制释放 ──
    if not wait_no_listener(BACKEND_PORT):
        print(f"[TaskM] 端口 {BACKEND_PORT} 被占用，尝试强制释放...", flush=True)
        release_port_by_netstat(BACKEND_PORT)

    # ── 3) 预绑定 socket（SO_REUSEADDR 避免 TIME_WAIT） ──
    server_sock = bind_server_socket("0.0.0.0", BACKEND_PORT)

    # ── 4) 后台线程：服务就绪后 → 隐藏控制台 + 启动系统托盘 ──
    is_frozen = getattr(sys, "frozen", False)

    def _on_startup():
        time.sleep(1.5)
        if is_frozen:
            print("\n" + "=" * 48, flush=True)
            print("  服务已启动完成，点击托盘图标打开浏览器", flush=True)
            print("=" * 48 + "\n", flush=True)
            time.sleep(2)
            _hide_console()
        try:
            from app.tray_icon import start_tray
            tray_thread = threading.Thread(target=start_tray, daemon=True, name="TrayIcon")
            tray_thread.start()
            print("[TaskM] 托盘已启动", flush=True)
        except (ImportError, Exception) as e:
            print(f"[TaskM] 托盘未启动（缺少 pystray/Pillow）: {e}", flush=True)

    threading.Thread(target=_on_startup, daemon=True).start()

    # ── 5) 使用预绑定的 socket 启动 uvicorn（不再直接 bind 端口） ──
    config = Config(
        app,
        host="0.0.0.0",
        port=BACKEND_PORT,
        reload=False,
        log_level="info",
    )
    server = Server(config=config)
    server.run(sockets=[server_sock])
