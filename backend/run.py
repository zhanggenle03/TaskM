#!/usr/bin/env python3
"""启动 TaskM 后端服务 - 单实例保护"""
import os
import sys
import socket
import time
import atexit
import subprocess
import threading

# ── 强制 UTF-8 模式 ──
# pythonw.exe 启动时默认编码是 mbcs/GBK，会导致 openpyxl 读取含中文表头的
# Excel 文件时返回含 surrogate 的字符串，进而污染 JSON 响应。
# 这里把 stdout/stderr 显式切到 utf-8。
# 注意：必须在 import 任何第三方库（尤其 openpyxl）之前完成。
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")  # py3.7+
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── 路径 ──
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)          # TaskM 根目录
PID_FILE = os.path.join(PROJECT_ROOT, "taskm.pid")   # PID 文件路径

# ── 配置 ──
BACKEND_PORT = 8000
MAX_PORT_WAIT = 3  # 最多等待 3 秒释放端口


# ═══════════════════════════════════════════════
#  1) PID 单实例检测
#  注：app/process_manager.py 中有更完善的版本（os.kill + taskkill /F /T）。
#  此处为启动时一次性检测，在 main.py 加载前执行，故独立实现。
# ═══════════════════════════════════════════════

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


def ensure_single_instance():
    """启动时检查 PID 文件，杀死旧进程，然后写入自身 PID"""
    my_pid = os.getpid()

    # ── 读取已有的 PID 文件 ──
    if os.path.isfile(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                old_pid_str = f.read().strip()
            if old_pid_str:
                old_pid = int(old_pid_str)
                if old_pid != my_pid and is_process_alive(old_pid):
                    print(f"[启动] 发现旧进程 PID={old_pid}，正在终止...", flush=True)
                    kill_process(old_pid)
                    time.sleep(1)
        except (ValueError, OSError):
            pass

    # ── 写入自身 PID ──
    try:
        with open(PID_FILE, "w") as f:
            f.write(str(my_pid))
        print(f"[启动] PID 已写入: {my_pid}", flush=True)
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
                print(f"[退出] PID 文件已清理", flush=True)
    except Exception:
        pass


# ═══════════════════════════════════════════════
#  2) 端口检测 & socket 预绑定
# ═══════════════════════════════════════════════

def port_has_listener(port):
    """检查端口上是否还有活动监听者"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(("127.0.0.1", port))
        s.close()
        return result == 0  # 连接成功 = 有人监听
    except Exception:
        return False


def wait_no_listener(port, timeout=MAX_PORT_WAIT):
    """等待端口上的监听者消失"""
    for _ in range(timeout):
        if not port_has_listener(port):
            return True
        print(f"[启动] 端口 {port} 仍被占用，等待释放...", flush=True)
        time.sleep(1)
    return not port_has_listener(port)


def release_port_by_netstat(port):
    """通过 netstat 查找占用端口的进程并强制终止"""
    print(f"[启动] 端口 {port} 仍被占用，尝试通过 netstat 释放...", flush=True)
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
    import socket as sock_mod
    sock = sock_mod.socket(sock_mod.AF_INET, sock_mod.SOCK_STREAM)
    sock.setsockopt(sock_mod.SOL_SOCKET, sock_mod.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(128)
    sock.settimeout(None)
    print(f"[启动] socket 已绑定 {host}:{port}（SO_REUSEADDR=ON）", flush=True)
    return sock


# ═══════════════════════════════════════════════
#  3) 主流程
# ═══════════════════════════════════════════════

# ── 日志重定向（pythonw 无控制台） ──
log_path = os.path.join(BACKEND_DIR, "uvicorn.log")
sys.stderr = open(log_path, "w", encoding="utf-8")
sys.stdout = sys.stderr

# ── 单实例保护 ──
ensure_single_instance()
atexit.register(cleanup_pid)

# ── 等待端口上的旧监听者释放 ──
if not wait_no_listener(BACKEND_PORT):
    print(f"[启动] 端口 {BACKEND_PORT} 被占用，尝试强制释放...", flush=True)
    release_port_by_netstat(BACKEND_PORT)

# ── 预绑定 socket（SO_REUSEADDR 避免 TIME_WAIT 问题） ──
server_sock = bind_server_socket("0.0.0.0", BACKEND_PORT)

# ── 切换工作目录 ──
os.chdir(BACKEND_DIR)

# ── 启动系统托盘（子线程） ──
_tray_thread = None
try:
    from app.tray_icon import start_tray
    _tray_thread = threading.Thread(target=start_tray, daemon=True, name="TrayIcon")
    _tray_thread.start()
    print("[启动] 系统托盘已启动", flush=True)
except Exception as e:
    print(f"[启动] 系统托盘启动失败: {e}", flush=True)

# ── 启动 uvicorn（使用预绑定的 socket） ──
try:
    from uvicorn import Config, Server

    config = Config(
        "app.main:app",
        host="0.0.0.0",
        port=BACKEND_PORT,
        reload=False,
    )
    server = Server(config=config)
    server.run(sockets=[server_sock])
except Exception:
    import traceback
    traceback.print_exc()
    sys.stderr.flush()
