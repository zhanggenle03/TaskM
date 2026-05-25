from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from ..database import get_db, Task, Contact, Communication, CommunicationContact, Attachment, ProjectContact, StatusPool
from ..schemas import (
    TaskCreate, TaskUpdate, TaskOut, TaskDetail,
    ContactCreate, ContactUpdate, ContactOut,
    CommunicationCreate, CommunicationUpdate, CommunicationOut
)

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])


@router.get("", response_model=List[TaskOut])
def list_tasks(project_id: int, status_id: Optional[int] = None, db: Session = Depends(get_db)):
    tasks = db.query(Task).options(
        joinedload(Task.contacts)
    ).filter(Task.project_id == project_id).order_by(Task.updated_at.desc()).all()

    # 从沟通记录中推导每个任务的最终状态
    if tasks:
        task_ids = [t.id for t in tasks]
        # 用子查询获取每个任务最新的有状态变更的沟通记录
        latest = db.query(
            Communication.task_id,
            Communication.new_status_id
        ).filter(
            Communication.task_id.in_(task_ids),
            Communication.new_status_id.isnot(None)
        ).order_by(Communication.id.desc()).all()
        # 取每个 task_id 第一条（id 最大的）
        seen = set()
        status_map = {}
        for tid, nsid in latest:
            if tid not in seen:
                seen.add(tid)
                status_map[tid] = nsid
        for t in tasks:
            if t.id in status_map:
                t.status_id = status_map[t.id]

    # 筛选（在推导后的状态上筛选）
    if status_id is not None:
        tasks = [t for t in tasks if t.status_id == status_id]

    return tasks


@router.post("", response_model=TaskOut)
def create_task(project_id: int, data: TaskCreate, db: Session = Depends(get_db)):
    task = Task(project_id=project_id, **data.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskDetail)
def get_task(project_id: int, task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).options(
        joinedload(Task.contacts),
        joinedload(Task.communications)
            .joinedload(Communication.attachments),
        joinedload(Task.communications)
            .joinedload(Communication.communication_contacts)
            .joinedload(CommunicationContact.contact)
    ).filter(Task.id == task_id, Task.project_id == project_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    return task


@router.put("/{task_id}", response_model=TaskOut)
def update_task(project_id: int, task_id: int, data: TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id, Task.project_id == project_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    old_status_id = task.status_id
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(task, k, v)
    # 如果状态变更，自动生成沟通记录
    if task.status_id != old_status_id and task.status_id is not None:
        from datetime import datetime
        old_label = ''
        if old_status_id:
            from ..database import StatusPool
            old_pool = db.query(StatusPool).filter(StatusPool.id == old_status_id).first()
            old_label = old_pool.name if old_pool else ''
        new_pool = db.query(StatusPool).filter(StatusPool.id == task.status_id).first()
        new_label = new_pool.name if new_pool else ''
        comm = Communication(
            task_id=task_id,
            content=f"状态变更：{old_label or '未设置'} → {new_label}",
            comm_at=datetime.utcnow(),
            old_status_id=old_status_id,
            new_status_id=task.status_id
        )
        db.add(comm)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}")
def delete_task(project_id: int, task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id, Task.project_id == project_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    db.delete(task)
    db.commit()
    return {"ok": True}


# ---- 对接人 ----
@router.post("/{task_id}/contacts", response_model=ContactOut)
def add_contact(project_id: int, task_id: int, data: ContactCreate, db: Session = Depends(get_db)):
    # 自动添加到项目对接人库（如果不存在）
    existing_pc = db.query(ProjectContact).filter(
        ProjectContact.project_id == project_id,
        ProjectContact.name == data.name
    ).first()
    
    if not existing_pc:
        # 添加到项目对接人库
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
    
    # 创建任务对接人
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
    return c


@router.delete("/{task_id}/contacts/{contact_id}")
def remove_contact(project_id: int, task_id: int, contact_id: int, db: Session = Depends(get_db)):
    c = db.query(Contact).filter(Contact.id == contact_id, Contact.task_id == task_id).first()
    if not c:
        raise HTTPException(404, "对接人不存在")
    db.delete(c)
    db.commit()
    return {"ok": True}


# ---- 沟通记录 ----
@router.post("/{task_id}/communications", response_model=CommunicationOut)
def add_communication(project_id: int, task_id: int, data: CommunicationCreate, db: Session = Depends(get_db)):
    from datetime import datetime
    comm_data = data.model_dump()
    if comm_data.get("comm_at") is None:
        comm_data["comm_at"] = datetime.utcnow()
    # 移除 contact_ids（Communication 模型无此字段）
    contact_ids = comm_data.pop("contact_ids", [])
    comm = Communication(task_id=task_id, **comm_data)
    db.add(comm)
    # 如果选择了新状态，同步更新任务状态（确保数据库层面一致）
    new_status = comm_data.get("new_status_id")
    if new_status is not None:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task and task.status_id != new_status:
            task.status_id = new_status
    db.commit()
    # 写入关联表
    for cid in contact_ids:
        cc = CommunicationContact(communication_id=comm.id, contact_id=cid)
        db.add(cc)
    db.commit()
    db.refresh(comm)
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
        # 删除旧关联
        db.query(CommunicationContact).filter(
            CommunicationContact.communication_id == comm.id
        ).delete()
        # 插入新关联
        for cid in contact_ids:
            cc = CommunicationContact(communication_id=comm.id, contact_id=cid)
            db.add(cc)
    db.commit()
    db.refresh(comm)
    return comm


@router.delete("/{task_id}/communications/{comm_id}")
def delete_communication(project_id: int, task_id: int, comm_id: int, db: Session = Depends(get_db)):
    comm = db.query(Communication).filter(Communication.id == comm_id, Communication.task_id == task_id).first()
    if not comm:
        raise HTTPException(404, "沟通记录不存在")
    db.delete(comm)
    db.commit()
    return {"ok": True}
