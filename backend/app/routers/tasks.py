from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime, date as date_type
import json, os
from ..database import (
    get_db, Project, Task, Contact, Communication, CommunicationContact,
    Attachment, ProjectContact, StatusPool, CommTypePool, TagPool, TaskTag,
    TaskRequirement, Requirement,
    touch_project, derive_task_status, sync_task_status, cleanup_comm_files,
    generate_task_display_id, resolve_project, resolve_task,
    UPLOAD_DIR, CONFIG_DIR,
)
from ..schemas import (
    TaskCreate, TaskUpdate, TaskOut, TaskDetail,
    ContactCreate, ContactUpdate, ContactOut,
    CommunicationCreate, CommunicationUpdate, CommunicationOut,
    TagBrief, RequirementBrief,
    KanbanData, KanbanColumn, KanbanTaskSimple,
)
from ..database import StatusPool, Communication

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])


# ---------- 工具函数 ----------

def _get_comm_type_name(db, project_pk: int):
    """获取自动生成沟通记录使用的沟通类型名。优先"备注"，否则项目默认，最后兜底"备注"。"""
    ct = db.query(CommTypePool).filter(
        CommTypePool.project_id == project_pk,
        CommTypePool.name == "备注"
    ).first()
    if ct:
        return ct.name
    ct = db.query(CommTypePool).filter(
        CommTypePool.project_id == project_pk,
        CommTypePool.is_default == True
    ).first()
    return ct.name if ct else "备注"


# ---------- 任务 CRUD ----------

@router.get("", response_model=List[TaskOut])
def list_tasks(
    project_id: str,
    status_id: Optional[int] = None,
    tag_ids: Optional[str] = None,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
):
    proj = resolve_project(db, project_id)
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
                Task.project_id == proj.id,
                Task.id.in_(sub)
            ).all()
        else:
            tasks = db.query(Task).options(
                joinedload(Task.contacts)
            ).filter(Task.project_id == proj.id).all()
    else:
        tasks = db.query(Task).options(
            joinedload(Task.contacts)
        ).filter(Task.project_id == proj.id).all()

    if not tasks:
        return tasks

    task_ids = [t.id for t in tasks]

    # 从沟通记录推导每个任务的最终状态
    for t in tasks:
        derived = derive_task_status(db, t.id)
        if derived is not None:
            t.status_id = derived

    # 批量查询每个任务的最新沟通记录（含对接人）
    from sqlalchemy import func as sa_func
    max_id_subq = db.query(
        Communication.task_id,
        sa_func.max(Communication.id).label("max_id")
    ).filter(
        Communication.task_id.in_(task_ids)
    ).group_by(Communication.task_id).subquery()
    latest_comms = db.query(Communication).join(
        max_id_subq,
        Communication.id == max_id_subq.c.max_id
    ).options(
        joinedload(Communication.communication_contacts)
            .joinedload(CommunicationContact.contact)
    ).all()
    comm_at_map = {}
    comm_contact_map = {}
    for c in latest_comms:
        comm_at_map[c.task_id] = c.comm_at
        if c.communication_contacts:
            names = [cc.contact.name for cc in c.communication_contacts if cc.contact]
            comm_contact_map[c.task_id] = "、".join(names) if names else None
        else:
            comm_contact_map[c.task_id] = None

    # 排序（Python 层面，因为状态是在内存中推导的）
    sort_key = None
    if sort_by == "title":
        sort_key = lambda t: t.title or ""
        reverse = (sort_order == "desc")
    elif sort_by == "status":
        pools = db.query(StatusPool).filter(StatusPool.project_id == proj.id).order_by(StatusPool.sort_order, StatusPool.id).all()
        pool_rank = {}
        for idx, p in enumerate(pools):
            pool_rank[p.id] = idx
        sort_key = lambda t: pool_rank.get(t.status_id, 9999)
        reverse = (sort_order == "desc")
    elif sort_by == "due_date":
        sort_key = lambda t: (0, t.due_date) if t.due_date else (1, date_type.max)
        reverse = False
    else:  # 默认按最后沟通时间，无沟通任务的按创建时间
        sort_key = lambda t: comm_at_map.get(t.id) or t.created_at or datetime.min
        reverse = (sort_order == "desc")

    tasks.sort(key=sort_key, reverse=reverse)

    if status_id is not None:
        tasks = [t for t in tasks if t.status_id == status_id]

    # 构建最终返回数据（含 last_comm_at 和 tags）
    result = []
    all_tag_rows = db.query(TaskTag).filter(TaskTag.task_id.in_(task_ids)).all()
    task_tags_map = {}
    for row in all_tag_rows:
        task_tags_map.setdefault(row.task_id, []).append(row.tag_id)
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
            "display_id": t.display_id,
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
            "last_comm_contact_name": comm_contact_map.get(t.id),
        })
    return result


# ponytail: 每项目独立 JSON 文件
KANBAN_CONFIG_FILE = "kanban.json"


def _kanban_config_path(proj):
    d = os.path.join(CONFIG_DIR, proj.display_id)
    return os.path.join(d, KANBAN_CONFIG_FILE)


@router.get("/kanban-config")
def get_kanban_config(project_id: str, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    p = _kanban_config_path(proj)
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


@router.put("/kanban-config")
def put_kanban_config(project_id: str, body: dict, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    p = _kanban_config_path(proj)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)
    return {"ok": True}


@router.get("/kanban", response_model=KanbanData)
def get_kanban_tasks(project_id: str, db: Session = Depends(get_db)):
    """获取任务看板数据：按状态分组，含停留时长"""
    proj = resolve_project(db, project_id)
    tasks = db.query(Task).options(
        joinedload(Task.contacts)
    ).filter(Task.project_id == proj.id).all()

    if not tasks:
        return KanbanData(columns=[])

    task_ids = [t.id for t in tasks]

    # ponytail: 批量查每条任务的状态变更时间（最新一条有 new_status_id 的记录）
    from sqlalchemy import func as sa_func
    max_subq = db.query(
        Communication.task_id,
        sa_func.max(Communication.id).label("max_id")
    ).filter(
        Communication.task_id.in_(task_ids),
        Communication.new_status_id.isnot(None)
    ).group_by(Communication.task_id).subquery()

    status_change_comms = db.query(
        Communication.task_id,
        Communication.new_status_id,
        Communication.comm_at
    ).join(max_subq, Communication.id == max_subq.c.max_id).all()

    status_change_map = {}  # task_id -> {new_status_id, comm_at}
    for sc in status_change_comms:
        status_change_map[sc.task_id] = {"new_status_id": sc.new_status_id, "comm_at": sc.comm_at}

    # ponytail: 批量查每条任务的最新沟通记录（含对接人）
    max_comm_subq = db.query(
        Communication.task_id,
        sa_func.max(Communication.id).label("max_id")
    ).filter(
        Communication.task_id.in_(task_ids)
    ).group_by(Communication.task_id).subquery()

    latest_comms = db.query(Communication).join(
        max_comm_subq,
        Communication.id == max_comm_subq.c.max_id
    ).options(
        joinedload(Communication.communication_contacts)
            .joinedload(CommunicationContact.contact)
    ).all()
    comm_contact_map = {}
    for c in latest_comms:
        if c.communication_contacts:
            names = [cc.contact.name for cc in c.communication_contacts if cc.contact]
            comm_contact_map[c.task_id] = "、".join(names) if names else "无"
        else:
            comm_contact_map[c.task_id] = "无"

    now = datetime.now()
    status_groups = {}
    for t in tasks:
        sc_info = status_change_map.get(t.id)
        if sc_info:
            t.status_id = sc_info["new_status_id"]
            hours = (now - sc_info["comm_at"]).total_seconds() / 3600
            days = int(hours // 24)
            hrs = int(hours % 24)
            if days >= 30:
                dur_text = f"{days // 30}个月"
            elif days > 0:
                dur_text = f"{days}天{hrs}小时" if hrs else f"{days}天"
            else:
                dur_text = f"{int(hours)}小时" if hours >= 1 else "<1小时"
        else:
            hours = 0
            dur_text = ""

        contact_names = comm_contact_map.get(t.id, "无")

        card = KanbanTaskSimple(
            id=t.id,
            display_id=t.display_id,
            title=t.title,
            priority=t.priority,
            due_date=t.due_date,
            contact_names=contact_names,
            status_duration_hours=hours,
            status_duration_text=dur_text,
        )
        sid = t.status_id or 0
        status_groups.setdefault(sid, []).append((t, card))

    # 获取项目所有的状态池
    pools = db.query(StatusPool).filter(
        StatusPool.project_id == proj.id,
        StatusPool.is_active == True,
    ).order_by(StatusPool.sort_order, StatusPool.id).all()

    columns = []
    for sp in pools:
        cards = [c for _, c in status_groups.get(sp.id, [])]
        columns.append(KanbanColumn(
            status_id=sp.id,
            status_name=sp.name,
            color=sp.color,
            tasks=cards,
        ))

    # 如果有任务状态指向已停用/不存在的池，归入"其他"
    known_ids = {sp.id for sp in pools}
    orphan_cards = []
    for sid, items in status_groups.items():
        if sid not in known_ids and sid != 0:
            orphan_cards.extend(c for _, c in items)
    if orphan_cards:
        columns.append(KanbanColumn(
            status_id=0, status_name="其他", color="#909399", tasks=orphan_cards,
        ))

    return KanbanData(columns=columns)


@router.post("", response_model=TaskOut)
def create_task(project_id: str, data: TaskCreate, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    task_data = data.model_dump()
    tag_ids = task_data.pop("tag_ids", [])
    task = Task(project_id=proj.id, **task_data)
    db.add(task)
    db.flush()

    # 设置默认状态：取项目状态池中标记为默认的
    default_status = db.query(StatusPool).filter(
        StatusPool.project_id == proj.id,
        StatusPool.is_default == True
    ).first()
    if default_status and task.status_id is None:
        task.status_id = default_status.id

    # 创建初始状态沟通记录，使状态链完整
    if task.status_id:
        status_pool = db.query(StatusPool).filter(StatusPool.id == task.status_id).first()
        status_name = status_pool.name if status_pool else ''
        comm = Communication(
            task_id=task.id,
            content=f"创建任务，初始状态：{status_name}",
            comm_at=datetime.now(),
            comm_type=_get_comm_type_name(db, proj.id),
            old_status_id=None,
            new_status_id=task.status_id
        )
        db.add(comm)

    # 生成任务显示ID
    task.display_id = generate_task_display_id(db, proj)

    # 创建标签关联
    for tid in tag_ids:
        db.add(TaskTag(task_id=task.id, tag_id=tid))

    db.commit()
    db.refresh(task)
    touch_project(db, proj.id)
    return task


@router.get("/{task_id}", response_model=TaskDetail)
def get_task(project_id: str, task_id: str, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    task = db.query(Task).options(
        joinedload(Task.contacts),
        joinedload(Task.tags),
        joinedload(Task.linked_requirements),
        joinedload(Task.communications)
            .joinedload(Communication.attachments),
        joinedload(Task.communications)
            .joinedload(Communication.communication_contacts)
            .joinedload(CommunicationContact.contact)
    ).filter(Task.display_id == task_id, Task.project_id == proj.id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    derived = derive_task_status(db, task.id)
    if derived is not None:
        task.status_id = derived
    return task


@router.put("/{task_id}", response_model=TaskOut)
def update_task(project_id: str, task_id: str, data: TaskUpdate, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    task = db.query(Task).filter(Task.display_id == task_id, Task.project_id == proj.id).first()
    if not task:
        raise HTTPException(404, "任务不存在")

    current_status = derive_task_status(db, task.id)

    update_data = data.model_dump(exclude_unset=True)
    tag_ids = update_data.pop("tag_ids", None)
    status_id = update_data.get("status_id")

    for k, v in update_data.items():
        if k != "status_id":
            setattr(task, k, v)

    if status_id is not None and status_id != current_status:
        old_label = ''
        if current_status:
            old_pool = db.query(StatusPool).filter(StatusPool.id == current_status).first()
            old_label = old_pool.name if old_pool else ''
        new_pool = db.query(StatusPool).filter(StatusPool.id == status_id).first()
        new_label = new_pool.name if new_pool else ''

        comm = Communication(
            task_id=task.id,
            content=f"状态变更：{old_label or '未设置'} → {new_label}",
            comm_at=datetime.now(),
            comm_type=_get_comm_type_name(db, proj.id),
            old_status_id=current_status,
            new_status_id=status_id
        )
        db.add(comm)
        task.status_id = status_id

    if tag_ids is not None:
        db.query(TaskTag).filter(TaskTag.task_id == task.id).delete()
        for tid in tag_ids:
            db.add(TaskTag(task_id=task.id, tag_id=tid))

    db.commit()
    touch_project(db, proj.id)
    db.refresh(task)

    derived = derive_task_status(db, task.id)
    if derived is not None:
        task.status_id = derived
    return task


@router.delete("/{task_id}")
def delete_task(project_id: str, task_id: str, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    task = resolve_task(db, proj.id, task_id)
    comm_rows = db.query(Communication.id).filter(Communication.task_id == task.id).all()
    task_display_id = task.display_id
    db.delete(task)
    db.commit()
    for (cid,) in comm_rows:
        cleanup_comm_files(proj.display_id, task_display_id, cid)
    touch_project(db, proj.id)
    return {"ok": True}


# ---------- 对接人 ----------

@router.post("/{task_id}/contacts", response_model=ContactOut)
def add_contact(project_id: str, task_id: str, data: ContactCreate, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    task = resolve_task(db, proj.id, task_id)
    existing_pc = db.query(ProjectContact).filter(
        ProjectContact.project_id == proj.id,
        ProjectContact.name == data.name
    ).first()

    if not existing_pc:
        project_contact = ProjectContact(
            project_id=proj.id,
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
        task_id=task.id,
        project_contact_id=project_contact_id,
        name=data.name,
        role=data.role,
        contact_info=data.contact_info
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    touch_project(db, proj.id)
    return contact


@router.put("/{task_id}/contacts/{contact_id}", response_model=ContactOut)
def update_contact(project_id: str, task_id: str, contact_id: int, data: ContactUpdate, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    task = resolve_task(db, proj.id, task_id)
    c = db.query(Contact).filter(Contact.id == contact_id, Contact.task_id == task.id).first()
    if not c:
        raise HTTPException(404, "对接人不存在")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    touch_project(db, proj.id)
    return c


@router.delete("/{task_id}/contacts/{contact_id}")
def remove_contact(project_id: str, task_id: str, contact_id: int, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    task = resolve_task(db, proj.id, task_id)
    c = db.query(Contact).filter(Contact.id == contact_id, Contact.task_id == task.id).first()
    if not c:
        raise HTTPException(404, "对接人不存在")
    # 先清理 CommunicationContact 关联记录，避免悬挂引用导致沟通记录加载失败
    db.query(CommunicationContact).filter(CommunicationContact.contact_id == contact_id).delete(
        synchronize_session=False
    )
    db.delete(c)
    db.commit()
    touch_project(db, proj.id)
    return {"ok": True}


# ---------- 关联需求 ----------

@router.post("/{task_id}/requirements")
def link_requirement(project_id: str, task_id: str, data: dict, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    task = resolve_task(db, proj.id, task_id)
    req_id = data.get("requirement_id")
    if not req_id:
        raise HTTPException(400, "缺少 requirement_id")
    # 验证需求属于同一项目
    req = db.query(Requirement).filter(Requirement.id == req_id, Requirement.project_id == proj.id).first()
    if not req:
        raise HTTPException(404, "需求不存在")
    # 检查是否已关联
    existing = db.query(TaskRequirement).filter(
        TaskRequirement.task_id == task.id,
        TaskRequirement.requirement_id == req_id
    ).first()
    if existing:
        raise HTTPException(400, "该需求已关联到本任务")
    db.add(TaskRequirement(task_id=task.id, requirement_id=req_id))
    db.commit()
    touch_project(db, proj.id)
    return {"ok": True, "requirement": {"id": req.id, "display_id": req.display_id, "title": req.title, "priority": req.priority, "status": req.status}}

@router.delete("/{task_id}/requirements/{requirement_id}")
def unlink_requirement(project_id: str, task_id: str, requirement_id: int, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    task = resolve_task(db, proj.id, task_id)
    tr = db.query(TaskRequirement).filter(
        TaskRequirement.task_id == task.id,
        TaskRequirement.requirement_id == requirement_id
    ).first()
    if not tr:
        raise HTTPException(404, "关联关系不存在")
    db.delete(tr)
    db.commit()
    touch_project(db, proj.id)
    return {"ok": True}


# ---------- 沟通记录 ----------

@router.post("/{task_id}/communications", response_model=CommunicationOut)
def add_communication(project_id: str, task_id: str, data: CommunicationCreate, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    task = resolve_task(db, proj.id, task_id)
    comm_data = data.model_dump()
    if comm_data.get("comm_at") is None:
        comm_data["comm_at"] = datetime.now()

    contact_ids = comm_data.pop("contact_ids", [])
    comm = Communication(task_id=task.id, **comm_data)
    db.add(comm)

    new_status = comm_data.get("new_status_id")
    if new_status is not None:
        if task:
            task.status_id = new_status

    db.commit()

    for cid in contact_ids:
        cc = CommunicationContact(communication_id=comm.id, contact_id=cid)
        db.add(cc)
    db.commit()
    db.refresh(comm)
    touch_project(db, proj.id)
    return comm


@router.put("/{task_id}/communications/{comm_id}", response_model=CommunicationOut)
def update_communication(project_id: str, task_id: str, comm_id: int, data: CommunicationUpdate, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    task = resolve_task(db, proj.id, task_id)
    comm = db.query(Communication).filter(Communication.id == comm_id, Communication.task_id == task.id).first()
    if not comm:
        raise HTTPException(404, "沟通记录不存在")
    # ========== 检测状态字段变化（含 null） ==========
    raw_data = data.model_dump()
    comm_data = {k: v for k, v in raw_data.items() if v is not None}
    contact_ids = comm_data.pop("contact_ids", None)

    old_status_changed = "old_status_id" in raw_data and raw_data["old_status_id"] != comm.old_status_id
    new_status_changed = "new_status_id" in raw_data and raw_data["new_status_id"] != comm.new_status_id
    new_old_value = raw_data.get("old_status_id") if old_status_changed else None
    new_new_value = raw_data.get("new_status_id") if new_status_changed else None
    # 记录当前 comm 的原始类型（在 setattr 之前判断）
    was_no_change = comm.new_status_id is None or comm.new_status_id == comm.old_status_id

    # ========== 先获取时间线（按 (comm_at, id) 排序），定位当前索引 ==========
    all_comms = db.query(Communication).filter(
        Communication.task_id == task.id
    ).order_by(Communication.comm_at, Communication.id).all()
    idx = next((i for i, c in enumerate(all_comms) if c.id == comm.id), None)

    # ========== 应用编辑到 comm 对象 ==========
    for k, v in comm_data.items():
        if k in ('contact_ids',):
            continue
        setattr(comm, k, v)

    if contact_ids is not None:
        db.query(CommunicationContact).filter(
            CommunicationContact.communication_id == comm.id
        ).delete()
        for cid in contact_ids:
            cc = CommunicationContact(communication_id=comm.id, contact_id=cid)
            db.add(cc)

    # ========== 重新按时间排序（comm_at 可能已变），重新定位索引 ==========
    all_comms.sort(key=lambda c: (c.comm_at, c.id))
    idx = next((i for i, c in enumerate(all_comms) if c.id == comm.id), None)

    # ========== 辅助函数 ==========
    def _is_change(r):
        """有状态变更：new IS NOT NULL 且 old != new"""
        return r.new_status_id is not None and r.new_status_id != r.old_status_id

    def _forward(comms, start, val):
        """往前传播（到更早的记录）：
        无变更 → 改 old，继续
        有变更 → 改 new，停止"""
        for j in range(start, -1, -1):
            c = comms[j]
            if _is_change(c):
                c.new_status_id = val
                break
            c.old_status_id = val

    def _backward(comms, start, val):
        """往后传播（到更晚的记录）：
        统一改 old，无变更继续，有变更停止"""
        for j in range(start, len(comms)):
            c = comms[j]
            if _is_change(c):
                c.old_status_id = val
                break
            c.old_status_id = val

    # ========== 状态链一致性同步 ==========
    # old 变了 → 往前传播
    if old_status_changed and new_old_value is not None and idx is not None:
        _forward(all_comms, idx - 1, new_old_value)

    # new 变了 → 往后传播
    if new_status_changed and new_new_value is not None and idx is not None:
        _backward(all_comms, idx + 1, new_new_value)

    # 无状态变更记录只改了 old：effective_new = old 也变了，后面也要同步
    if was_no_change and old_status_changed and not new_status_changed and new_old_value is not None and idx is not None:
        _backward(all_comms, idx + 1, new_old_value)

    db.commit()
    sync_task_status(db, task.id)
    db.refresh(comm)
    touch_project(db, proj.id)
    return comm


@router.delete("/{task_id}/communications/{comm_id}")
def delete_communication(project_id: str, task_id: str, comm_id: int, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    task = resolve_task(db, proj.id, task_id)
    comm = db.query(Communication).filter(Communication.id == comm_id, Communication.task_id == task.id).first()
    if not comm:
        raise HTTPException(404, "沟通记录不存在")

    db.delete(comm)
    db.commit()

    cleanup_comm_files(proj.display_id, task.display_id, comm_id)
    sync_task_status(db, task.id)
    touch_project(db, proj.id)
    return {"ok": True}
