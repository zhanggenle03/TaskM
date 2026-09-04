"""副本编辑共享模块：沟通附件 / 需求正文文件 / 文件管理独立上传 三类文件统一副本编辑。

流程：
  1) open_edit：复制原件到 %TEMP%/taskm_edit/（副本名=原始文件名），加逻辑锁（edit_lock 列），
     由调用方 os.startfile 打开副本；
  2) 编辑期间：原件被逻辑锁拦住所有 UI 写操作（删除/重命名/移动/再次编辑）；
  3) commit_edit：校验副本归属与扩展名 → 原子覆盖原件 → 更新 file_size → 清 Office 转换缓存 → 清锁；
  4) discard_edit：删除副本、清锁。

设计取舍：使用「逻辑锁 + 回写前 mtime 校验」，不持有物理文件句柄。
  - 本地单用户工具下足够稳健，且不干扰预览/下载；
  - 跨请求/异常关闭有 EDIT_TTL_MINUTES 超时兜底，不会永久锁死；
  - 回写前校验原件 mtime，防止用户在编辑期间手动篡改原件（逻辑锁只拦 UI 操作）。
"""
import os
import json
import shutil
import tempfile
from datetime import datetime, timedelta
from fastapi import HTTPException

# 锁超时（分钟）：超时自动释放，防异常关闭/长时间未提交导致原件永久锁死
EDIT_TTL_MINUTES = 180
EDIT_DIR = os.path.join(tempfile.gettempdir(), "taskm_edit")

# 文件名非法字符（Windows）
_ILLEGAL = set('\\/:*?"<>|')


def _ensure_edit_dir():
    os.makedirs(EDIT_DIR, exist_ok=True)
    return EDIT_DIR


def _now_iso():
    return datetime.utcnow().isoformat()


def _parse_lock(edit_lock):
    """解析锁 JSON；超时或非法返回 None（调用方据此视为未锁）。"""
    if not edit_lock:
        return None
    try:
        lock = json.loads(edit_lock)
    except Exception:
        return None
    locked_at = lock.get("locked_at")
    if not locked_at:
        return None
    try:
        ts = datetime.fromisoformat(locked_at)
    except Exception:
        return None
    if datetime.utcnow() - ts > timedelta(minutes=EDIT_TTL_MINUTES):
        return None
    return lock


def is_locked(rec):
    return _parse_lock(getattr(rec, "edit_lock", None)) is not None


def raise_if_locked(rec, kind="文件"):
    if is_locked(rec):
        raise HTTPException(423, f"该{kind}正在编辑中，请先完成编辑或放弃修改")


def _safe_copy_name(display_name, src_path):
    """副本显示名：去非法字符；缺扩展名则从原件补，保证 Word/WPS 能识别类型。"""
    name = (display_name or os.path.basename(src_path)).strip()
    name = "".join("_" if c in _ILLEGAL else c for c in name) or os.path.basename(src_path)
    if not os.path.splitext(name)[1]:
        ext = os.path.splitext(src_path)[1]
        if ext:
            name += ext
    return name


def open_edit(rec, src_path, display_name=None):
    """开启副本编辑。

    若已有有效锁则拒绝（423）；超时锁自动清除以便重开；否则复制副本 + 加锁。
    返回 (copy_path, display_name)。
    """
    if getattr(rec, "edit_lock", None):
        existing = _parse_lock(rec.edit_lock)
        if existing is not None:
            raise HTTPException(423, "该文件正在编辑中，请先完成编辑或放弃修改")
        rec.edit_lock = None  # 超时锁，清掉以便重开
    _ensure_edit_dir()
    base_name = _safe_copy_name(display_name, src_path)
    base, ext = os.path.splitext(base_name)
    copy_path = os.path.join(EDIT_DIR, base_name)
    i = 1
    while os.path.exists(copy_path):
        copy_path = os.path.join(EDIT_DIR, f"{base} ({i}){ext}")
        i += 1
    shutil.copy2(src_path, copy_path)
    lock = {
        "locked_at": _now_iso(),
        "copy_path": copy_path,
        "display_name": base_name,
        "original_ext": os.path.splitext(src_path)[1].lower(),
        "original_mtime": os.path.getmtime(src_path),
    }
    rec.edit_lock = json.dumps(lock)
    return copy_path, base_name


def _validate_copy(rec, copy_path):
    """校验副本路径合法且属于当前编辑会话（防目录穿越 / 串改）。"""
    if not copy_path or not os.path.isabs(copy_path):
        raise HTTPException(400, "非法的副本路径")
    norm = os.path.normpath(copy_path)
    if not norm.startswith(os.path.normpath(EDIT_DIR)):
        raise HTTPException(400, "副本路径不在编辑临时目录内，拒绝操作")
    lock = _parse_lock(getattr(rec, "edit_lock", None))
    if not lock:
        raise HTTPException(409, "编辑会话已失效或超时，请重新打开编辑")
    if os.path.normpath(lock.get("copy_path", "")) != norm:
        raise HTTPException(400, "副本路径与当前编辑会话不一致")


def commit_edit(rec, src_path, copy_path, force=False):
    """回写副本内容到原件：校验 → 原子覆盖 → 更新 size → 清 Office 缓存 → 清锁。

    force=True 跳过 mtime 冲突校验（前端二次确认后调用）。
    """
    _validate_copy(rec, copy_path)
    if not os.path.isfile(copy_path):
        raise HTTPException(404, "副本文件不存在，可能已被删除")
    lock = json.loads(rec.edit_lock)
    ext = os.path.splitext(copy_path)[1].lower()
    if ext != lock.get("original_ext"):
        raise HTTPException(400, "副本扩展名与原件不一致，拒绝回写")
    # 回写前校验原件未被外部改动（逻辑锁只拦 UI 操作，此处防手动篡改）
    orig_mtime = lock.get("original_mtime")
    if not force and orig_mtime is not None and abs(os.path.getmtime(src_path) - orig_mtime) > 1.0:
        raise HTTPException(
            409,
            "原件在编辑期间被外部修改，回写将覆盖原件内容。请放弃修改以保留原件，或确认覆盖保存。",
        )
    # 原子覆盖：先写临时文件再替换，避免写一半损坏原件
    tmp = src_path + ".taskm_edit_tmp"
    shutil.copy2(copy_path, tmp)
    os.replace(tmp, src_path)
    rec.file_size = os.path.getsize(src_path)
    # 清 Office 转换缓存（同目录同名 .pdf），下次预览重新转换
    pdf_cache = os.path.splitext(src_path)[0] + ".pdf"
    if os.path.isfile(pdf_cache):
        try:
            os.remove(pdf_cache)
        except OSError:
            pass
    rec.edit_lock = None
    try:
        os.remove(copy_path)
    except OSError:
        pass


def discard_edit(rec, copy_path):
    """放弃编辑：删除副本、清锁。"""
    _validate_copy(rec, copy_path)
    try:
        os.remove(copy_path)
    except OSError:
        pass
    rec.edit_lock = None
