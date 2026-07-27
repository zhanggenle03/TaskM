"""请假记录 CRUD（年假/调休/请假，与签到独立）。

路由前缀 /api/leave，由 main.py 注册（prefix="/api/leave"）：
- GET    /api/leave           列表（支持 year+month / 单日 date / 区间 start~end 过滤）
- GET    /api/leave/workdays  预览某范围内「应上班的工作日」数量与日期（自动排除周末/法定假，含调休班）
- POST   /api/leave           新增：把 [date, date_end] 范围内每个工作日落一条独立记录（每条 date_end=NULL、days=1.0），
                              就像「批量签到」——每天一条，彼此独立，可单独编辑/删除，无组概念。
- PUT    /api/leave/{id}      编辑单条（即当天）
- DELETE /api/leave/{id}      删除单条

设计要点：
- 每条请假 = 一天 = 一条记录，与 checkin 完全同构。多日请假提交时后端按「应上班的工作日」逐日生成多条，
  但彼此独立、无 group_id 关联，编辑/删除任意一天互不影响。
- 「应上班的工作日」判定与前端日历一致：手动覆盖 > 法定假/调休班(timor) > 周末。
  即：法定假 & 普通周末 & 覆盖为休息 = 休息日（不计入）；普通工作日 & 调休班 & 覆盖为上班 = 工作日（计入）。
"""

import calendar
from datetime import date as date_cls, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import SessionLocal, Leave, Checkin, HolidayOverride
from ..holiday_service import get_year

router = APIRouter(tags=["leave"])


# ---------- 休息日判定（与前端日历一致） ----------
def _is_rest_day(d: date_cls) -> bool:
    """该日期是否为休息日（不算作应上班的工作日）。

    优先级：用户手动覆盖 > timor 法定假/调休班 > 周末。
    """
    db = SessionLocal()
    try:
        ov = db.query(HolidayOverride).filter(HolidayOverride.date == d).first()
        if ov:
            t = ov.override_type
            if t == "off":
                return True
            if t in ("normal", "workday"):
                return False
            if t == "holiday":
                return True
    finally:
        db.close()
    data = get_year(d.year)
    mmdd = d.strftime("%m-%d")
    if data and mmdd in data:
        return bool(data[mmdd].get("holiday"))
    return d.weekday() >= 5


def _working_days(start: date_cls, end: date_cls) -> List[date_cls]:
    """返回 [start, end] 闭区间内所有「应上班的工作日」（已排除休息日）。"""
    if start > end:
        start, end = end, start
    out = []
    cur = start
    while cur <= end:
        if not _is_rest_day(cur):
            out.append(cur)
        cur += timedelta(days=1)
    return out


def _date_available(d: date_cls, exclude_leave_id: int = None) -> bool:
    """该日期是否可以添加请假记录：当天不能有签到，也不能有其他请假。"""
    db = SessionLocal()
    try:
        if db.query(Checkin).filter(Checkin.date == d).first():
            return False
        q = db.query(Leave).filter(Leave.date == d)
        if exclude_leave_id:
            q = q.filter(Leave.id != exclude_leave_id)
        if q.first():
            return False
        return True
    finally:
        db.close()


# ---------- 序列化 ----------
def _serialize(r: Leave) -> dict:
    return {
        "id": r.id,
        "date": r.date.isoformat(),
        "date_end": r.date_end.isoformat() if r.date_end else None,
        "leave_type": r.leave_type,
        "subtype": r.subtype,
        "days": r.days,
        "reason": r.reason,
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _parse(d: str):
    y, m, dd = map(int, d.split("-"))
    return date_cls(y, m, dd)


# ---------- 请求体 ----------
class LeaveCreate(BaseModel):
    date: str                      # YYYY-MM-DD（起始日）
    date_end: Optional[str] = None  # YYYY-MM-DD（结束日，含）；与 date 相同或不填=单日
    leave_type: str = "personal"   # annual | compensatory | personal
    subtype: Optional[str] = None
    days: float = 1.0              # 兼容字段；逐日记录恒为 1.0，此处忽略
    reason: Optional[str] = None


class LeaveUpdate(BaseModel):
    date: Optional[str] = None
    leave_type: Optional[str] = None
    subtype: Optional[str] = None
    days: Optional[float] = None
    reason: Optional[str] = None


# ---------- 接口 ----------
@router.get("")
def list_leaves(year: Optional[int] = None, month: Optional[int] = None, date: Optional[str] = None,
                start_date: Optional[str] = None, end_date: Optional[str] = None):
    """列出请假记录。每条记录就是一天，过滤逻辑为精确日期比对（无区间重叠复杂度）。"""
    db = SessionLocal()
    try:
        q = db.query(Leave)
        if start_date and end_date:
            s, e = _parse(start_date), _parse(end_date)
            q = q.filter(Leave.date >= s, Leave.date <= e)
        elif date:
            d = _parse(date)
            q = q.filter(Leave.date == d)
        elif year and month:
            _, last = calendar.monthrange(year, month)
            m_start = date_cls(year, month, 1)
            m_end = date_cls(year, month, last)
            q = q.filter(Leave.date >= m_start, Leave.date <= m_end)
        rows = q.order_by(Leave.date, Leave.id).all()
        return [_serialize(r) for r in rows]
    finally:
        db.close()


@router.get("/workdays")
def preview_workdays(start_date: str, end_date: Optional[str] = None):
    """预览 [start_date, end_date] 内应上班的工作日数量与具体日期（用于弹窗自动算天数）。"""
    start = _parse(start_date)
    end = _parse(end_date) if end_date else start
    days = _working_days(start, end)
    return {"count": len(days), "dates": [d.isoformat() for d in days]}


@router.post("")
def create_leave(payload: LeaveCreate):
    start = _parse(payload.date)
    end = _parse(payload.date_end) if payload.date_end else start
    workdays = _working_days(start, end)
    if not workdays:
        raise HTTPException(
            status_code=400,
            detail="所选范围内没有需要上班的工作日（已全部是周末/法定假），未创建请假记录",
        )
    # 逐日检查可用性：当天已有签到或已有请假 → 冲突
    conflicts = []
    available = []
    for d in workdays:
        if _date_available(d):
            available.append(d)
        else:
            conflicts.append(d.isoformat())
    if conflicts and not available:
        raise HTTPException(
            status_code=409,
            detail=f"所选日期均已被占用：{', '.join(conflicts)}（已有签到或请假记录）",
        )
    db = SessionLocal()
    try:
        created = []
        for d in available:
            rec = Leave(
                date=d,
                date_end=None,
                leave_type=payload.leave_type,
                subtype=payload.subtype,
                days=1.0,
                reason=payload.reason,
                status="recorded",
            )
            db.add(rec)
            created.append(rec)
        db.commit()
        for rec in created:
            db.refresh(rec)
        result = {
            "created": [_serialize(r) for r in created],
            "count": len(created),
        }
        if conflicts:
            result["conflicts"] = conflicts
        return result
    finally:
        db.close()


@router.put("/{leave_id}")
def update_leave(leave_id: int, payload: LeaveUpdate):
    db = SessionLocal()
    try:
        rec = db.query(Leave).filter(Leave.id == leave_id).first()
        if not rec:
            raise HTTPException(status_code=404, detail="请假记录不存在")
        if payload.date is not None:
            new_date = _parse(payload.date)
            if not _date_available(new_date, exclude_leave_id=leave_id):
                raise HTTPException(status_code=409, detail=f"{new_date.isoformat()} 当天已有签到或请假记录")
            rec.date = new_date
        for f in ("leave_type", "subtype", "days", "reason"):
            v = getattr(payload, f)
            if v is not None:
                setattr(rec, f, v)
        rec.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(rec)
        return _serialize(rec)
    finally:
        db.close()


@router.delete("/{leave_id}")
def delete_leave(leave_id: int):
    db = SessionLocal()
    try:
        rec = db.query(Leave).filter(Leave.id == leave_id).first()
        if not rec:
            raise HTTPException(status_code=404, detail="请假记录不存在")
        db.delete(rec)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


class _LeaveBatchDelete(BaseModel):
    ids: List[int]


@router.post("/batch-delete")
def batch_delete_leaves(data: _LeaveBatchDelete):
    db = SessionLocal()
    try:
        count = db.query(Leave).filter(Leave.id.in_(data.ids)).delete(synchronize_session=False)
        db.commit()
        return {"ok": True, "deleted": count}
    finally:
        db.close()
