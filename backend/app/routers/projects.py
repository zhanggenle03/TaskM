from fastapi import APIRouter, Depends, HTTPException
import os
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from ..database import get_db, Project, RequirementCustomField, RequirementStatusPool, RequirementPriorityPool, StatusPool, CommTypePool, TagPool, Checkin, CheckinProject, CheckinTask, Task, TaskTag, Communication, Contact, HolidayOverride, touch_project, cleanup_comm_files, generate_project_display_id, _random_prefix, resolve_project, UPLOAD_DIR, CONFIG_DIR
from ..schemas import (
    ProjectCreate, ProjectUpdate, ProjectOut,
    StatusPoolCreate, StatusPoolUpdate, StatusPoolOut,
    CommTypePoolCreate, CommTypePoolUpdate, CommTypePoolOut,
    TagPoolCreate, TagPoolUpdate, TagPoolOut,
    CheckinCreate, CheckinOut, BatchDeleteIds,
    HolidayOverrideSet, HolidayOverrideOut,
)


def _ensure_single_default(db: Session, model_class, project_id: int, exclude_id: int = None):
    """确保项目内该池类型只有一个默认项。将其他 is_default=True 的项取消。"""
    others = db.query(model_class).filter(
        model_class.project_id == project_id,
        model_class.is_default == True,
    )
    if exclude_id is not None:
        others = others.filter(model_class.id != exclude_id)
    for item in others.all():
        item.is_default = False


def _count_status_refs(db: Session, status_id: int) -> dict:
    """统计状态被引用的次数"""
    return {
        "任务": db.query(Task).filter(Task.status_id == status_id).count(),
        "沟通记录（旧状态）": db.query(Communication).filter(Communication.old_status_id == status_id).count(),
        "沟通记录（新状态）": db.query(Communication).filter(Communication.new_status_id == status_id).count(),
    }


def _clear_status_refs(db: Session, status_id: int, project_id: int):
    """清理状态引用（设为默认状态）"""
    # 查找项目默认状态
    default_status = db.query(StatusPool).filter(
        StatusPool.project_id == project_id,
        StatusPool.is_default == True,
        StatusPool.id != status_id,
    ).first()
    default_id = default_status.id if default_status else None
    db.query(Task).filter(Task.status_id == status_id).update({Task.status_id: default_id}, synchronize_session=False)
    db.query(Communication).filter(Communication.old_status_id == status_id).update({Communication.old_status_id: default_id}, synchronize_session=False)
    db.query(Communication).filter(Communication.new_status_id == status_id).update({Communication.new_status_id: default_id}, synchronize_session=False)


def _count_comm_type_refs(db: Session, type_name: str) -> dict:
    """统计沟通类型被引用的次数（comm_type 存的是名称字符串）"""
    count = db.query(Communication).filter(Communication.comm_type == type_name).count()
    return {"沟通记录": count} if count else {}


def _clear_tag_refs(db: Session, tag_id: int):
    """清理标签引用（删除关联表）"""
    db.query(TaskTag).filter(TaskTag.tag_id == tag_id).delete(synchronize_session=False)


def _count_tag_refs(db: Session, tag_id: int) -> dict:
    """统计标签被引用的次数"""
    count = db.query(TaskTag).filter(TaskTag.tag_id == tag_id).count()
    return {"任务": count} if count else {}


from datetime import date as date_type, datetime


router = APIRouter(prefix="/projects", tags=["projects"])
# ---- 节假日覆盖（数据库版） ----
@router.get("/holiday-overrides", response_model=List[HolidayOverrideOut])
def list_holiday_overrides(year: Optional[int] = None, db: Session = Depends(get_db)):
    from sqlalchemy import extract
    q = db.query(HolidayOverride)
    if year is not None:
        q = q.filter(extract('year', HolidayOverride.date) == year)
    return q.order_by(HolidayOverride.date).all()


@router.put("/holiday-overrides", response_model=HolidayOverrideOut)
def set_holiday_override(data: HolidayOverrideSet, db: Session = Depends(get_db)):
    chk_date = date_type.fromisoformat(data.date)
    existing = db.query(HolidayOverride).filter(HolidayOverride.date == chk_date).first()
    if data.override_type is None:
        if existing:
            db.delete(existing)
            db.commit()
        return {'date': chk_date, 'override_type': '', 'remark': '', 'created_at': datetime.utcnow(), 'updated_at': datetime.utcnow()}
    if existing:
        existing.override_type = data.override_type
        existing.remark = data.remark
    else:
        ho = HolidayOverride(date=chk_date, override_type=data.override_type, remark=data.remark)
        db.add(ho)
    db.commit()
    ho = db.query(HolidayOverride).filter(HolidayOverride.date == chk_date).first()
    return ho


@router.delete("/holiday-overrides")
def delete_holiday_overrides(dates: List[str], db: Session = Depends(get_db)):
    # 批量删除指定日期的覆盖
    date_objs = [date_type.fromisoformat(d) for d in dates]
    count = db.query(HolidayOverride).filter(HolidayOverride.date.in_(date_objs)).delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "deleted": count}

@router.get("", response_model=List[ProjectOut])
def list_projects(
    search: Optional[str] = None,
    sort_by: Optional[str] = "updated_at",
    sort_order: Optional[str] = "desc",
    db: Session = Depends(get_db),
):
    query = db.query(Project)

    # 搜索：匹配名称或描述
    if search:
        like = f"%{search}%"
        query = query.filter(Project.name.like(like) | Project.description.like(like))

    # 排序
    sort_map = {
        "name": Project.name,
        "start_date": Project.start_date,
        "created_at": Project.created_at,
        "updated_at": Project.updated_at,
    }
    col = sort_map.get(sort_by, Project.updated_at)
    order_fn = col.asc() if sort_order == "asc" else col.desc()

    return query.order_by(Project.pinned.desc(), order_fn).all()


@router.post("", response_model=ProjectOut)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    proj_data = data.model_dump()
    custom_prefix = proj_data.pop("custom_prefix", None)
    if not custom_prefix:
        custom_prefix = _random_prefix()
    else:
        custom_prefix = custom_prefix.upper()

    proj = Project(**proj_data)
    proj.custom_prefix = custom_prefix
    db.add(proj)
    db.flush()

    # 生成显示ID
    display_id, _ = generate_project_display_id(db, custom_prefix)
    proj.display_id = display_id

    # 创建默认状态池
    defaults = [
        StatusPool(project_id=proj.id, name="待处理", color="#185FA5", sort_order=0, is_default=True),
        StatusPool(project_id=proj.id, name="进行中", color="#0F6E56", sort_order=1),
        StatusPool(project_id=proj.id, name="已完成", color="#639922", sort_order=2),
    ]
    db.add_all(defaults)
    # 创建默认沟通类型池
    type_defaults = [
        CommTypePool(project_id=proj.id, name="备注", color="#0F6E56", sort_order=0, is_default=True),
        CommTypePool(project_id=proj.id, name="会议", color="#534AB7", sort_order=1),
        CommTypePool(project_id=proj.id, name="邮件", color="#854F0B", sort_order=2),
        CommTypePool(project_id=proj.id, name="电话", color="#993C1D", sort_order=3),
        CommTypePool(project_id=proj.id, name="线上", color="#185FA5", sort_order=4),
    ]
    db.add_all(type_defaults)
    # 创建默认需求状态池
    req_statuses = [
        RequirementStatusPool(project_id=proj.id, name="待处理", color="#185FA5", sort_order=0, is_default=True),
        RequirementStatusPool(project_id=proj.id, name="进行中", color="#0F6E56", sort_order=1),
        RequirementStatusPool(project_id=proj.id, name="已完成", color="#639922", sort_order=2),
        RequirementStatusPool(project_id=proj.id, name="已取消", color="#909399", sort_order=3),
    ]
    db.add_all(req_statuses)
    # 创建默认需求优先级池
    req_priorities = [
        RequirementPriorityPool(project_id=proj.id, name="低", color="#909399", sort_order=0),
        RequirementPriorityPool(project_id=proj.id, name="普通", color="#185FA5", sort_order=1, is_default=True),
        RequirementPriorityPool(project_id=proj.id, name="高", color="#854F0B", sort_order=2),
        RequirementPriorityPool(project_id=proj.id, name="紧急", color="#993C1D", sort_order=3),
    ]
    db.add_all(req_priorities)
    # 创建需求内置字段
    req_builtin_fields = [
        RequirementCustomField(project_id=proj.id, field_name="标题", field_type="text", field_options="", sort_order=0, is_active=True, is_builtin=True),
        RequirementCustomField(project_id=proj.id, field_name="状态", field_type="dropdown", field_options="待处理\n进行中\n已完成\n已取消", sort_order=1, is_active=True, is_builtin=True),
        RequirementCustomField(project_id=proj.id, field_name="优先级", field_type="dropdown", field_options="低\n普通\n高\n紧急", sort_order=2, is_active=True, is_builtin=True),
        RequirementCustomField(project_id=proj.id, field_name="创建时间", field_type="datetime", field_options="", sort_order=3, is_active=True, is_builtin=True),
        RequirementCustomField(project_id=proj.id, field_name="更新时间", field_type="datetime", field_options="", sort_order=4, is_active=True, is_builtin=True),
    ]
    db.add_all(req_builtin_fields)
    db.commit()
    db.refresh(proj)
    return proj


# ---- 签到（全局路由必须在 /{project_id} 之前） ----
@router.get("/checkins/today-update-status")
def today_checkin_status(date: Optional[str] = None, db: Session = Depends(get_db)):
    from datetime import date as date_type, datetime, timedelta
    local_date = date_type.fromisoformat(date) if date else date_type.today()

    # ---- ① 签到记录 ----
    checkins = db.query(Checkin).options(
        joinedload(Checkin.projects), joinedload(Checkin.tasks)
    ).filter(Checkin.date == local_date).all()

    project_ids = set()
    task_ids = set()
    for chk in checkins:
        for p in chk.projects:
            project_ids.add(p.id)
        for t in chk.tasks:
            task_ids.add(t.id)

    # ---- ② 沟通记录（comm_at 存的是 datetime.now() 本地时间，直接用本地时间查询） ----
    local_today_start = datetime(local_date.year, local_date.month, local_date.day)
    local_today_end = local_today_start + timedelta(days=1)

    comms = db.query(Communication).options(
        joinedload(Communication.task)
    ).filter(
        Communication.comm_at >= local_today_start,
        Communication.comm_at < local_today_end,
    ).all()

    for comm in comms:
        task_ids.add(comm.task_id)
        if comm.task:
            project_ids.add(comm.task.project_id)

    return {"project_ids": list(project_ids), "task_ids": list(task_ids)}


@router.get("/checkins", response_model=List[CheckinOut])
def list_all_checkins(year: Optional[int] = None, month: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Checkin).options(
        joinedload(Checkin.projects), joinedload(Checkin.tasks)
    )
    if year is not None:
        from sqlalchemy import extract
        q = q.filter(extract('year', Checkin.date) == year)
        if month is not None:
            q = q.filter(extract('month', Checkin.date) == month)
    return q.order_by(Checkin.date.desc(), Checkin.created_at.desc()).all()


@router.post("/checkins", response_model=CheckinOut)
def create_checkin_global(data: CheckinCreate, db: Session = Depends(get_db)):
    from datetime import date as date_type
    chk_date = date_type.fromisoformat(data.date) if data.date else date_type.today()
    chk = Checkin(
        date=chk_date,
        content=data.content,
        multi_project=data.multi_project,
    )
    # 关联项目
    for pid in data.project_ids:
        proj = db.query(Project).filter(Project.id == pid).first()
        if proj:
            chk.projects.append(proj)
    # 关联任务
    for tid in data.task_ids:
        task = db.query(Task).filter(Task.id == tid).first()
        if task:
            chk.tasks.append(task)
    db.add(chk)
    db.commit()
    db.refresh(chk)
    return chk


@router.post("/checkins/batch-delete")
def batch_delete_checkins(data: BatchDeleteIds, db: Session = Depends(get_db)):
    count = db.query(Checkin).filter(Checkin.id.in_(data.ids)).delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "deleted": count}


@router.put("/checkins/{checkin_id}", response_model=CheckinOut)
def update_checkin(checkin_id: int, data: CheckinCreate, db: Session = Depends(get_db)):
    chk = db.query(Checkin).options(joinedload(Checkin.projects), joinedload(Checkin.tasks)).filter(Checkin.id == checkin_id).first()
    if not chk:
        raise HTTPException(404, "签到记录不存在")
    from datetime import date as date_type
    chk.date = date_type.fromisoformat(data.date) if data.date else chk.date
    chk.content = data.content
    chk.multi_project = data.multi_project
    # 更新关联项目
    chk.projects = []
    for pid in data.project_ids:
        proj = db.query(Project).filter(Project.id == pid).first()
        if proj: chk.projects.append(proj)
    # 更新关联任务
    chk.tasks = []
    for tid in data.task_ids:
        task = db.query(Task).filter(Task.id == tid).first()
        if task: chk.tasks.append(task)
    db.commit()
    db.refresh(chk)
    return chk


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)):
    return resolve_project(db, project_id)


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, data: ProjectUpdate, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(proj, k, v)
    db.commit()
    db.refresh(proj)
    return proj


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    # 清理工作记录（checkin）的关联数据
    db.query(CheckinProject).filter(CheckinProject.project_id == proj.id).delete(synchronize_session=False)
    db.query(CheckinTask).filter(CheckinTask.task_id.in_(
        db.query(Task.id).filter(Task.project_id == proj.id)
    )).delete(synchronize_session=False)

    # 先查出所有关联沟通记录信息（用于后续清理磁盘文件）
    comm_rows = db.query(Communication.id, Task.display_id).join(
        Task, Communication.task_id == Task.id
    ).filter(Task.project_id == proj.id).all()
    db.delete(proj)
    db.commit()
    # DB 删除后，删磁盘上的附件文件
    for comm_id, task_display_id in comm_rows:
        cleanup_comm_files(proj.display_id, task_display_id, comm_id)
    # 删除项目级上传目录
    proj_upload_dir = os.path.join(UPLOAD_DIR, proj.display_id)
    if os.path.isdir(proj_upload_dir):
        import shutil
        shutil.rmtree(proj_upload_dir)
    # 删除项目级配置目录
    proj_config_dir = os.path.join(CONFIG_DIR, proj.display_id)
    if os.path.isdir(proj_config_dir):
        import shutil
        shutil.rmtree(proj_config_dir)
    return {"ok": True}


# ---- 状态池 ----
@router.get("/{project_id}/statuses", response_model=List[StatusPoolOut])
def list_statuses(project_id: str, show_inactive: bool = False, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    q = db.query(StatusPool).filter(StatusPool.project_id == proj.id)
    if not show_inactive:
        q = q.filter(StatusPool.is_active == True)
    return q.order_by(StatusPool.sort_order).all()


@router.post("/{project_id}/statuses", response_model=StatusPoolOut)
def create_status(project_id: str, data: StatusPoolCreate, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    # 检查同名非活动项，重新激活
    inactive = db.query(StatusPool).filter(
        StatusPool.project_id == proj.id,
        StatusPool.name == data.name,
        StatusPool.is_active == False
    ).first()
    if inactive:
        for k, v in data.model_dump().items():
            setattr(inactive, k, v)
        inactive.is_active = True
        db.flush()
        if data.is_default:
            _ensure_single_default(db, StatusPool, proj.id, exclude_id=inactive.id)
        db.commit()
        db.refresh(inactive)
        touch_project(db, proj.id)
        return inactive
    status = StatusPool(project_id=proj.id, **data.model_dump())
    db.add(status)
    db.flush()
    if data.is_default:
        _ensure_single_default(db, StatusPool, proj.id, exclude_id=status.id)
    db.commit()
    db.refresh(status)
    touch_project(db, proj.id)
    return status


@router.put("/{project_id}/statuses/{status_id}", response_model=StatusPoolOut)
def update_status(project_id: str, status_id: int, data: StatusPoolUpdate, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    status = db.query(StatusPool).filter(StatusPool.id == status_id, StatusPool.project_id == proj.id).first()
    if not status:
        raise HTTPException(404, "状态不存在")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(status, k, v)
    db.flush()
    if data.is_default is True:
        _ensure_single_default(db, StatusPool, proj.id, exclude_id=status.id)
    db.commit()
    db.refresh(status)
    touch_project(db, proj.id)
    return status


@router.delete("/{project_id}/statuses/{status_id}")
def delete_status(project_id: str, status_id: int, force: bool = False, confirmed: bool = False, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    status = db.query(StatusPool).filter(StatusPool.id == status_id, StatusPool.project_id == proj.id).first()
    if not status:
        raise HTTPException(404, "状态不存在")
    if status.is_default:
        raise HTTPException(400, "默认值不允许停用或删除，请先设置其他状态为默认值")
    if force:
        refs = _count_status_refs(db, status_id)
        real_refs = {k: v for k, v in refs.items() if v > 0}
        if real_refs and not confirmed:
            raise HTTPException(409, detail={"message": "有数据引用该状态", "refs": real_refs})
        _clear_status_refs(db, status_id, proj.id)
        db.delete(status)
        db.commit()
        touch_project(db, proj.id)
        return {"ok": True, "refs_cleaned": real_refs}
    status.is_active = False
    db.commit()
    touch_project(db, proj.id)
    return {"ok": True}


# ---- 沟通类型池 ----
@router.get("/{project_id}/comm-types", response_model=List[CommTypePoolOut])
def list_comm_types(project_id: str, show_inactive: bool = False, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    q = db.query(CommTypePool).filter(CommTypePool.project_id == proj.id)
    if not show_inactive:
        q = q.filter(CommTypePool.is_active == True)
    return q.order_by(CommTypePool.sort_order).all()


@router.post("/{project_id}/comm-types", response_model=CommTypePoolOut)
def create_comm_type(project_id: str, data: CommTypePoolCreate, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    # 检查同名非活动项，重新激活
    inactive = db.query(CommTypePool).filter(
        CommTypePool.project_id == proj.id,
        CommTypePool.name == data.name,
        CommTypePool.is_active == False
    ).first()
    if inactive:
        for k, v in data.model_dump().items():
            setattr(inactive, k, v)
        inactive.is_active = True
        db.flush()
        if data.is_default:
            _ensure_single_default(db, CommTypePool, proj.id, exclude_id=inactive.id)
        db.commit()
        db.refresh(inactive)
        touch_project(db, proj.id)
        return inactive
    ct = CommTypePool(project_id=proj.id, **data.model_dump())
    db.add(ct)
    db.flush()
    if data.is_default:
        _ensure_single_default(db, CommTypePool, proj.id, exclude_id=ct.id)
    db.commit()
    db.refresh(ct)
    touch_project(db, proj.id)
    return ct


@router.put("/{project_id}/comm-types/{type_id}", response_model=CommTypePoolOut)
def update_comm_type(project_id: str, type_id: int, data: CommTypePoolUpdate, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    ct = db.query(CommTypePool).filter(CommTypePool.id == type_id, CommTypePool.project_id == proj.id).first()
    if not ct:
        raise HTTPException(404, "沟通类型不存在")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(ct, k, v)
    db.flush()
    if data.is_default is True:
        _ensure_single_default(db, CommTypePool, proj.id, exclude_id=ct.id)
    db.commit()
    db.refresh(ct)
    touch_project(db, proj.id)
    return ct


@router.delete("/{project_id}/comm-types/{type_id}")
def delete_comm_type(project_id: str, type_id: int, force: bool = False, confirmed: bool = False, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    ct = db.query(CommTypePool).filter(CommTypePool.id == type_id, CommTypePool.project_id == proj.id).first()
    if not ct:
        raise HTTPException(404, "沟通类型不存在")
    if ct.is_default:
        raise HTTPException(400, "默认值不允许停用或删除，请先设置其他沟通类型为默认值")
    if force:
        refs = _count_comm_type_refs(db, ct.name)
        if refs and not confirmed:
            raise HTTPException(409, detail={"message": "有数据引用该沟通类型", "refs": refs})
        # 查找默认沟通类型，将引用改为默认值
        default_ct = db.query(CommTypePool).filter(
            CommTypePool.project_id == proj.id,
            CommTypePool.is_default == True,
            CommTypePool.id != type_id,
        ).first()
        default_name = default_ct.name if default_ct else "备注"
        db.query(Communication).filter(Communication.comm_type == ct.name).update(
            {Communication.comm_type: default_name}, synchronize_session=False
        )
        db.delete(ct)
        db.commit()
        touch_project(db, proj.id)
        return {"ok": True, "refs_cleaned": refs}
    ct.is_active = False
    db.commit()
    touch_project(db, proj.id)
    return {"ok": True}


# ---- 标签池 ----
@router.get("/{project_id}/tags", response_model=List[TagPoolOut])
def list_tags(project_id: str, show_inactive: bool = False, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    q = db.query(TagPool).filter(TagPool.project_id == proj.id)
    if not show_inactive:
        q = q.filter(TagPool.is_active == True)
    return q.order_by(TagPool.sort_order).all()


@router.post("/{project_id}/tags", response_model=TagPoolOut)
def create_tag(project_id: str, data: TagPoolCreate, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    # 检查同名非活动项，重新激活
    inactive = db.query(TagPool).filter(
        TagPool.project_id == proj.id,
        TagPool.name == data.name,
        TagPool.is_active == False
    ).first()
    if inactive:
        for k, v in data.model_dump().items():
            setattr(inactive, k, v)
        inactive.is_active = True
        db.commit()
        db.refresh(inactive)
        touch_project(db, proj.id)
        return inactive
    tag = TagPool(project_id=proj.id, **data.model_dump())
    db.add(tag)
    db.commit()
    db.refresh(tag)
    touch_project(db, proj.id)
    return tag


@router.put("/{project_id}/tags/{tag_id}", response_model=TagPoolOut)
def update_tag(project_id: str, tag_id: int, data: TagPoolUpdate, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    tag = db.query(TagPool).filter(TagPool.id == tag_id, TagPool.project_id == proj.id).first()
    if not tag:
        raise HTTPException(404, "标签不存在")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(tag, k, v)
    db.commit()
    db.refresh(tag)
    touch_project(db, proj.id)
    return tag


@router.delete("/{project_id}/tags/{tag_id}")
def delete_tag(project_id: str, tag_id: int, force: bool = False, confirmed: bool = False, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    tag = db.query(TagPool).filter(TagPool.id == tag_id, TagPool.project_id == proj.id).first()
    if not tag:
        raise HTTPException(404, "标签不存在")
    if force:
        refs = _count_tag_refs(db, tag_id)
        if refs and not confirmed:
            raise HTTPException(409, detail={"message": "有数据引用该标签", "refs": refs})
        _clear_tag_refs(db, tag_id)
        db.delete(tag)
        db.commit()
        touch_project(db, proj.id)
        return {"ok": True, "refs_cleaned": refs}
    tag.is_active = False
    db.commit()
    touch_project(db, proj.id)
    return {"ok": True}


@router.get("/{project_id}/checkins", response_model=List[CheckinOut])
def list_checkins(project_id: str, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    return db.query(Checkin).options(
        joinedload(Checkin.projects), joinedload(Checkin.tasks)
    ).filter(Checkin.projects.any(id=proj.id)).order_by(Checkin.date.desc(), Checkin.created_at.desc()).all()


@router.post("/{project_id}/checkins", response_model=CheckinOut)
def create_checkin(project_id: str, data: CheckinCreate, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    from datetime import date as date_type
    chk_date = date_type.fromisoformat(data.date) if data.date else date_type.today()
    chk = Checkin(date=chk_date, content=data.content, multi_project=data.multi_project)
    chk.projects.append(proj)
    for tid in data.task_ids:
        task = db.query(Task).filter(Task.id == tid).first()
        if task: chk.tasks.append(task)
    db.add(chk)
    db.commit()
    db.refresh(chk)
    return chk


@router.delete("/{project_id}/checkins/{checkin_id}")
def delete_checkin(project_id: str, checkin_id: int, db: Session = Depends(get_db)):
    chk = db.query(Checkin).filter(Checkin.id == checkin_id).first()
    if not chk:
        raise HTTPException(404, "签到记录不存在")
    db.delete(chk)
    db.commit()
    return {"ok": True}
