"""服务端节假日缓存服务

在应用启动时预取并缓存 timor.tech 的法定节假日数据，
使前端在打开「工作记录」页面之前即可获得数据，
避免页面卡在加载骨架 / 直连外部 API 超时导致的慢。

缓存策略：
  - 内存缓存 _CACHE: { year: { 'MM-DD': {...} } }
  - 持久化到 holiday_cache.json（与 taskm.db 同目录），重启后立即可用
  - 启动时在后台线程刷新当前年及前后一年（带超时，失败静默）
"""
import os
import json
import threading
from datetime import datetime
import urllib.request

from .database import BASE_DIR

CACHE_FILE = os.path.join(BASE_DIR, "holiday_cache.json")
TIMOR_API = "https://timor.tech/api/holiday/year/{}"
_FETCH_TIMEOUT = 6  # 秒：单次外部请求超时，避免阻塞后台线程

_lock = threading.Lock()
_CACHE = {}


def _load_file():
    """启动时从磁盘加载缓存（同步、立即可用）"""
    global _CACHE
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                _CACHE = json.load(f) or {}
    except Exception as e:
        print(f"[holiday] 读取缓存文件失败: {e}", flush=True)
        _CACHE = {}


def _save_file():
    """将内存缓存写回磁盘"""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_CACHE, f, ensure_ascii=False)
    except Exception as e:
        print(f"[holiday] 写入缓存文件失败: {e}", flush=True)


def _fetch_year(year):
    """从 timor.tech 拉取某年数据，成功返回 holiday dict，否则 None"""
    try:
        req = urllib.request.Request(
            TIMOR_API.format(year),
            headers={"User-Agent": "TaskM"},
        )
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("code") == 0 and data.get("holiday"):
            return data["holiday"]
    except Exception as e:
        print(f"[holiday] 拉取 {year} 年失败: {e}", flush=True)
    return None


def refresh_year(year):
    """重新拉取某年并写入缓存 + 落盘。返回是否成功。"""
    hol = _fetch_year(year)
    if hol:
        with _lock:
            _CACHE[str(year)] = hol
        _save_file()
        return True
    return False


def get_year(year):
    """读取已缓存的某年数据（可能为空）"""
    with _lock:
        return _CACHE.get(str(year))


def prefetch_on_startup():
    """应用启动时调用：载入本地缓存文件 + 后台刷新近三年"""
    _load_file()
    this_year = datetime.now().year
    years = [this_year - 1, this_year, this_year + 1]

    def _worker():
        # 第一遍：仅补充本地缺失的年份（快速让缓存可用）
        for y in years:
            with _lock:
                have = str(y) in _CACHE
            if not have:
                refresh_year(y)
        # 第二遍：静默刷新已有年份，保证数据新鲜（如当年节假日微调）
        for y in years:
            refresh_year(y)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
