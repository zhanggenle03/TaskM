from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import or_, func as sa_func
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime, date as date_type
import json, os, uuid, re
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
    SearchHits, SearchCommHit,
)

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])


# ---------- 工具函数 ----------

def _escape_like(s: str) -> str:
    """转义 LIKE 通配符，配合 escape='\\\\' 使用，避免用户输入 % _ 被当作通配符"""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _strip_html(html: str) -> str:
    """将富文本（HTML）剥离为纯文本，用于搜索命中片段展示"""
    text = re.sub(r"<br\s*/?>", "\n", html or "")
    text = re.sub(r"</(?:p|div|li|h[1-6]|tr)>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    for ent, ch in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"')):
        text = text.replace(ent, ch)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _make_snippet(text: str, keyword: str, radius: int = 45) -> str:
    """从纯文本中截取包含关键词的上下文片段，用于命中摘要"""
    idx = text.lower().find(keyword.lower())
    if idx < 0:
        return text[: radius * 2]
    start = max(0, idx - radius)
    end = min(len(text), idx + len(keyword) + radius)
    return ("…" if start > 0 else "") + text[start:end] + ("…" if end < len(text) else "")

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
    search: Optional[str] = None,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
):
    proj = resolve_project(db, project_id)
    # 如果传了 tag_ids，先筛选出符合条件的 task_id 列表
    if tag_ids:
        tag_id_list = [int(x) for x in tag_ids.split(",") if x.strip()]
        if tag_id_list:
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
        reverse = (sort_order == "desc")
    else:  # 默认按最后沟通时间，无沟通任务的按创建时间
        sort_key = lambda t: comm_at_map.get(t.id) or t.created_at or datetime.min
        reverse = (sort_order == "desc")

    tasks.sort(key=sort_key, reverse=reverse)

    if status_id is not None:
        tasks = [t for t in tasks if t.status_id == status_id]

    # ========== 综合搜索（可选）：任务字段 / 标签 / 对接人 / 任务内部沟通记录 ==========
    search_hits_map = {}
    if search and search.strip():
        kw = search.strip()
        like_kw = f"%{_escape_like(kw)}%"

        # 1) 命中任务本身字段（标题/描述/编号）
        field_task_ids = [r[0] for r in db.query(Task.id).filter(
            Task.id.in_(task_ids),
            or_(
                Task.title.like(like_kw, escape="\\"),
                Task.description.like(like_kw, escape="\\"),
                Task.display_id.like(like_kw, escape="\\"),
            ),
        ).all()]
        # 2) 命中标签名
        tag_task_ids = [r[0] for r in db.query(TaskTag.task_id).join(
            TagPool, TagPool.id == TaskTag.tag_id
        ).filter(
            TaskTag.task_id.in_(task_ids),
            TagPool.name.like(like_kw, escape="\\"),
        ).all()]
        # 3) 命中对接人姓名
        contact_task_ids = [r[0] for r in db.query(Contact.task_id).filter(
            Contact.task_id.in_(task_ids),
            Contact.name.like(like_kw, escape="\\"),
        ).all()]
        # 4) 命中任务内部沟通记录（正文或主题）
        hit_comms = db.query(Communication).filter(
            Communication.task_id.in_(task_ids),
            or_(
                Communication.content.like(like_kw, escape="\\"),
                Communication.subject.like(like_kw, escape="\\"),
            ),
        ).options(
            joinedload(Communication.communication_contacts)
                .joinedload(CommunicationContact.contact)
        ).order_by(Communication.comm_at.desc(), Communication.id.desc()).all()
        comm_task_ids = {c.task_id for c in hit_comms}

        matched_ids = set(field_task_ids) | set(tag_task_ids) | set(contact_task_ids) | comm_task_ids
        tasks = [t for t in tasks if t.id in matched_ids]

        # 按任务分组命中的沟通记录（每条截取关键词上下文片段，最多返回 5 条）
        comm_hits_by_task = {}
        for c in hit_comms:
            names = [cc.contact.name for cc in c.communication_contacts if cc.contact]
            comm_hits_by_task.setdefault(c.task_id, []).append(
                SearchCommHit(
                    id=c.id,
                    comm_at=c.comm_at,
                    subject=c.subject or "",
                    comm_type=c.comm_type or "",
                    snippet=_make_snippet(_strip_html(c.content), kw),
                    contacts=names,
                )
            )

        tag_task_ids_set = set(tag_task_ids)
        contact_task_ids_set = set(contact_task_ids)
        for t in tasks:
            fields = []
            if kw.lower() in (t.title or "").lower():
                fields.append("title")
            if kw.lower() in (t.description or "").lower():
                fields.append("description")
            if kw.lower() in (t.display_id or "").lower():
                fields.append("display_id")
            if t.id in tag_task_ids_set:
                fields.append("tag")
            if t.id in contact_task_ids_set:
                fields.append("contact")
            search_hits_map[t.id] = SearchHits(
                task_fields=fields,
                comms=comm_hits_by_task.get(t.id, [])[:5],
            )

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
            "search_hits": search_hits_map.get(t.id),
        })
    return result


# ponytail: 每项目独立 JSON 文件
KANBAN_CONFIG_FILE = "kanban.json"


def _kanban_config_path(proj):
    d = os.path.join(CONFIG_DIR, proj.display_id)
    return os.path.join(d, KANBAN_CONFIG_FILE)


SORT_CONFIG_FILE = "sort.json"


def _sort_config_path(proj):
    d = os.path.join(CONFIG_DIR, proj.display_id)
    return os.path.join(d, SORT_CONFIG_FILE)


@router.get("/sort-config")
def get_sort_config(project_id: str, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    p = _sort_config_path(proj)
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


@router.put("/sort-config")
def put_sort_config(project_id: str, body: dict, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    p = _sort_config_path(proj)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)
    return {"ok": True}


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
    # 读取现有配置，合并新数据，保留其他 key（如 dashboard_chart_field）
    existing = {}
    if os.path.isfile(p):
        try:
            with open(p, encoding="utf-8") as f:
                existing = json.load(f)
        except:
            pass
    existing.update(body)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
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

    # ponytail: 批量取每条任务的最新沟通记录（按人为设置的 comm_at,id 降序取每组第一条）
    _rn = sa_func.row_number().over(
        partition_by=Communication.task_id,
        order_by=(Communication.comm_at.desc(), Communication.id.desc())
    ).label("rn")
    _ranked = db.query(
        Communication.task_id, Communication.id, _rn
    ).filter(Communication.task_id.in_(task_ids)).subquery()
    latest_comm_ids = [r[0] for r in db.query(_ranked.c.id).filter(_ranked.c.rn == 1).all()]

    latest_comms = db.query(Communication).filter(
        Communication.id.in_(latest_comm_ids)
    ).options(
        joinedload(Communication.communication_contacts)
            .joinedload(CommunicationContact.contact)
    ).all()

    comm_contact_map = {}
    latest_status_map = {}  # task_id -> {old_status_id, new_status_id}
    for c in latest_comms:
        latest_status_map[c.task_id] = {
            "old_status_id": c.old_status_id,
            "new_status_id": c.new_status_id,
        }
        if c.communication_contacts:
            names = [cc.contact.name for cc in c.communication_contacts if cc.contact]
            comm_contact_map[c.task_id] = "、".join(names) if names else "无"
        else:
            comm_contact_map[c.task_id] = "无"

    # ponytail: 批量查每条任务最后一次"状态变更"的时间（最新一条有 new_status_id 的记录），
    # 用于看板显示"当前状态持续时长"
    _rn2 = sa_func.row_number().over(
        partition_by=Communication.task_id,
        order_by=(Communication.comm_at.desc(), Communication.id.desc())
    ).label("rn2")
    _ranked2 = db.query(
        Communication.task_id, Communication.new_status_id, Communication.comm_at, _rn2
    ).filter(
        Communication.task_id.in_(task_ids),
        Communication.new_status_id.isnot(None)
    ).subquery()
    status_change_comms = db.query(
        _ranked2.c.task_id, _ranked2.c.new_status_id, _ranked2.c.comm_at
    ).filter(_ranked2.c.rn2 == 1).all()

    status_change_map = {}  # task_id -> {new_status_id, comm_at}
    for sc in status_change_comms:
        status_change_map[sc.task_id] = {"new_status_id": sc.new_status_id, "comm_at": sc.comm_at}

    # ponytail: 构建状态名称映射
    all_status_pools = db.query(StatusPool).filter(
        StatusPool.project_id == proj.id,
    ).all()
    status_name_map = {sp.id: sp.name for sp in all_status_pools}

    now = datetime.now()
    status_groups = {}
    for t in tasks:
        # 状态口径与 derive_task_status 一致：最新沟通记录（按人为设置的 comm_at）有 new 用 new，否则沿用 old
        latest = latest_status_map.get(t.id)
        if latest is not None:
            if latest["new_status_id"] is not None:
                t.status_id = latest["new_status_id"]
            elif latest["old_status_id"] is not None:
                t.status_id = latest["old_status_id"]
        # 状态持续时长：仍以最后一次真正"状态变更"的 comm_at 为准
        sc_info = status_change_map.get(t.id)
        if sc_info:
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
            status_name=status_name_map.get(t.status_id or 0, "未知"),
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

    # 注：新建任务不再生成"创建任务"初始沟通记录。
    # 任务状态由 Task.status_id 字段（已写入默认状态）独立承载，
    # 状态推导链路在无沟通记录时会回退到该字段，无需靠状态记录起链。

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
    found = resolve_task(db, proj.id, task_id)  # 兼容数字 ID / 显示 ID
    task = db.query(Task).options(
        joinedload(Task.contacts),
        joinedload(Task.tags),
        joinedload(Task.linked_requirements),
        joinedload(Task.communications)
            .joinedload(Communication.attachments),
        joinedload(Task.communications)
            .joinedload(Communication.communication_contacts)
            .joinedload(CommunicationContact.contact)
    ).filter(Task.id == found.id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    derived = derive_task_status(db, task.id)
    if derived is not None:
        task.status_id = derived
    return task


@router.put("/{task_id}", response_model=TaskOut)
def update_task(project_id: str, task_id: str, data: TaskUpdate, db: Session = Depends(get_db)):
    proj = resolve_project(db, project_id)
    task = resolve_task(db, proj.id, task_id)  # 兼容数字 ID / 显示 ID

    current_status = derive_task_status(db, task.id)
    if current_status is None:
        # 无状态变更记录时，以字段当前状态作为 old 端，保证首次改状态语义正确
        current_status = task.status_id

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

        # 状态变更记录必须落在时间线末尾：comm_at 取「时间线最新 comm_at」与 now 的较大者，
        # 避免存在未来时间沟通时，新状态被判定逻辑忽略（A2 修复）。
        latest_comm = db.query(Communication.comm_at).filter(
            Communication.task_id == task.id
        ).order_by(Communication.comm_at.desc(), Communication.id.desc()).first()
        latest_comm_at = latest_comm[0] if latest_comm else None
        comm_at = latest_comm_at if (latest_comm_at and latest_comm_at > datetime.now()) else datetime.now()

        comm = Communication(
            task_id=task.id,
            content=f"状态变更：{old_label or '未设置'} → {new_label}",
            comm_at=comm_at,
            comm_type=_get_comm_type_name(db, proj.id),
            old_status_id=current_status,
            new_status_id=status_id
        )
        db.add(comm)
        # 状态写回交给 sync_task_status（整链重建）统一处理，不直接改字段，避免破坏链起点锚定

    if tag_ids is not None:
        db.query(TaskTag).filter(TaskTag.task_id == task.id).delete()
        for tid in tag_ids:
            db.add(TaskTag(task_id=task.id, tag_id=tid))

    db.commit()
    # 状态写回统一走整链重建（reconcile），替代"直接改字段 + derive 回写"
    sync_task_status(db, task.id)
    db.refresh(task)
    touch_project(db, proj.id)
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
    db.commit()

    for cid in contact_ids:
        cc = CommunicationContact(communication_id=comm.id, contact_id=cid)
        db.add(cc)
    db.commit()

    # 状态统一走推导：最新沟通记录（按人为设置的 comm_at）有 new 用 new，否则沿用 old。
    # 不再无条件 task.status_id = new_status，避免 comm_at 设为过去时把状态错改成历史状态。
    sync_task_status(db, task.id)
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
    raw_data = data.model_dump(exclude_unset=True)   # 仅前端实际提交的字段
    comm_data = dict(raw_data)                        # 保留 None：显式传 null 表示清空 old/new
    contact_ids = comm_data.pop("contact_ids", None)
    # 用户本次显式提交了状态字段 → 该记录为"权威"，old/new 字段绝不被衔接修正覆盖
    if 'old_status_id' in raw_data or 'new_status_id' in raw_data:
        auth_ids = {comm.id}
    else:
        auth_ids = None

    # ========== 保存旧 content，用于后续孤儿文件清理 ==========
    old_content = comm.content or ''

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

    # 伪变更保护标记：用户编辑后若 new==old 则标记，后续 reconcile 永远不清其 new
    if comm.new_status_id is not None and comm.new_status_id == comm.old_status_id:
        comm.protected_fake = True
    else:
        comm.protected_fake = False

    # ========== 清理孤立的沟通内联图片 ==========
    new_content = comm.content or ''
    # 1) 新风格图片：/uploads/{proj}/{task}/comm_{comm_id}/images/{filename}
    images_dir = os.path.join(UPLOAD_DIR, proj.display_id, task.display_id, f'comm_{comm_id}', 'images')
    if os.path.isdir(images_dir):
        referenced_new = set()
        for m in re.finditer(
            rf'/uploads/{re.escape(proj.display_id)}/{re.escape(task.display_id)}/comm_{comm_id}/images/([^"\'\s)\]]+)',
            new_content,
        ):
            referenced_new.add(m.group(1))
        for fn in os.listdir(images_dir):
            fp = os.path.join(images_dir, fn)
            if os.path.isfile(fp) and fn not in referenced_new:
                os.remove(fp)
        if not os.listdir(images_dir):
            os.rmdir(images_dir)

    # 2) 旧风格附件图片：/api/attachments/{id}/preview —— content 中已移除的附件需清理
    old_att_ids = set(int(m) for m in re.findall(r'/api/attachments/(\d+)/preview', old_content))
    new_att_ids = set(int(m) for m in re.findall(r'/api/attachments/(\d+)/preview', new_content))
    for att_id in old_att_ids - new_att_ids:
        att = db.query(Attachment).filter(Attachment.id == att_id, Attachment.comm_id == comm.id).first()
        if att:
            if os.path.exists(att.file_path):
                os.remove(att.file_path)
            db.delete(att)

    db.commit()
    # 状态链整链重建：保证相邻变更记录 old→new 衔接，权威记录字段不被覆盖。
    sync_task_status(db, task.id, authoritative_ids=auth_ids)
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


# ---------- 沟通图片上传（不创建 Attachment 记录，仅嵌入正文） ----------
@router.post("/{task_id}/communications/{comm_id}/images")
def upload_comm_image(
    project_id: str, task_id: str, comm_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传沟通富文本内联图片，存储在 comm_{comm_id}/images/ 下，不写入 attachments 表"""
    proj = resolve_project(db, project_id)
    task = resolve_task(db, proj.id, task_id)
    comm = db.query(Communication).filter(Communication.id == comm_id, Communication.task_id == task.id).first()
    if not comm:
        raise HTTPException(404, "沟通记录不存在")

    img_dir = os.path.join(UPLOAD_DIR, proj.display_id, task.display_id, f'comm_{comm_id}', 'images')
    os.makedirs(img_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or '')[1] or '.png'
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(img_dir, filename)
    content = file.file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    url = f"/uploads/{proj.display_id}/{task.display_id}/comm_{comm_id}/images/{filename}"
    return {"url": url, "errno": 0}
