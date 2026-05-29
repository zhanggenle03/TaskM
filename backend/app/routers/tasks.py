from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime, date as date_type
from ..database import (
    get_db, Project, Task, Contact, Communication, CommunicationContact,
    Attachment, ProjectContact, StatusPool, CommTypePool, TagPool, TaskTag,
    touch_project, derive_task_status, sync_task_status, cleanup_comm_files
)
from ..schemas import (
    TaskCreate, TaskUpdate, TaskOut, TaskDetail,
    ContactCreate, ContactUpdate, ContactOut,
    CommunicationCreate, CommunicationUpdate, CommunicationOut,
    TagBrief,
)

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])


# ---------- 工具函数 ----------

def _get_comm_type_name(db, project_id):
    """获取自动生成沟通记录使用的沟通类型名。优先"备注"，否则项目默认，最后兜底"备注"。"""
    ct = db.query(CommTypePool).filter(
        CommTypePool.project_id == project_id,
        CommTypePool.name == "备注"
    ).first()
    if ct:
        return ct.name
    ct = db.query(CommTypePool).filter(
        CommTypePool.project_id == project_id,
        CommTypePool.is_default == True
    ).first()
    return ct.name if ct else "备注"


# ---------- 任务 CRUD ----------

@router.get("", response_model=List[TaskOut])
def list_tasks(
    project_id: int,
    status_id: Optional[int] = None,
    tag_ids: Optional[str] = None,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
):
    # 如果传了 tag_ids，先筛选出符合条件的 task_id 列表
    if tag_ids:
        tag_id_list = [int(x) for x in tag_ids.split(",") if x.strip()]
        if tag_id_list:
            from sqlalchemy import func as sa_func
            sub = db.query(TaskTag.task_id).filter(
                TaskTag.tag_id.in_(tag_id_list)
            ).group_by(TaskTag.task_id).having(
                sa_func.count(TaskTag.tag_id.distinct()) == len(tag_id_list)
            ).subquery()
            tasks = db.query(Task).options(
                joinedload(Task.contacts)
            ).filter(
                Task.project_id == project_id,
                Task.id.in_(sub)
            ).all()
        else:
            tasks = db.query(Task).options(
                joinedload(Task.contacts)
            ).filter(Task.project_id == project_id).all()
    else:
        tasks = db.query(Task).options(
            joinedload(Task.contacts)
        ).filter(Task.project_id == project_id).all()

    if not tasks:
        return tasks

    task_ids = [t.id for t in tasks]

    # 从沟通记录推导每个任务的最终状态
    for t in tasks:
        derived = derive_task_status(db, t.id)
        if derived is not None:
            t.status_id = derived

    # 批量查询每个任务的最后一条沟通时间
    from sqlalchemy import func as sa_func
    last_comm_rows = db.query(
        Communication.task_id,
        sa_func.max(Communication.comm_at).label("max_comm_at")
    ).filter(
        Communication.task_id.in_(task_ids)
    ).group_by(Communication.task_id).all()
    comm_at_map = {row.task_id: row.max_comm_at for row in last_comm_rows}

    # 排序（Python 层面，因为状态是在内存中推导的）
    sort_key = None
    if sort_by == "title":
        sort_key = lambda t: t.title or ""
        reverse = (sort_order == "desc")
    elif sort_by == "status":
        # 加载项目状态池 sort_order 映射（按 sort_order, id 排序以保证相同 sort_order 内的顺序）
        pools = db.query(StatusPool).filter(StatusPool.project_id == project_id).order_by(StatusPool.sort_order, StatusPool.id).all()
        # 为每个状态池分配一个唯一的排序序号
        pool_rank = {}
        for idx, p in enumerate(pools):
            pool_rank[p.id] = idx
        sort_key = lambda t: pool_rank.get(t.status_id, 9999)
        reverse = (sort_order == "desc")
    elif sort_by == "due_date":
        # 按截止日期正序，没有截止日期的排最后
        sort_key = lambda t: (0, t.due_date) if t.due_date else (1, date_type.max)
        reverse = False
    else:  # 默认按最后沟通时间
        sort_key = lambda t: comm_at_map.get(t.id) or datetime.min
        reverse = (sort_order == "desc")

    tasks.sort(key=sort_key, reverse=reverse)

    if status_id is not None:
        tasks = [t for t in tasks if t.status_id == status_id]

    # 构建最终返回数据（含 last_comm_at 和 tags）
    result = []
    # 批量加载所有 task 的 tags（避免 N+1）
    all_tag_rows = db.query(TaskTag).filter(TaskTag.task_id.in_(task_ids)).all()
    task_tags_map = {}
    for row in all_tag_rows:
        task_tags_map.setdefault(row.task_id, []).append(row.tag_id)
    # 获取所有用到的标签信息
    all_tag_ids = set()
    for ids in task_tags_map.values():
        all_tag_ids.update(ids)
    tag_info_map = {}
    if all_tag_ids:
        tag_rows = db.query(TagPool).filter(TagPool.id.in_(all_tag_ids)).all()
        tag_info_map = {tr.id: {"id": tr.id, "name": tr.name, "color": tr.color} for tr in tag_rows}

    for t in tasks:
        tag_ids_for_task = task_tags_map.get(t.id, [])
        tags_for_task = [tag_info_map[tid] for tid in tag_ids_for_task if tid in tag_info_map]
        result.append({
            "id": t.id,
            "project_id": t.project_id,
            "title": t.title,
            "description": t.description,
            "priority": t.priority,
            "due_date": t.due_date,
            "status_id": t.status_id,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
            "contacts": t.contacts,
            "tags": tags_for_task,
            "last_comm_at": comm_at_map.get(t.id),
        })
    return result


@router.post("", response_model=TaskOut)
def create_task(project_id: int, data: TaskCreate, db: Session = Depends(get_db)):
    task_data = data.model_dump()
    tag_ids = task_data.pop("tag_ids", [])
    task = Task(project_id=project_id, **task_data)
    db.add(task)
    db.flush()  # 获取 task.id 但不提交

    # 设置默认状态：取项目状态池中标记为默认的
    default_status = db.query(StatusPool).filter(
        StatusPool.project_id == project_id,
        StatusPool.is_default == True
    ).first()
    if default_status and task.status_id is None:
        task.status_id = default_status.id

    # 创建标签关联
    for tid in tag_ids:
        db.add(TaskTag(task_id=task.id, tag_id=tid))

    db.commit()
    db.refresh(task)
    touch_project(db, project_id)
    return task


@router.get("/{task_id}", response_model=TaskDetail)
def get_task(project_id: int, task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).options(
        joinedload(Task.contacts),
        joinedload(Task.tags),
        joinedload(Task.communications)
            .joinedload(Communication.attachments),
        joinedload(Task.communications)
            .joinedload(Communication.communication_contacts)
            .joinedload(CommunicationContact.contact)
    ).filter(Task.id == task_id, Task.project_id == project_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    # 从沟通记录推导最终状态（与 list_tasks 一致）
    derived = derive_task_status(db, task.id)
    if derived is not None:
        task.status_id = derived
    return task


@router.put("/{task_id}", response_model=TaskOut)
def update_task(project_id: int, task_id: int, data: TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id, Task.project_id == project_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")

    # 从沟通记录推导真实当前状态（而非 task.status_id）
    current_status = derive_task_status(db, task_id)

    # 提取 tag_ids（Task 模型无此字段，需单独处理）
    update_data = data.model_dump(exclude_unset=True)
    tag_ids = update_data.pop("tag_ids", None)
    status_id = update_data.get("status_id")

    # 应用非状态字段的更新
    for k, v in update_data.items():
        if k != "status_id":
            setattr(task, k, v)

    # 如果前端传了 status_id 且与推导出的当前状态不同，自动生成沟通记录
    if status_id is not None and status_id != current_status:
        old_label = ''
        if current_status:
            old_pool = db.query(StatusPool).filter(StatusPool.id == current_status).first()
            old_label = old_pool.name if old_pool else ''
        new_pool = db.query(StatusPool).filter(StatusPool.id == status_id).first()
        new_label = new_pool.name if new_pool else ''

        comm = Communication(
            task_id=task_id,
            content=f"状态变更：{old_label or '未设置'} → {new_label}",
            comm_at=datetime.now(),
            comm_type=_get_comm_type_name(db, project_id),
            old_status_id=current_status,
            new_status_id=status_id
        )
        db.add(comm)

        # 将 task.status_id 写为新状态
        task.status_id = status_id

    # 同步标签关联
    if tag_ids is not None:
        # 删除旧的标签关联
        db.query(TaskTag).filter(TaskTag.task_id == task_id).delete()
        # 创建新的标签关联
        for tid in tag_ids:
            db.add(TaskTag(task_id=task_id, tag_id=tid))

    db.commit()

    # touch_project 必须在 db.commit() 之后、db.refresh() 之前
    touch_project(db, project_id)

    # refresh 后 task 对象拿到最新数据
    db.refresh(task)

    # 最终再从沟通记录推导一次，确保绝对一致
    derived = derive_task_status(db, task_id)
    if derived is not None:
        task.status_id = derived

    return task


@router.delete("/{task_id}")
def delete_task(project_id: int, task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id, Task.project_id == project_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    # 先清理所有关联沟通记录的附件文件
    comm_ids = db.query(Communication.id).filter(Communication.task_id == task_id).all()
    db.delete(task)
    db.commit()
    # DB 删除后，删磁盘文件
    for (cid,) in comm_ids:
        cleanup_comm_files(cid)
    touch_project(db, project_id)
    return {"ok": True}


# ---------- 对接人 ----------

@router.post("/{task_id}/contacts", response_model=ContactOut)
def add_contact(project_id: int, task_id: int, data: ContactCreate, db: Session = Depends(get_db)):
    existing_pc = db.query(ProjectContact).filter(
        ProjectContact.project_id == project_id,
        ProjectContact.name == data.name
    ).first()

    if not existing_pc:
        project_contact = ProjectContact(
            project_id=project_id,
            name=data.name,
            role=data.role,
            contact_info=data.contact_info
        )
        db.add(project_contact)
        db.commit()
        db.refresh(project_contact)
        project_contact_id = project_contact.id
    else:
        project_contact_id = existing_pc.id

    contact = Contact(
        task_id=task_id,
        project_contact_id=project_contact_id,
        name=data.name,
        role=data.role,
        contact_info=data.contact_info
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    touch_project(db, project_id)
    return contact


@router.put("/{task_id}/contacts/{contact_id}", response_model=ContactOut)
def update_contact(project_id: int, task_id: int, contact_id: int, data: ContactUpdate, db: Session = Depends(get_db)):
    c = db.query(Contact).filter(Contact.id == contact_id, Contact.task_id == task_id).first()
    if not c:
        raise HTTPException(404, "对接人不存在")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    touch_project(db, project_id)
    return c


@router.delete("/{task_id}/contacts/{contact_id}")
def remove_contact(project_id: int, task_id: int, contact_id: int, db: Session = Depends(get_db)):
    c = db.query(Contact).filter(Contact.id == contact_id, Contact.task_id == task_id).first()
    if not c:
        raise HTTPException(404, "对接人不存在")
    db.delete(c)
    db.commit()
    touch_project(db, project_id)
    return {"ok": True}


# ---------- 沟通记录 ----------

@router.post("/{task_id}/communications", response_model=CommunicationOut)
def add_communication(project_id: int, task_id: int, data: CommunicationCreate, db: Session = Depends(get_db)):
    comm_data = data.model_dump()
    if comm_data.get("comm_at") is None:
        comm_data["comm_at"] = datetime.now()

    # 移除 contact_ids（Communication 模型无此字段）
    contact_ids = comm_data.pop("contact_ids", [])
    comm = Communication(task_id=task_id, **comm_data)
    db.add(comm)

    # 如果有状态变更，同步更新 task.status_id
    new_status = comm_data.get("new_status_id")
    if new_status is not None:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status_id = new_status

    db.commit()

    # 写入关联表
    for cid in contact_ids:
        cc = CommunicationContact(communication_id=comm.id, contact_id=cid)
        db.add(cc)
    db.commit()
    db.refresh(comm)
    touch_project(db, project_id)
    return comm


@router.put("/{task_id}/communications/{comm_id}", response_model=CommunicationOut)
def update_communication(project_id: int, task_id: int, comm_id: int, data: CommunicationUpdate, db: Session = Depends(get_db)):
    comm = db.query(Communication).filter(Communication.id == comm_id, Communication.task_id == task_id).first()
    if not comm:
        raise HTTPException(404, "沟通记录不存在")
    comm_data = data.model_dump(exclude_none=True)

    # 处理 contact_ids
    contact_ids = comm_data.pop("contact_ids", None)
    for k, v in comm_data.items():
        if k in ('contact_ids',):
            continue
        setattr(comm, k, v)

    # 更新关联表
    if contact_ids is not None:
        db.query(CommunicationContact).filter(
            CommunicationContact.communication_id == comm.id
        ).delete()
        for cid in contact_ids:
            cc = CommunicationContact(communication_id=comm.id, contact_id=cid)
            db.add(cc)

    db.commit()

    # 编辑沟通记录后，重新推导 task.status_id（确保与最新沟通记录一致）
    sync_task_status(db, task_id)

    db.refresh(comm)
    touch_project(db, project_id)
    return comm


@router.delete("/{task_id}/communications/{comm_id}")
def delete_communication(project_id: int, task_id: int, comm_id: int, db: Session = Depends(get_db)):
    comm = db.query(Communication).filter(Communication.id == comm_id, Communication.task_id == task_id).first()
    if not comm:
        raise HTTPException(404, "沟通记录不存在")
    db.delete(comm)
    db.commit()

    # 删除磁盘上的附件文件
    cleanup_comm_files(comm_id)

    # 删除沟通记录后，重新推导 task.status_id
    sync_task_status(db, task_id)

    touch_project(db, project_id)
    return {"ok": True}
