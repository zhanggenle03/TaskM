from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case, nullslast, select, or_
from typing import List, Optional, Dict
from collections import defaultdict
from datetime import datetime, date, timedelta
import json, os, uuid

from ..database import (
    get_db, Project, Requirement, RequirementCustomField, RequirementCustomValue,
    RequirementStatusPool, RequirementPriorityPool,
    Task, StatusPool, touch_project, resolve_project,
    generate_requirement_display_id, UPLOAD_DIR,
)
from ..schemas import (
    RequirementCreate, RequirementUpdate, RequirementOut,
    RequirementCustomFieldCreate, RequirementCustomFieldUpdate, RequirementCustomFieldOut,
    RequirementCustomValueOut,
    RequirementStatusPoolCreate, RequirementStatusPoolUpdate, RequirementStatusPoolOut,
    RequirementPriorityPoolCreate, RequirementPriorityPoolUpdate, RequirementPriorityPoolOut,
    StatusDistribution, PriorityDistribution, TrendPoint,
    ProjectProgress, DashboardData,
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


# ========== 筛选面板统计 ==========

@router.get("/filter-stats")
def filter_stats(
    project_id: str,
    column_filters: Optional[str] = None,  # JSON: {prop: [values]} 跨列联动
    db: Session = Depends(get_db),
):
    """返回所有可筛选列的独立值及其出现次数（全量数据，不分页）
    若传入 column_filters，则按其他列筛选后再统计（用于跨列联动）。
    """
    proj = resolve_project(db, project_id)
    req_q = db.query(Requirement).filter(
        Requirement.project_id == proj.id
    )

    # 应用跨列筛选（排除当前列的话由前端控制）
    if column_filters:
        try:
            cf_json = json.loads(column_filters)
        except (json.JSONDecodeError, TypeError):
            cf_json = {}
        for prop, values in cf_json.items():
            if not values:
                continue
            if prop == "status":
                req_q = req_q.filter(Requirement.status.in_(values))
            elif prop == "priority":
                req_q = req_q.filter(Requirement.priority.in_(values))
            elif prop == "display_id":
                req_q = req_q.filter(Requirement.display_id.in_(values))
            elif prop == "title":
                req_q = req_q.filter(Requirement.title.in_(values))
            elif prop.startswith("cf_"):
                try:
                    fid = int(prop[3:])
                except ValueError:
                    continue
                cf = db.query(RequirementCustomField).filter(
                    RequirementCustomField.id == fid,
                    RequirementCustomField.project_id == proj.id,
                ).first()
                if not cf:
                    continue
                if cf.field_type in ("date", "datetime"):
                    subq = db.query(RequirementCustomValue.requirement_id).filter(
                        RequirementCustomValue.field_id == fid
                    )
                    like_conds = [RequirementCustomValue.value.like(f"{v}%") for v in values if v]
                    if like_conds:
                        subq = subq.filter(or_(*like_conds))
                    req_q = req_q.filter(Requirement.id.in_(subq))
                else:
                    subq = db.query(RequirementCustomValue.requirement_id).filter(
                        RequirementCustomValue.field_id == fid,
                        RequirementCustomValue.value.in_(values),
                    )
                    req_q = req_q.filter(Requirement.id.in_(subq))

    reqs = req_q.all()

    # 内置列（转换为前端中文标签）
    STATUS_LABELS = {'todo': '待处理', 'in_progress': '进行中', 'done': '已完成', 'cancelled': '已取消'}
    PRIORITY_LABELS = {'low': '低', 'normal': '普通', 'high': '高', 'urgent': '紧急'}
    status_counter = {}
    priority_counter = {}
    display_id_counter = {}
    title_counter = {}
    for r in reqs:
        status_counter[STATUS_LABELS.get(r.status, r.status)] = status_counter.get(STATUS_LABELS.get(r.status, r.status), 0) + 1
        priority_counter[PRIORITY_LABELS.get(r.priority, r.priority)] = priority_counter.get(PRIORITY_LABELS.get(r.priority, r.priority), 0) + 1
        if r.display_id:
            display_id_counter[r.display_id] = display_id_counter.get(r.display_id, 0) + 1
        if r.title:
            title_counter[r.title] = title_counter.get(r.title, 0) + 1

    def fmt(counter):
        return [{"value": k, "count": v} for k, v in sorted(counter.items(), key=lambda x: -x[1])]

    result = {
        "status": fmt(status_counter),
        "priority": fmt(priority_counter),
        "display_id": fmt(display_id_counter),
        "title": fmt(title_counter),
    }

    # 自定义字段
    custom_fields = db.query(RequirementCustomField).filter(
        RequirementCustomField.project_id == proj.id,
        RequirementCustomField.is_active == True,
    ).all()

    for cf in custom_fields:
        cv_counter = {}
        for r in reqs:
            cv = db.query(RequirementCustomValue).filter(
                RequirementCustomValue.requirement_id == r.id,
                RequirementCustomValue.field_id == cf.id,
            ).first()
            if cv and cv.value:
                cv_counter[cv.value] = cv_counter.get(cv.value, 0) + 1
        result[f"cf_{cf.id}"] = fmt(cv_counter)

    return result


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

    # 4. 需求趋势（按周统计创建量，最近10周）
    today = date.today()
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
        description=req.description or "",
        priority=req.priority,
        status=req.status,
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

@router.get("")
def list_requirements(
    project_id: str,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
    status_order: Optional[str] = None,
    priority_order: Optional[str] = None,
    column_filters: Optional[str] = None,  # JSON: {prop: [values]}
    page: int = 1,
    page_size: int = 50,
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
            Requirement.title.like(like)
        )

    # 列筛选（column_filters JSON）
    if column_filters:
        try:
            cf_json = json.loads(column_filters)
        except (json.JSONDecodeError, TypeError):
            cf_json = {}
        for prop, values in cf_json.items():
            if not values:
                continue
            if prop == "status":
                q = q.filter(Requirement.status.in_(values))
            elif prop == "priority":
                q = q.filter(Requirement.priority.in_(values))
            elif prop == "display_id":
                q = q.filter(Requirement.display_id.in_(values))
            elif prop == "title":
                q = q.filter(Requirement.title.in_(values))
            elif prop.startswith("cf_"):
                try:
                    fid = int(prop[3:])
                except ValueError:
                    continue
                # 检查字段类型
                cf = db.query(RequirementCustomField).filter(
                    RequirementCustomField.id == fid,
                    RequirementCustomField.project_id == proj.id,
                ).first()
                if not cf:
                    continue
                if cf.field_type in ("date", "datetime"):
                    # 日期列：前缀匹配 (LIKE)
                    subq = db.query(RequirementCustomValue.requirement_id).filter(
                        RequirementCustomValue.field_id == fid
                    )
                    # 使用 LIKE 前缀匹配每个筛选值
                    like_conds = []
                    for v in values:
                        like_conds.append(RequirementCustomValue.value.like(f"{v}%"))
                    if like_conds:
                        subq = subq.filter(or_(*like_conds))
                    q = q.filter(Requirement.id.in_(subq))
                else:
                    # 非日期列：精确匹配
                    subq = db.query(RequirementCustomValue.requirement_id).filter(
                        RequirementCustomValue.field_id == fid,
                        RequirementCustomValue.value.in_(values),
                    )
                    q = q.filter(Requirement.id.in_(subq))

    # 多列排序：接收逗号分隔的 sort_by 和 sort_order
    # 如 sort_by=priority,status&sort_order=asc,desc → 先按优先级升序，再按状态降序
    sort_map = {
        "updated_at": Requirement.updated_at,
        "created_at": Requirement.created_at,
        "title": Requirement.title,
        "priority": Requirement.priority,
        "status": Requirement.status,
    }

    # 解析 status_order / priority_order 为值→索引映射（用于 CASE 表达式）
    status_idx = {}
    if status_order:
        for i, v in enumerate(status_order.split(",")):
            status_idx[v.strip()] = i
    priority_idx = {}
    if priority_order:
        for i, v in enumerate(priority_order.split(",")):
            priority_idx[v.strip()] = i

    order_clauses = []
    if sort_by and sort_order:
        sort_by_list = [s.strip() for s in sort_by.split(",") if s.strip()]
        sort_order_list = [s.strip() for s in sort_order.split(",") if s.strip()]

        for i, col_name in enumerate(sort_by_list):
            order_dir = sort_order_list[i] if i < len(sort_order_list) else "asc"

            # 自定义字段排序：使用关联子查询取字段值
            if col_name.startswith("cf_"):
                try:
                    field_id = int(col_name.replace("cf_", ""))
                except ValueError:
                    continue
                cv_subq = (
                    select(RequirementCustomValue.value)
                    .where(
                        RequirementCustomValue.requirement_id == Requirement.id,
                        RequirementCustomValue.field_id == field_id,
                    )
                    .correlate(Requirement)
                    .scalar_subquery()
                )
                order_clauses.append(cv_subq.desc() if order_dir == "desc" else cv_subq.asc())
                continue

            col = sort_map.get(col_name)
            if col is None:
                continue

            # 对 status 和 priority 使用 CASE 表达式实现池顺序排序
            if col_name == "status" and status_idx:
                col = case(status_idx, value=Requirement.status)
            elif col_name == "priority" and priority_idx:
                col = case(priority_idx, value=Requirement.priority)
            order_clauses.append(col.desc() if order_dir == "desc" else col.asc())

    # 无活跃排序时默认按更新时间降序
    if not order_clauses:
        order_clauses.append(Requirement.updated_at.desc())

    # 总记录数（分页用）
    total = q.count()

    # 分页
    page = max(1, page)
    page_size = min(max(1, page_size), 9999)
    results = q.order_by(*order_clauses).offset((page - 1) * page_size).limit(page_size).all()

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
            priority=r.priority,
            status=r.status,
            created_at=r.created_at,
            updated_at=r.updated_at,
            custom_values=vals,
        ))
    return {"items": out, "total": total}



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
        priority=data.priority,
        status=data.status,
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


# ---- 富文本图片上传 ----

@router.post("/{requirement_id}/images")
def upload_requirement_image(
    project_id: str,
    requirement_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传富文本编辑器中的图片，返回可访问的 URL"""
    proj = resolve_project(db, project_id)
    req = db.query(Requirement).filter(
        Requirement.id == requirement_id,
        Requirement.project_id == proj.id
    ).first()
    if not req:
        raise HTTPException(404, "需求不存在")

    # 按项目显示ID/需求显示ID 分目录存储
    req_display_id = req.display_id or f"req_{req.id}"
    img_dir = os.path.join(UPLOAD_DIR, proj.display_id, "requirements", req_display_id, "images")
    os.makedirs(img_dir, exist_ok=True)

    # 生成唯一文件名
    ext = os.path.splitext(file.filename)[1] if file.filename else ".png"
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(img_dir, filename)

    content = file.file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    # 返回可访问的 URL（相对 /uploads）
    url = f"/uploads/{proj.display_id}/requirements/{req_display_id}/images/{filename}"
    return {"url": url, "errno": 0}


@router.delete("/{requirement_id}/images/{filename}")
def delete_requirement_image(
    project_id: str,
    requirement_id: int,
    filename: str,
    db: Session = Depends(get_db),
):
    """删除富文本编辑器中的图片文件"""
    proj = resolve_project(db, project_id)
    req = db.query(Requirement).filter(
        Requirement.id == requirement_id,
        Requirement.project_id == proj.id
    ).first()
    if not req:
        raise HTTPException(404, "需求不存在")

    req_display_id = req.display_id or f"req_{req.id}"
    img_dir = os.path.join(UPLOAD_DIR, proj.display_id, "requirements", req_display_id, "images")
    filepath = os.path.join(img_dir, filename)

    if os.path.exists(filepath):
        os.remove(filepath)

    return {"ok": True}


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


# ── Excel 导入 ─────────────────────────────────────────
import openpyxl
from io import BytesIO
from pydantic import BaseModel
from typing import List, Dict, Optional
from fastapi import UploadFile, File, Form

# ──────── 通用 Excel 解析 ────────
def _cell_str(v) -> str:
    """将 Excel 单元格值安全转为字符串，修复 lone surrogate"""
    if v is None:
        return ""
    s = str(v).strip()
    try:
        s.encode("utf-8")
    except UnicodeEncodeError:
        s = s.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="replace").strip()
    return s


def _parse_excel(content: bytes, filename: str = "") -> tuple:
    """
    解析 Excel 内容，返回 (headers, all_rows)。
    headers — 第一行各列文本
    all_rows — 从第二行开始的所有数据行（每行与 headers 等长，空串填充）
    """
    is_xls = filename.lower().endswith(".xls") and not filename.lower().endswith(".xlsx")

    if is_xls:
        # .xls 优先用 xlrd，失败时 fallback 到 openpyxl
        try:
            return _parse_xls(content)
        except HTTPException:
            raise
        except Exception as e_xls:
            try:
                return _parse_xlsx(content)
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(400, f"无法解析 .xls 文件: {e_xls}")
    else:
        # .xlsx 优先用 openpyxl，失败时 fallback 到 xlrd
        try:
            return _parse_xlsx(content)
        except HTTPException:
            raise
        except Exception as e_xlsx:
            try:
                return _parse_xls(content)
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(400, f"无法解析 .xlsx 文件: {e_xlsx}")


def _parse_xlsx(content: bytes) -> tuple:
    """用 openpyxl 解析 .xlsx 内容"""
    wb = openpyxl.load_workbook(BytesIO(content), data_only=True)
    ws = wb.active
    if ws is None:
        wb.close()
        raise HTTPException(400, "Excel 文件没有工作表")

    # 扫描所有有数据的单元格，自行探测行列范围
    # 不依赖 ws.max_column/max_row，因为部分 WPS/非标准 Excel 文件的
    # dimension 可能返回错误值，导致 iter_rows 丢列或空迭代。
    cell_data = {}  # (row, col) -> value
    max_row, max_col = 0, 0
    for (r, c), cell in ws._cells.items():
        if cell.value is not None:
            cell_data[(r, c)] = cell.value
            max_row = max(max_row, r)
            max_col = max(max_col, c)

    if max_row == 0:
        wb.close()
        raise HTTPException(400, "Excel 文件没有数据")

    if max_col == 0:
        wb.close()
        raise HTTPException(400, "Excel 文件没有检测到列")

    # 第一行作表头
    headers = [_cell_str(cell_data.get((1, col))) for col in range(1, max_col + 1)]

    all_rows = []
    for r in range(2, max_row + 1):
        row_vals = [_cell_str(cell_data.get((r, col))) for col in range(1, max_col + 1)]
        all_rows.append(row_vals)

    wb.close()
    return headers, all_rows


def _parse_xls(content: bytes) -> tuple:
    """用 xlrd 解析 .xls 内容（旧版 Excel 格式）"""
    import xlrd
    wb = xlrd.open_workbook(file_contents=content)
    ws = wb.sheet_by_index(0)
    if ws.nrows == 0:
        raise HTTPException(400, "Excel 文件为空")

    first = [str(ws.cell_value(0, c)).strip() for c in range(ws.ncols)]
    all_rows = []
    for r in range(1, ws.nrows):
        row_vals = [str(ws.cell_value(r, c)).strip() if ws.cell_type(r, c) != xlrd.XL_CELL_EMPTY else "" for c in range(ws.ncols)]
        all_rows.append(row_vals)
    return first, all_rows


class ExcelPreviewOut(BaseModel):
    headers: List[str]
    rows: List[List[str]]
    total_rows: int


@router.post("/import/preview")
async def import_preview(
    project_id: str,
    file: UploadFile = File(...),
):
    """上传 Excel 文件，预览表头和前几行数据"""
    content = await file.read()
    if not content:
        raise HTTPException(400, "上传的文件为空")

    filename = file.filename or ""
    try:
        headers, all_rows = _parse_excel(content, filename)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"无法解析 Excel 文件: {e}")

    preview_rows = all_rows[:5]
    return ExcelPreviewOut(
        headers=headers,
        rows=preview_rows,
        total_rows=len(all_rows),
    )


class ColumnMapping(BaseModel):
    target: str  # "title" | "status" | "priority" | "field:{id}" | "new"
    field_name: Optional[str] = None
    field_type: Optional[str] = None
    field_options: Optional[str] = None


def _find_title_col(excel_headers, mapping_dict):
    """从 mapping_dict 中找到标题列的索引"""
    for h, m_obj in mapping_dict.items():
        if m_obj.target == "title" and h in excel_headers:
            return excel_headers.index(h)
    return None


def _detect_file_duplicates(all_rows, title_col):
    """检测文件内重复标题，返回 [(title, [row_numbers])]"""
    title_groups = defaultdict(list)
    for idx, row_vals in enumerate(all_rows):
        if not any(row_vals):
            continue
        val = (row_vals[title_col] or "").strip() if title_col < len(row_vals) else ""
        if val:
            title_groups[val].append(idx + 2)  # +2 因为 Excel 行号（表头占1）
    return [(t, r) for t, r in title_groups.items() if len(r) > 1]


def _dedup_rows_add_sequence(all_rows, title_col):
    """添加序号策略：重复标题加 _1 _2 后缀，全部保留"""
    counter = defaultdict(int)
    result = []
    for row_vals in all_rows:
        title = (row_vals[title_col] or "").strip() if title_col < len(row_vals) else ""
        if title:
            counter[title] += 1
            if counter[title] > 1:
                new_title = f"{title}_{counter[title] - 1}"
                row_vals[title_col] = new_title
        result.append(row_vals)
    return result


@router.post("/import")
async def import_requirements(
    project_id: str,
    file: UploadFile = File(...),
    mapping: str = Form(...),  # JSON: {"Excel列名": ColumnMapping}
    mode: str = Form("append"),  # append | overwrite | update
    force: bool = Form(False),  # True = 跳过重复检测
    dup_strategy: str = Form("cancel"),  # cancel | add_sequence
    db: Session = Depends(get_db),
):
    """根据列映射导入 Excel 数据到需求
    mode: append=直接新增, overwrite=清空后重新导入, update=标题匹配更新/新增
    """
    import json
    mapping_dict: Dict[str, ColumnMapping] = {}
    try:
        raw = json.loads(mapping)
        for k, v in raw.items():
            mapping_dict[k] = ColumnMapping(**v)
    except Exception as e:
        raise HTTPException(400, f"映射格式错误: {e}")

    if not mapping_dict:
        raise HTTPException(400, "未配置任何列映射")

    proj = resolve_project(db, project_id)
    content = await file.read()
    if not content:
        raise HTTPException(400, "上传的文件为空")

    filename = file.filename or ""
    try:
        excel_headers, all_rows = _parse_excel(content, filename)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"无法解析 Excel 文件: {e}")

    # ── 重复检测与冲突处理 ──
    if not force:
        title_col = _find_title_col(excel_headers, mapping_dict)
        dup_result = None  # {message, dialog_type, actions, file_duplicates}

        if title_col is not None:
            file_dups = _detect_file_duplicates(all_rows, title_col)

            if mode == 'overwrite' and file_dups:
                # overwrite: 文件内重复 → 二选一
                dup_result = {
                    "file_duplicates": [{"title": t, "rows": r} for t, r in file_dups],
                    "dialog_type": "choice",
                    "actions": ["cancel", "add_sequence"],
                    "message": f"文件内发现 {len(file_dups)} 组重复标题",
                }

            elif mode == 'update' and file_dups:
                # update: 检查重复标题是否在 DB 中有对应
                dup_titles = [t for t, _ in file_dups]
                db_existing = set(
                    r[0] for r in db.query(Requirement.title).filter(
                        Requirement.project_id == proj.id,
                        Requirement.title.in_(dup_titles),
                    ).all()
                )
                db_conflict_dups = [(t, r) for t, r in file_dups if t in db_existing]
                no_conflict_dups = [(t, r) for t, r in file_dups if t not in db_existing]

                if db_conflict_dups:
                    # 有冲突的重复 → 不可处理
                    if no_conflict_dups:
                        dup_result = {
                            "file_duplicates": [{"title": t, "rows": r} for t, r in file_dups],
                            "dialog_type": "abandon_only",
                            "actions": ["cancel"],
                            "message": (
                                f"以下重复标题已存在于数据库，无法匹配更新："
                                + "、".join(t for t, _ in db_conflict_dups)
                                + "。请取消导入并调整文件。"
                            ),
                        }
                    else:
                        dup_result = {
                            "file_duplicates": [{"title": t, "rows": r} for t, r in file_dups],
                            "dialog_type": "abandon_only",
                            "actions": ["cancel"],
                            "message": "重复标题已存在于数据库，无法匹配更新，请取消导入并调整文件。",
                        }
                elif no_conflict_dups:
                    # 纯重复，DB 中无对应 → 二选一
                    dup_result = {
                        "file_duplicates": [{"title": t, "rows": r} for t, r in no_conflict_dups],
                        "dialog_type": "choice",
                        "actions": ["cancel", "add_sequence"],
                        "message": f"文件内发现 {len(no_conflict_dups)} 组重复标题（数据库中无对应）",
                    }

            elif mode == 'append' and file_dups:
                # append: 检测冲突+非冲突
                dup_titles = [t for t, _ in file_dups]
                db_existing = set(
                    r[0] for r in db.query(Requirement.title).filter(
                        Requirement.project_id == proj.id,
                        Requirement.title.in_(dup_titles),
                    ).all()
                )
                db_conflict_dups = [(t, r) for t, r in file_dups if t in db_existing]
                no_conflict_dups = [(t, r) for t, r in file_dups if t not in db_existing]

                if db_conflict_dups and not no_conflict_dups:
                    # 全冲突 → 提示信息
                    dup_result = {
                        "file_duplicates": [{"title": t, "rows": r} for t, r in db_conflict_dups],
                        "dialog_type": "info_only",
                        "actions": ["ok"],
                        "message": f"重复标题「{'、'.join(t for t, _ in db_conflict_dups)}」已存在于数据库，已跳过，无需额外处理。",
                    }
                elif no_conflict_dups:
                    parts = []
                    if db_conflict_dups:
                        parts.append(f"「{'、'.join(t for t, _ in db_conflict_dups)}」→ 已存在于DB，已跳过")
                    # 纯重复部分需要用户选择
                    dup_result = {
                        "file_duplicates": [{"title": t, "rows": r} for t, r in no_conflict_dups],
                        "dialog_type": "choice",
                        "actions": ["cancel", "add_sequence"],
                        "message": "文件内发现重复标题" + ("，" + "；".join(parts) if parts else ""),
                    }

        if dup_result:
            dup_result["warning"] = True
            return dup_result

    # ── 按策略去重 ──
    if dup_strategy == "add_sequence":
        title_col = _find_title_col(excel_headers, mapping_dict)
        if title_col is not None:
            all_rows = _dedup_rows_add_sequence(all_rows, title_col)

    # ── 覆盖模式：先清空所有已有数据，再重新创建 ──
    if mode == 'overwrite':
        db.query(RequirementCustomValue).filter(
            RequirementCustomValue.requirement_id.in_(
                db.query(Requirement.id).filter(Requirement.project_id == proj.id)
            )
        ).delete(synchronize_session=False)
        db.query(Requirement).filter(Requirement.project_id == proj.id).delete(synchronize_session=False)
        db.query(RequirementCustomField).filter(
            RequirementCustomField.project_id == proj.id
        ).delete(synchronize_session=False)
        db.query(RequirementStatusPool).filter(
            RequirementStatusPool.project_id == proj.id
        ).delete(synchronize_session=False)
        db.query(RequirementPriorityPool).filter(
            RequirementPriorityPool.project_id == proj.id
        ).delete(synchronize_session=False)
        db.flush()

    # 解析映射并创建新字段
    field_id_cache: Dict[str, Optional[int]] = {}

    def resolve_field_target(excel_col: str) -> Optional[int]:
        if excel_col not in mapping_dict:
            return None
        m = mapping_dict[excel_col]
        if m.target.startswith("field:"):
            try:
                return int(m.target.split(":")[1])
            except (ValueError, IndexError):
                return None
        if m.target != "new":
            return None
        cf = RequirementCustomField(
            project_id=proj.id,
            field_name=m.field_name or excel_col,
            field_type=m.field_type or "text",
            field_options=m.field_options or "",
            sort_order=999,
        )
        db.add(cf)
        db.flush()
        return cf.id

    for h in excel_headers:
        if h in mapping_dict:
            field_id_cache[h] = resolve_field_target(h)
        else:
            field_id_cache[h] = None

    # 枚举值规范化：中文/英文混合输入都能识别
    status_name_to_value = {"待处理": "todo", "进行中": "in_progress", "已完成": "done", "已取消": "cancelled"}
    status_value_set = {"todo", "in_progress", "done", "cancelled"}
    priority_name_to_value = {"低": "low", "普通": "normal", "高": "high", "紧急": "urgent"}
    priority_value_set = {"low", "normal", "high", "urgent"}

    def _normalize_status(v: str) -> str:
        v = (v or "").strip()
        if not v:
            return "todo"
        if v in status_value_set:
            return v
        if v in status_name_to_value:
            return status_name_to_value[v]
        # 检查是否在状态池中（含刚同步添加的）
        in_pool = db.query(RequirementStatusPool).filter(
            RequirementStatusPool.project_id == proj.id,
            RequirementStatusPool.name == v,
            RequirementStatusPool.is_active == True,
        ).first()
        if in_pool:
            return v
        return "todo"

    def _normalize_priority(v: str) -> str:
        v = (v or "").strip()
        if not v:
            return "normal"
        if v in priority_value_set:
            return v
        if v in priority_name_to_value:
            return priority_name_to_value[v]
        # 检查是否在优先级池中（含刚同步添加的）
        in_pool = db.query(RequirementPriorityPool).filter(
            RequirementPriorityPool.project_id == proj.id,
            RequirementPriorityPool.name == v,
            RequirementPriorityPool.is_active == True,
        ).first()
        if in_pool:
            return v
        return "normal"

    # ── 同步池数据：将导入值自动添加到状态池/优先级池/下拉选项 ──
    def _sync_import_pools():

        # 查找 Excel 中哪一列映射到了 status
        status_col = None
        priority_col = None
        drop_field_ids = set()
        for h, m in mapping_dict.items():
            if m.target == 'status':
                status_col = h
            elif m.target == 'priority':
                priority_col = h
            elif m.target.startswith('field:'):
                try:
                    fid = int(m.target.split(':')[1])
                except (ValueError, IndexError):
                    continue
                if fid in drop_field_ids:
                    continue
                cf = db.query(RequirementCustomField).filter(
                    RequirementCustomField.id == fid,
                    RequirementCustomField.project_id == proj.id,
                ).first()
                if cf and cf.field_type in ('dropdown', 'multi_dropdown'):
                    drop_field_ids.add(fid)
        # 此外，field_id_cache 中新建（new）的字段也可能是 dropdown
        for h, fid in field_id_cache.items():
            if fid is None:
                continue
            if fid in drop_field_ids:
                continue
            if h not in mapping_dict:
                continue
            if mapping_dict[h].target != 'new':
                continue
            cf = db.query(RequirementCustomField).filter(
                RequirementCustomField.id == fid,
                RequirementCustomField.project_id == proj.id,
            ).first()
            if cf and cf.field_type in ('dropdown', 'multi_dropdown'):
                drop_field_ids.add(fid)

        # 收集唯一值
        status_vals = set()
        priority_vals = set()
        drop_vals = {}  # field_id -> set of values
        for row_vals in all_rows:
            for i, h in enumerate(excel_headers):
                val = row_vals[i].strip() if i < len(row_vals) else ''
                if not val:
                    continue
                if h == status_col:
                    status_vals.add(val)
                elif h == priority_col:
                    priority_vals.add(val)
                elif h in mapping_dict:
                    mt = mapping_dict[h].target
                    fid = None
                    if mt.startswith('field:'):
                        try:
                            fid = int(mt.split(':')[1])
                        except (ValueError, IndexError):
                            continue
                    elif mt == 'new':
                        # 新建字段：从 field_id_cache 取 id
                        fid = field_id_cache.get(h)
                    if fid is not None and fid in drop_field_ids:
                        if fid not in drop_vals:
                            drop_vals[fid] = set()
                        for part in val.split(','):
                            p = part.strip()
                            if p:
                                drop_vals[fid].add(p)

        # 同步状态池
        existing_statuses = {
            r.name for r in db.query(RequirementStatusPool).filter(
                RequirementStatusPool.project_id == proj.id
            ).all()
        }
        for v in sorted(status_vals):
            if v not in existing_statuses and v not in status_value_set:
                sp = RequirementStatusPool(
                    project_id=proj.id, name=v, color='#5F5E5A', sort_order=999
                )
                db.add(sp)

        # 同步优先级池
        existing_priorities = {
            r.name for r in db.query(RequirementPriorityPool).filter(
                RequirementPriorityPool.project_id == proj.id
            ).all()
        }
        for v in sorted(priority_vals):
            if v not in existing_priorities and v not in priority_value_set:
                pp = RequirementPriorityPool(
                    project_id=proj.id, name=v, color='#5F5E5A', sort_order=999
                )
                db.add(pp)

        # 同步下拉/多选自定义字段的选项
        for fid, val_set in drop_vals.items():
            cf = db.query(RequirementCustomField).filter(
                RequirementCustomField.id == fid,
                RequirementCustomField.project_id == proj.id,
            ).first()
            if not cf:
                continue
            try:
                opts = json.loads(cf.field_options) if cf.field_options else []
            except (json.JSONDecodeError, TypeError):
                opts = []
            existing_labels = {o.get('label', '') for o in opts}
            added = []
            for v in sorted(val_set):
                if v not in existing_labels:
                    opts.append({'label': v, 'color': '#5F5E5A'})
                    added.append(v)
            if added:
                cf.field_options = json.dumps(opts, ensure_ascii=False)
                db.add(cf)

    _sync_import_pools()
    db.flush()

    # ── 根据模式处理已有数据 ──
    updated = 0
    existing_titles = set()  # append 模式用于检测 DB 冲突
    if mode == 'update':
        # 更新模式：预加载所有已有需求的标题→id映射
        existing = {
            r.title: r for r in db.query(Requirement).filter(
                Requirement.project_id == proj.id
            ).all()
        }
    elif mode == 'append':
        # 追加模式：只加载标题用于冲突检测
        existing_titles = set(
            r[0] for r in db.query(Requirement.title).filter(
                Requirement.project_id == proj.id
            ).all()
        )

    created = 0
    skipped_empty_title = 0
    skipped_db_collision = 0
    for row_vals in all_rows:
        if not any(row_vals):
            continue

        data = {}
        custom_vals = {}

        for i, h in enumerate(excel_headers):
            val = row_vals[i] if i < len(row_vals) else ""
            if h not in mapping_dict:
                continue
            m = mapping_dict[h]

            if m.target in ("title", "status", "priority"):
                data[m.target] = val
            elif field_id_cache[h] is not None:
                custom_vals[str(field_id_cache[h])] = val

        # 标题必填：空标题整行跳过
        raw_title = (data.get("title") or "").strip()
        if not raw_title:
            skipped_empty_title += 1
            continue

        # 追加模式：冲突标题跳过
        if mode == 'append' and raw_title in existing_titles:
            skipped_db_collision += 1
            continue

        if mode == 'update' and raw_title in existing:
            # 更新已有需求
            req = existing[raw_title]
            if data.get('priority'):
                req.priority = _normalize_priority(data.get('priority'))
            if data.get('status'):
                req.status = _normalize_status(data.get('status'))
            db.add(req)
            db.flush()

            # 更新自定义字段值
            for fid_str, val in custom_vals.items():
                if not val:
                    continue
                existing_cv = db.query(RequirementCustomValue).filter(
                    RequirementCustomValue.requirement_id == req.id,
                    RequirementCustomValue.field_id == int(fid_str),
                ).first()
                if existing_cv:
                    existing_cv.value = val
                    db.add(existing_cv)
                else:
                    db.add(RequirementCustomValue(
                        requirement_id=req.id,
                        field_id=int(fid_str),
                        value=val,
                    ))
            updated += 1
        else:
            # 新增需求
            req = Requirement(
                project_id=proj.id,
                display_id=generate_requirement_display_id(db, proj),
                title=raw_title,
                priority=_normalize_priority(data.get('priority')),
                status=_normalize_status(data.get('status')),
            )
            db.add(req)
            db.flush()

            for fid_str, val in custom_vals.items():
                if val:
                    cv = RequirementCustomValue(
                        requirement_id=req.id,
                        field_id=int(fid_str),
                        value=val,
                    )
                    db.add(cv)
            created += 1

    db.commit()
    touch_project(db, proj.id)
    msg_parts = []
    if created:
        msg_parts.append(f"新增 {created} 条")
    if updated:
        msg_parts.append(f"更新 {updated} 条")
    msg = "成功导入，" + "，".join(msg_parts) if msg_parts else "无数据变更"
    if skipped_empty_title:
        msg += f"，跳过 {skipped_empty_title} 条无标题空行"
    if skipped_db_collision:
        msg += f"，跳过 {skipped_db_collision} 条（数据库中已存在）"
    return {"created": created, "updated": updated, "skipped_empty": skipped_empty_title, "skipped_db_collision": skipped_db_collision, "message": msg}
