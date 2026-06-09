from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, date, timedelta
import json

from ..database import (
    get_db, Project, Requirement, RequirementCustomField, RequirementCustomValue,
    RequirementStatusPool, RequirementPriorityPool,
    Task, StatusPool, touch_project, resolve_project,
    generate_requirement_display_id,
)
from ..schemas import (
    RequirementCreate, RequirementUpdate, RequirementOut,
    RequirementCustomFieldCreate, RequirementCustomFieldUpdate, RequirementCustomFieldOut,
    RequirementCustomValueOut,
    RequirementStatusPoolCreate, RequirementStatusPoolUpdate, RequirementStatusPoolOut,
    RequirementPriorityPoolCreate, RequirementPriorityPoolUpdate, RequirementPriorityPoolOut,
    StatusDistribution, PriorityDistribution, TrendPoint,
    ProjectProgress, UpcomingDeadline, DashboardData,
)

router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])


# ========== 自定义字段 CRUD ==========

@router.get("/fields", response_model=List[RequirementCustomFieldOut])
def list_custom_fields(
    project_id: str,
    show_inactive: bool = False,
    db: Session = Depends(get_db),
):
    proj = resolve_project(db, project_id)
    q = db.query(RequirementCustomField).filter(
        RequirementCustomField.project_id == proj.id
    )
    if not show_inactive:
        q = q.filter(RequirementCustomField.is_active == True)
    return q.order_by(RequirementCustomField.sort_order).all()


@router.post("/fields", response_model=RequirementCustomFieldOut)
def create_custom_field(
    project_id: str,
    data: RequirementCustomFieldCreate,
    db: Session = Depends(get_db),
):
    proj = resolve_project(db, project_id)

    # 检查是否存在同名非活动字段，有则自动激活
    existing = db.query(RequirementCustomField).filter(
        RequirementCustomField.project_id == proj.id,
        RequirementCustomField.field_name == data.field_name,
        RequirementCustomField.is_active == False,
    ).first()
    if existing:
        existing.is_active = True
        existing.field_type = data.field_type
        existing.field_options = data.field_options
        existing.sort_order = data.sort_order
        db.commit()
        db.refresh(existing)
        touch_project(db, proj.id)
        return existing

    field = RequirementCustomField(
        project_id=proj.id,
        field_name=data.field_name,
        field_type=data.field_type,
        field_options=data.field_options,
        sort_order=data.sort_order,
    )
    db.add(field)
    db.commit()
    db.refresh(field)
    touch_project(db, proj.id)
    return field


@router.put("/fields/{field_id}", response_model=RequirementCustomFieldOut)
def update_custom_field(
    project_id: str,
    field_id: int,
    data: RequirementCustomFieldUpdate,
    db: Session = Depends(get_db),
):
    proj = resolve_project(db, project_id)
    field = db.query(RequirementCustomField).filter(
        RequirementCustomField.id == field_id,
        RequirementCustomField.project_id == proj.id
    ).first()
    if not field:
        raise HTTPException(404, "自定义字段不存在")
    if data.field_name is not None:
        field.field_name = data.field_name
    if data.field_type is not None:
        field.field_type = data.field_type
    if data.field_options is not None:
        field.field_options = data.field_options
    if data.sort_order is not None:
        field.sort_order = data.sort_order
    db.commit()
    db.refresh(field)
    touch_project(db, proj.id)
    return field


@router.delete("/fields/{field_id}")
def delete_custom_field(
    project_id: str,
    field_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
):
    proj = resolve_project(db, project_id)
    field = db.query(RequirementCustomField).filter(
        RequirementCustomField.id == field_id,
        RequirementCustomField.project_id == proj.id
    ).first()
    if not field:
        raise HTTPException(404, "自定义字段不存在")
    if force:
        db.delete(field)
    else:
        field.is_active = False
    db.commit()
    touch_project(db, proj.id)
    return {"message": "ok"}


# ========== 大屏数据统计 API ==========

@router.get("/stats/dashboard", response_model=DashboardData)
def dashboard_stats(
    project_id: str,
    db: Session = Depends(get_db),
):
    proj = resolve_project(db, project_id)

    # 1. 需求状态分布
    status_counts = db.query(
        Requirement.status, func.count(Requirement.id)
    ).filter(
        Requirement.project_id == proj.id
    ).group_by(Requirement.status).all()

    status_label_map = {
        "todo": "待处理",
        "in_progress": "进行中",
        "done": "已完成",
        "cancelled": "已取消",
    }
    status_distribution = [
        StatusDistribution(name=status_label_map.get(s, s), value=c)
        for s, c in status_counts
    ]

    # 2. 需求优先级分布
    priority_counts = db.query(
        Requirement.priority, func.count(Requirement.id)
    ).filter(
        Requirement.project_id == proj.id
    ).group_by(Requirement.priority).all()

    priority_label_map = {
        "low": "低",
        "normal": "普通",
        "high": "高",
        "urgent": "紧急",
    }
    priority_distribution = [
        PriorityDistribution(name=priority_label_map.get(p, p), value=c)
        for p, c in priority_counts
    ]

    # 3. 项目进度概览（任务状态分布）
    status_pools = db.query(StatusPool).filter(
        StatusPool.project_id == proj.id,
        StatusPool.is_active == True,
    ).all()
    project_progress = []
    for sp in status_pools:
        count = db.query(Task).filter(
            Task.project_id == proj.id,
            Task.status_id == sp.id,
        ).count()
        if count > 0:
            project_progress.append(ProjectProgress(
                name=sp.name, value=count, color=sp.color
            ))

    # 4. 近期截止需求（未来7天内或已过期）
    today = date.today()
    week_later = today + timedelta(days=7)
    upcoming = db.query(Requirement).filter(
        Requirement.project_id == proj.id,
        Requirement.due_date.isnot(None),
        Requirement.due_date <= week_later,
        Requirement.status.in_(["todo", "in_progress"]),
    ).order_by(Requirement.due_date.asc()).limit(10).all()
    upcoming_deadlines = [
        UpcomingDeadline(
            id=r.id, title=r.title,
            due_date=r.due_date,
            priority=r.priority, status=r.status,
        ) for r in upcoming
    ]

    # 5. 需求趋势（按周统计创建量，最近10周）
    trend_data = []
    for i in range(9, -1, -1):
        week_start = today - timedelta(days=today.weekday()) - timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        count = db.query(func.count(Requirement.id)).filter(
            Requirement.project_id == proj.id,
            Requirement.created_at >= datetime.combine(week_start, datetime.min.time()),
            Requirement.created_at <= datetime.combine(week_end, datetime.max.time()),
        ).scalar() or 0
        trend_data.append(TrendPoint(
            date=week_start.strftime("%m/%d"),
            count=count,
        ))

    return DashboardData(
        status_distribution=status_distribution,
        priority_distribution=priority_distribution,
        project_progress=project_progress,
        upcoming_deadlines=upcoming_deadlines,
        trend=trend_data,
    )


# ========== 辅助函数 ==========

def _get_requirement_with_values(db: Session, req_id: int) -> RequirementOut:
    req = db.query(Requirement).options(
        joinedload(Requirement.custom_values).joinedload(RequirementCustomValue.field)
    ).filter(Requirement.id == req_id).first()
    return _format_requirement(req) if req else None


def _format_requirement(req: Requirement) -> RequirementOut:
    vals = []
    for cv in req.custom_values:
        vals.append(RequirementCustomValueOut(
            field_id=cv.field_id,
            field_name=cv.field.field_name if cv.field else "",
            field_type=cv.field.field_type if cv.field else "",
            value=cv.value,
        ))
    return RequirementOut(
        id=req.id,
        project_id=req.project_id,
        display_id=req.display_id,
        title=req.title,
        description=req.description,
        priority=req.priority,
        status=req.status,
        due_date=req.due_date,
        created_at=req.created_at,
        updated_at=req.updated_at,
        custom_values=vals,
    )


# ========== 需求状态池 ==========

@router.get("/status-pools", response_model=List[RequirementStatusPoolOut])
def list_status_pools(
    project_id: str,
    show_inactive: bool = False,
    db: Session = Depends(get_db),
):
    proj = resolve_project(db, project_id)
    q = db.query(RequirementStatusPool).filter(RequirementStatusPool.project_id == proj.id)
    if not show_inactive:
        q = q.filter(RequirementStatusPool.is_active == True)
    return q.order_by(RequirementStatusPool.sort_order).all()


@router.post("/status-pools", response_model=RequirementStatusPoolOut)
def create_status_pool(
    project_id: str,
    data: RequirementStatusPoolCreate,
    db: Session = Depends(get_db),
):
    proj = resolve_project(db, project_id)
    existing = db.query(RequirementStatusPool).filter(
        RequirementStatusPool.project_id == proj.id,
        RequirementStatusPool.name == data.name,
        RequirementStatusPool.is_active == False,
    ).first()
    if existing:
        existing.is_active = True
        existing.color = data.color
        existing.sort_order = data.sort_order
        existing.is_default = data.is_default
        db.commit()
        db.refresh(existing)
        return existing
    if data.is_default:
        db.query(RequirementStatusPool).filter(
            RequirementStatusPool.project_id == proj.id,
            RequirementStatusPool.is_default == True,
        ).update({"is_default": False})
    pool = RequirementStatusPool(project_id=proj.id, **data.model_dump())
    db.add(pool)
    db.commit()
    db.refresh(pool)
    touch_project(db, proj.id)
    return pool


@router.put("/status-pools/{pool_id}", response_model=RequirementStatusPoolOut)
def update_status_pool(project_id: str, pool_id: int, data: RequirementStatusPoolUpdate, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    pool = db.query(RequirementStatusPool).filter(
        RequirementStatusPool.id == pool_id, RequirementStatusPool.project_id == proj.id
    ).first()
    if not pool:
        raise HTTPException(404, "状态不存在")
    if data.is_default and not pool.is_default:
        db.query(RequirementStatusPool).filter(
            RequirementStatusPool.project_id == proj.id, RequirementStatusPool.is_default == True
        ).update({"is_default": False})
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(pool, k, v)
    db.commit()
    db.refresh(pool)
    return pool


@router.delete("/status-pools/{pool_id}")
def delete_status_pool(
    project_id: str, pool_id: int,
    force: bool = False,
    confirmed: bool = False,
    db: Session = Depends(get_db),
):
    proj = resolve_project(db, project_id)
    pool = db.query(RequirementStatusPool).filter(
        RequirementStatusPool.id == pool_id, RequirementStatusPool.project_id == proj.id
    ).first()
    if not pool:
        raise HTTPException(404, "状态不存在")

    # 默认值不允许停用或删除
    if pool.is_default:
        raise HTTPException(400, "默认值不允许停用或删除，请先设置其他状态为默认值")

    # 硬删除：检查引用数量
    if force:
        # 映射 name → requirement status value
        name_to_value = {"待处理": "todo", "进行中": "in_progress", "已完成": "done", "已取消": "cancelled"}
        status_value = name_to_value.get(pool.name, pool.name)
        ref_count = db.query(func.count(Requirement.id)).filter(
            Requirement.project_id == proj.id,
            Requirement.status == status_value,
        ).scalar() or 0

        if ref_count > 0 and not confirmed:
            raise HTTPException(409, detail={
                "message": "该状态被引用",
                "refs": {"需求": ref_count},
                "refs_cleaned": None,
            })

        if confirmed:
            # 查找默认状态
            default_status = db.query(RequirementStatusPool).filter(
                RequirementStatusPool.project_id == proj.id,
                RequirementStatusPool.is_default == True,
                RequirementStatusPool.id != pool_id,
            ).first()
            default_value = None
            if default_status:
                default_value = name_to_value.get(default_status.name, default_status.name)
            # 重置引用
            db.query(Requirement).filter(
                Requirement.project_id == proj.id,
                Requirement.status == status_value,
            ).update({"status": default_value or "todo"}, synchronize_session=False)

        db.delete(pool)
        db.commit()
        return {"message": "ok", "refs_cleaned": {"需求": ref_count} if ref_count > 0 else {}}

    pool.is_active = False
    db.commit()
    return {"message": "ok"}


# ========== 需求优先级池 ==========

@router.get("/priority-pools", response_model=List[RequirementPriorityPoolOut])
def list_priority_pools(
    project_id: str,
    show_inactive: bool = False,
    db: Session = Depends(get_db),
):
    proj = resolve_project(db, project_id)
    q = db.query(RequirementPriorityPool).filter(RequirementPriorityPool.project_id == proj.id)
    if not show_inactive:
        q = q.filter(RequirementPriorityPool.is_active == True)
    return q.order_by(RequirementPriorityPool.sort_order).all()


@router.post("/priority-pools", response_model=RequirementPriorityPoolOut)
def create_priority_pool(
    project_id: str,
    data: RequirementPriorityPoolCreate,
    db: Session = Depends(get_db),
):
    proj = resolve_project(db, project_id)
    existing = db.query(RequirementPriorityPool).filter(
        RequirementPriorityPool.project_id == proj.id,
        RequirementPriorityPool.name == data.name,
        RequirementPriorityPool.is_active == False,
    ).first()
    if existing:
        existing.is_active = True
        existing.color = data.color
        existing.sort_order = data.sort_order
        existing.is_default = data.is_default
        db.commit()
        db.refresh(existing)
        return existing
    if data.is_default:
        db.query(RequirementPriorityPool).filter(
            RequirementPriorityPool.project_id == proj.id,
            RequirementPriorityPool.is_default == True,
        ).update({"is_default": False})
    pool = RequirementPriorityPool(project_id=proj.id, **data.model_dump())
    db.add(pool)
    db.commit()
    db.refresh(pool)
    touch_project(db, proj.id)
    return pool


@router.put("/priority-pools/{pool_id}", response_model=RequirementPriorityPoolOut)
def update_priority_pool(project_id: str, pool_id: int, data: RequirementPriorityPoolUpdate, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    pool = db.query(RequirementPriorityPool).filter(
        RequirementPriorityPool.id == pool_id, RequirementPriorityPool.project_id == proj.id
    ).first()
    if not pool:
        raise HTTPException(404, "优先级不存在")
    if data.is_default and not pool.is_default:
        db.query(RequirementPriorityPool).filter(
            RequirementPriorityPool.project_id == proj.id, RequirementPriorityPool.is_default == True
        ).update({"is_default": False})
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(pool, k, v)
    db.commit()
    db.refresh(pool)
    return pool


@router.delete("/priority-pools/{pool_id}")
def delete_priority_pool(
    project_id: str, pool_id: int,
    force: bool = False,
    confirmed: bool = False,
    db: Session = Depends(get_db),
):
    proj = resolve_project(db, project_id)
    pool = db.query(RequirementPriorityPool).filter(
        RequirementPriorityPool.id == pool_id, RequirementPriorityPool.project_id == proj.id
    ).first()
    if not pool:
        raise HTTPException(404, "优先级不存在")

    # 默认值不允许停用或删除
    if pool.is_default:
        raise HTTPException(400, "默认值不允许停用或删除，请先设置其他优先级为默认值")

    # 硬删除：检查引用数量
    if force:
        name_to_value = {"低": "low", "普通": "normal", "高": "high", "紧急": "urgent"}
        priority_value = name_to_value.get(pool.name, pool.name)
        ref_count = db.query(func.count(Requirement.id)).filter(
            Requirement.project_id == proj.id,
            Requirement.priority == priority_value,
        ).scalar() or 0

        if ref_count > 0 and not confirmed:
            raise HTTPException(409, detail={
                "message": "该优先级被引用",
                "refs": {"需求": ref_count},
                "refs_cleaned": None,
            })

        if confirmed:
            default_priority = db.query(RequirementPriorityPool).filter(
                RequirementPriorityPool.project_id == proj.id,
                RequirementPriorityPool.is_default == True,
                RequirementPriorityPool.id != pool_id,
            ).first()
            default_value = None
            if default_priority:
                default_value = name_to_value.get(default_priority.name, default_priority.name)
            db.query(Requirement).filter(
                Requirement.project_id == proj.id,
                Requirement.priority == priority_value,
            ).update({"priority": default_value or "normal"}, synchronize_session=False)

        db.delete(pool)
        db.commit()
        return {"message": "ok", "refs_cleaned": {"需求": ref_count} if ref_count > 0 else {}}

    pool.is_active = False
    db.commit()
    return {"message": "ok"}


# ========== 需求 CRUD ==========

@router.get("", response_model=List[RequirementOut])
def list_requirements(
    project_id: str,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
):
    proj = resolve_project(db, project_id)
    q = db.query(Requirement).options(
        joinedload(Requirement.custom_values).joinedload(RequirementCustomValue.field)
    ).filter(Requirement.project_id == proj.id)

    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if statuses:
            q = q.filter(Requirement.status.in_(statuses))
    if priority:
        priorities = [p.strip() for p in priority.split(",") if p.strip()]
        if priorities:
            q = q.filter(Requirement.priority.in_(priorities))
    if search:
        like = f"%{search}%"
        q = q.filter(
            Requirement.title.like(like) | Requirement.description.like(like)
        )

    # 排序
    sort_map = {
        "updated_at": Requirement.updated_at,
        "created_at": Requirement.created_at,
        "title": Requirement.title,
        "priority": Requirement.priority,
        "status": Requirement.status,
        "due_date": Requirement.due_date,
    }
    sort_col = sort_map.get(sort_by, Requirement.updated_at)
    order_fn = sort_col.desc() if sort_order == "desc" else sort_col.asc()
    # due_date: nulls last
    if sort_by == "due_date":
        from sqlalchemy import nullslast
        order_fn = nullslast(order_fn)

    results = q.order_by(order_fn).all()

    # 组装 custom_values 为嵌套结构
    out = []
    for r in results:
        vals = []
        for cv in r.custom_values:
            vals.append(RequirementCustomValueOut(
                field_id=cv.field_id,
                field_name=cv.field.field_name if cv.field else "",
                field_type=cv.field.field_type if cv.field else "",
                value=cv.value,
            ))
        out.append(RequirementOut(
            id=r.id,
            project_id=r.project_id,
            display_id=r.display_id,
            title=r.title,
            description=r.description,
            priority=r.priority,
            status=r.status,
            due_date=r.due_date,
            created_at=r.created_at,
            updated_at=r.updated_at,
            custom_values=vals,
        ))
    return out


@router.post("", response_model=RequirementOut)
def create_requirement(
    project_id: str,
    data: RequirementCreate,
    db: Session = Depends(get_db),
):
    proj = resolve_project(db, project_id)
    req = Requirement(
        project_id=proj.id,
        display_id=generate_requirement_display_id(db, proj),
        title=data.title,
        description=data.description,
        priority=data.priority,
        status=data.status,
        due_date=data.due_date,
    )
    db.add(req)
    db.flush()  # 获取 req.id

    # 保存自定义字段值
    if data.custom_values:
        for field_id_str, value in data.custom_values.items():
            try:
                fid = int(field_id_str)
            except ValueError:
                continue
            if value is not None and value != "":
                cv = RequirementCustomValue(
                    requirement_id=req.id,
                    field_id=fid,
                    value=str(value),
                )
                db.add(cv)

    db.commit()
    db.refresh(req)
    touch_project(db, proj.id)

    # 重新加载含 custom_values 的完整对象
    return _get_requirement_with_values(db, req.id)


@router.get("/{requirement_id}", response_model=RequirementOut)
def get_requirement(
    project_id: str,
    requirement_id: int,
    db: Session = Depends(get_db),
):
    proj = resolve_project(db, project_id)
    req = db.query(Requirement).options(
        joinedload(Requirement.custom_values).joinedload(RequirementCustomValue.field)
    ).filter(
        Requirement.id == requirement_id,
        Requirement.project_id == proj.id
    ).first()
    if not req:
        raise HTTPException(404, "需求不存在")
    return _format_requirement(req)


@router.put("/{requirement_id}", response_model=RequirementOut)
def update_requirement(
    project_id: str,
    requirement_id: int,
    data: RequirementUpdate,
    db: Session = Depends(get_db),
):
    proj = resolve_project(db, project_id)
    req = db.query(Requirement).filter(
        Requirement.id == requirement_id,
        Requirement.project_id == proj.id
    ).first()
    if not req:
        raise HTTPException(404, "需求不存在")

    if data.title is not None:
        req.title = data.title
    if data.description is not None:
        req.description = data.description
    if data.priority is not None:
        req.priority = data.priority
    if data.status is not None:
        req.status = data.status
    if data.due_date is not None:
        req.due_date = data.due_date

    # 更新自定义字段值
    if data.custom_values is not None:
        for field_id_str, value in data.custom_values.items():
            try:
                fid = int(field_id_str)
            except ValueError:
                continue
            existing = db.query(RequirementCustomValue).filter(
                RequirementCustomValue.requirement_id == req.id,
                RequirementCustomValue.field_id == fid,
            ).first()
            if existing:
                if value is not None and value != "":
                    existing.value = str(value)
                else:
                    db.delete(existing)
            else:
                if value is not None and value != "":
                    cv = RequirementCustomValue(
                        requirement_id=req.id,
                        field_id=fid,
                        value=str(value),
                    )
                    db.add(cv)

    db.commit()
    db.refresh(req)
    touch_project(db, proj.id)
    return _get_requirement_with_values(db, req.id)


@router.delete("/{requirement_id}")
def delete_requirement(
    project_id: str,
    requirement_id: int,
    db: Session = Depends(get_db),
):
    proj = resolve_project(db, project_id)
    req = db.query(Requirement).filter(
        Requirement.id == requirement_id,
        Requirement.project_id == proj.id
    ).first()
    if not req:
        raise HTTPException(404, "需求不存在")
    db.delete(req)
    db.commit()
    touch_project(db, proj.id)
    return {"message": "ok"}
