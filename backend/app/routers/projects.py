from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from ..database import get_db, Project, StatusPool, CommTypePool, Checkin, CheckinProject, CheckinTask, Task, Communication, touch_project, cleanup_comm_files
from ..schemas import (
    ProjectCreate, ProjectUpdate, ProjectOut,
    StatusPoolCreate, StatusPoolUpdate, StatusPoolOut,
    CommTypePoolCreate, CommTypePoolUpdate, CommTypePoolOut,
    CheckinCreate, CheckinOut, BatchDeleteIds,
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


router = APIRouter(prefix="/projects", tags=["projects"])


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

    return query.order_by(order_fn).all()


@router.post("", response_model=ProjectOut)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    proj = Project(**data.model_dump())
    db.add(proj)
    db.flush()
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
    db.commit()
    db.refresh(proj)
    return proj


# ---- 签到（全局路由必须在 /{project_id} 之前） ----
@router.get("/checkins", response_model=List[CheckinOut])
def list_all_checkins(db: Session = Depends(get_db)):
    return db.query(Checkin).options(
        joinedload(Checkin.projects), joinedload(Checkin.tasks)
    ).order_by(Checkin.date.desc(), Checkin.created_at.desc()).all()


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
def get_project(project_id: int, db: Session = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(404, "项目不存在")
    return proj


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, data: ProjectUpdate, db: Session = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(404, "项目不存在")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(proj, k, v)
    db.commit()
    db.refresh(proj)
    return proj


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(404, "项目不存在")
    # 先查出所有关联沟通记录 ID（用于后续清理磁盘文件）
    comm_ids = db.query(Communication.id).join(Task).filter(Task.project_id == project_id).all()
    db.delete(proj)
    db.commit()
    # DB 删除后，删磁盘上的附件文件
    for (cid,) in comm_ids:
        cleanup_comm_files(cid)
    return {"ok": True}


# ---- 状态池 ----
@router.get("/{project_id}/statuses", response_model=List[StatusPoolOut])
def list_statuses(project_id: int, db: Session = Depends(get_db)):
    return db.query(StatusPool).filter(StatusPool.project_id == project_id).order_by(StatusPool.sort_order).all()


@router.post("/{project_id}/statuses", response_model=StatusPoolOut)
def create_status(project_id: int, data: StatusPoolCreate, db: Session = Depends(get_db)):
    status = StatusPool(project_id=project_id, **data.model_dump())
    db.add(status)
    db.flush()
    if data.is_default:
        _ensure_single_default(db, StatusPool, project_id, exclude_id=status.id)
    db.commit()
    db.refresh(status)
    touch_project(db, project_id)
    return status


@router.put("/{project_id}/statuses/{status_id}", response_model=StatusPoolOut)
def update_status(project_id: int, status_id: int, data: StatusPoolUpdate, db: Session = Depends(get_db)):
    status = db.query(StatusPool).filter(StatusPool.id == status_id, StatusPool.project_id == project_id).first()
    if not status:
        raise HTTPException(404, "状态不存在")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(status, k, v)
    db.flush()
    if data.is_default is True:
        _ensure_single_default(db, StatusPool, project_id, exclude_id=status.id)
    db.commit()
    db.refresh(status)
    touch_project(db, project_id)
    return status


@router.delete("/{project_id}/statuses/{status_id}")
def delete_status(project_id: int, status_id: int, db: Session = Depends(get_db)):
    status = db.query(StatusPool).filter(StatusPool.id == status_id, StatusPool.project_id == project_id).first()
    if not status:
        raise HTTPException(404, "状态不存在")
    db.delete(status)
    db.commit()
    touch_project(db, project_id)
    return {"ok": True}


# ---- 沟通类型池 ----
@router.get("/{project_id}/comm-types", response_model=List[CommTypePoolOut])
def list_comm_types(project_id: int, db: Session = Depends(get_db)):
    return db.query(CommTypePool).filter(CommTypePool.project_id == project_id).order_by(CommTypePool.sort_order).all()


@router.post("/{project_id}/comm-types", response_model=CommTypePoolOut)
def create_comm_type(project_id: int, data: CommTypePoolCreate, db: Session = Depends(get_db)):
    ct = CommTypePool(project_id=project_id, **data.model_dump())
    db.add(ct)
    db.flush()
    if data.is_default:
        _ensure_single_default(db, CommTypePool, project_id, exclude_id=ct.id)
    db.commit()
    db.refresh(ct)
    touch_project(db, project_id)
    return ct


@router.put("/{project_id}/comm-types/{type_id}", response_model=CommTypePoolOut)
def update_comm_type(project_id: int, type_id: int, data: CommTypePoolUpdate, db: Session = Depends(get_db)):
    ct = db.query(CommTypePool).filter(CommTypePool.id == type_id, CommTypePool.project_id == project_id).first()
    if not ct:
        raise HTTPException(404, "沟通类型不存在")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(ct, k, v)
    db.flush()
    if data.is_default is True:
        _ensure_single_default(db, CommTypePool, project_id, exclude_id=ct.id)
    db.commit()
    db.refresh(ct)
    touch_project(db, project_id)
    return ct


@router.delete("/{project_id}/comm-types/{type_id}")
def delete_comm_type(project_id: int, type_id: int, db: Session = Depends(get_db)):
    ct = db.query(CommTypePool).filter(CommTypePool.id == type_id, CommTypePool.project_id == project_id).first()
    if not ct:
        raise HTTPException(404, "沟通类型不存在")
    db.delete(ct)
    db.commit()
    touch_project(db, project_id)
    return {"ok": True}


@router.get("/{project_id}/checkins", response_model=List[CheckinOut])
def list_checkins(project_id: int, db: Session = Depends(get_db)):
    return db.query(Checkin).options(
        joinedload(Checkin.projects), joinedload(Checkin.tasks)
    ).filter(Checkin.projects.any(id=project_id)).order_by(Checkin.date.desc(), Checkin.created_at.desc()).all()


@router.post("/{project_id}/checkins", response_model=CheckinOut)
def create_checkin(project_id: int, data: CheckinCreate, db: Session = Depends(get_db)):
    from datetime import date as date_type
    chk_date = date_type.fromisoformat(data.date) if data.date else date_type.today()
    chk = Checkin(date=chk_date, content=data.content, multi_project=data.multi_project)
    proj = db.query(Project).filter(Project.id == project_id).first()
    if proj: chk.projects.append(proj)
    for tid in data.task_ids:
        task = db.query(Task).filter(Task.id == tid).first()
        if task: chk.tasks.append(task)
    db.add(chk)
    db.commit()
    db.refresh(chk)
    return chk


@router.delete("/{project_id}/checkins/{checkin_id}")
def delete_checkin(project_id: int, checkin_id: int, db: Session = Depends(get_db)):
    chk = db.query(Checkin).filter(Checkin.id == checkin_id).first()
    if not chk:
        raise HTTPException(404, "签到记录不存在")
    db.delete(chk)
    db.commit()
    return {"ok": True}
