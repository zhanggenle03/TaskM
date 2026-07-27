"""服务端节假日缓存服务

设计：本地数据库优先（read-through），后台异步刷新（带 diff）。

  - 持久化：SQLite 的 holiday_base 表（与 taskm.db 同库），重启后立即可用。
  - 内存热缓存 _CACHE：启动时由 holiday_base 表预热，请求路径只读它，毫秒级、绝不在请求线程里联网。
  - 读取路径（同步、不阻塞）：get_year(year) 直接返回 _CACHE；缺失返回 None。
  - 刷新路径（异步、不阻塞）：当某年缺失时被触发，后台线程去 timor.tech 拉取，
    与已存数据做整年 JSON 比对，有变化才 upsert 回 holiday_base 表 + 更新 _CACHE；无变化跳过写。
  - 旧缓存文件 holiday_cache.json 仅在「数据库为空」时做一次迁移导入，之后以数据库为唯一真相源。

触发时机（按用户决策：无 TTL）：
  - 应用启动：预热「当前年-3 ~ 当前年+2」窗口，仅对缺失年份联网补拉。
  - 请求命中缺失年份：get_holidays 立即返回（不阻塞），并 fire-and-forget 后台补拉，下次即命中。
"""

import os
import json
import threading
from datetime import datetime

import urllib.request

from .database import BASE_DIR, SessionLocal, HolidayBase

CACHE_FILE = os.path.join(BASE_DIR, "holiday_cache.json")
TIMOR_API = "https://timor.tech/api/holiday/year/{}"
_FETCH_TIMEOUT = 6  # 秒：单次外部请求超时，避免阻塞后台线程

_lock = threading.Lock()
_CACHE = {}          # year(str) -> holiday dict（内存热缓存）
_refreshing = set()  # 正在后台拉取的年份（去重，避免同一年并发重复拉）


# ---------- 数据库读写 ----------

def _upsert_db(year, data):
    """写入/更新单年数据到 holiday_base，并同步内存缓存。"""
    try:
        db = SessionLocal()
        payload = json.dumps(data, ensure_ascii=False)
        row = db.query(HolidayBase).filter(HolidayBase.year == int(year)).first()
        if row:
            if row.data != payload:
                row.data = payload
                row.fetched_at = datetime.now()
                db.commit()
        else:
            db.add(HolidayBase(year=int(year), data=payload, fetched_at=datetime.now()))
            db.commit()
        with _lock:
            _CACHE[str(year)] = data
    except Exception as e:
        print(f"[holiday] 写入数据库失败 {year}: {e}", flush=True)
    finally:
        db.close()


def load_from_db():
    """启动时从 holiday_base 表载入所有年份到内存缓存（毫秒级、本地）。"""
    global _CACHE
    try:
        db = SessionLocal()
        rows = db.query(HolidayBase).all()
        cache = {}
        for r in rows:
            try:
                cache[str(r.year)] = json.loads(r.data)
            except Exception:
                pass
        if cache:
            _CACHE = cache
            print(f"[holiday] 已从数据库载入 {len(cache)} 年节假日缓存", flush=True)
    except Exception as e:
        print(f"[holiday] 从数据库载入缓存失败: {e}", flush=True)
    finally:
        db.close()


def _migrate_json_if_needed():
    """一次性迁移：若 holiday_base 为空且旧 json 缓存存在，则导入，避免重复联网。"""
    try:
        db = SessionLocal()
        if db.query(HolidayBase).count() > 0:
            return
        if not os.path.exists(CACHE_FILE):
            return
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        for y, d in data.items():
            _upsert_db(y, d)
        print(f"[holiday] 已从 holiday_cache.json 迁移 {len(data)} 年数据到 holiday_base", flush=True)
    except Exception as e:
        print(f"[holiday] 迁移 json 失败(可忽略): {e}", flush=True)
    finally:
        db.close()


# ---------- 外部拉取 ----------

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
    """后台拉取某年，与本地(库)比对，有变化才写库。返回是否成功。"""
    hol = _fetch_year(year)
    if not hol:
        with _lock:
            _refreshing.discard(str(year))
        return False

    # diff：与已存数据整年比对，相同则跳过写
    changed = True
    try:
        db = SessionLocal()
        row = db.query(HolidayBase).filter(HolidayBase.year == int(year)).first()
        if row:
            try:
                if json.loads(row.data) == hol:
                    changed = False
            except Exception:
                changed = True
    except Exception:
        pass
    finally:
        db.close()

    if changed:
        _upsert_db(year, hol)
        print(f"[holiday] {year} 年数据已更新并落库", flush=True)
    else:
        with _lock:
            _CACHE.setdefault(str(year), hol)

    with _lock:
        _refreshing.discard(str(year))
    return True


def get_year(year):
    """读取已缓存的某年数据（可能为空）；只读内存，绝不联网。"""
    with _lock:
        return _CACHE.get(str(year))


def ensure_year_async(year):
    """缺失年份：后台非阻塞拉取（fire-and-forget），不阻塞当前请求。"""
    y = str(year)
    with _lock:
        if y in _CACHE or y in _refreshing:
            return
        _refreshing.add(y)
    t = threading.Thread(target=refresh_year, args=(year,), daemon=True)
    t.start()


def prefetch_on_startup():
    """应用启动时调用：从数据库预热 → 迁移旧 json（若需）→ 后台补拉窗口内缺失年份。"""
    load_from_db()
    _migrate_json_if_needed()
    this_year = datetime.now().year
    years = list(range(this_year - 3, this_year + 3))  # 当前年-3 ~ 当前年+2

    def _worker():
        # 仅补充本地缺失的年份（不重复拉已有数据，无 TTL）
        for y in years:
            with _lock:
                have = str(y) in _CACHE
            if not have:
                refresh_year(y)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
