"""
进程管理模块
移植自 CloudDiskShareManagement，适配 FastAPI
提供 PID 文件追踪、单实例保护、优雅关闭、自毁式退出
"""
import os
import signal
import subprocess
import time
from pathlib import Path

# ── 路径常量 ──
ROOT = Path(__file__).resolve().parents[2]  # TaskM 项目根目录 (backend/app/ → backend/ → TaskM/)
PID_FILE = ROOT / "taskm.pid"


# ── PID 文件操作 ──

def write_pid():
    """写入当前进程 PID 到文件"""
    try:
        PID_FILE.write_text(str(os.getpid()))
    except Exception:
        pass


def read_pid():
    """读取 PID 文件，失败返回 None"""
    try:
        if PID_FILE.exists():
            return int(PID_FILE.read_text().strip())
    except (ValueError, IOError):
        pass
    return None


def remove_pid():
    """删除 PID 文件"""
    try:
        if PID_FILE.exists():
            PID_FILE.remove()
    except Exception:
        pass


# ── 进程状态检查 ──

def is_process_alive(pid):
    """检查进程是否存活（信号0不杀进程，只检测存在性）"""
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


# ── 进程终止 ──

def kill_process(pid):
    """强制终止进程及其子进程树（Windows taskkill /F /T）"""
    if pid is None:
        return True
    try:
        result = subprocess.run(
            f'taskkill /F /T /PID {pid}',
            shell=True, capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def terminate_process(pid, timeout=3.0):
    """优雅终止：先 SIGTERM，超时后 taskkill /F /T"""
    if pid is None or not is_process_alive(pid):
        return True

    # 阶段1: SIGTERM
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass

    # 阶段2: 等待退出
    start = time.time()
    while time.time() - start < timeout:
        if not is_process_alive(pid):
            return True
        time.sleep(0.1)

    # 阶段3: 强制终止
    return kill_process(pid)


# ── 单实例保护 ──

def ensure_single_instance():
    """
    确保只有一个实例运行
    发现旧进程 → 先杀 → 删 PID 文件 → 继续
    """
    old_pid = read_pid()

    if old_pid is None:
        return True

    if old_pid == os.getpid():
        return True

    if is_process_alive(old_pid):
        terminate_process(old_pid, timeout=3.0)

    remove_pid()
    return True


# ── 服务关闭 ──

def shutdown_service():
    """
    自毁式关闭（最可靠）
    清理 PID 文件 → os._exit(0) 立刻退出
    """
    remove_pid()
    os._exit(0)


def graceful_shutdown():
    """优雅关闭：发 SIGTERM 让进程自行清理"""
    try:
        os.kill(os.getpid(), signal.SIGTERM)
    except OSError:
        pass


# ── 启动/关闭钩子 ──

def on_startup():
    """应用启动时调用：单实例保护 + 写 PID"""
    ensure_single_instance()  # 先检查/杀旧进程
    remove_pid()              # 清理旧 PID 文件
    write_pid()               # 写入当前 PID


def on_shutdown():
    """应用关闭时调用：清理 PID 文件"""
    remove_pid()
