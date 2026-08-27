"""任务文件管理 API：文件夹树、文件列表、独立上传、移动、沟通引用

数据模型：
- FileFolder：无限层级文件夹（parent_id 自引用），归属任务
- Attachment：task_id 归属任务；comm_id 空=独立上传；folder_id 空=根层级
- CommunicationFile：沟通记录与文件管理文件的多对多引用（引用不随移动/重命名失效）
"""
import os
import uuid
from typing import Optional

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import (
    get_db, Attachment, FileFolder, CommunicationFile, Communication,
    UPLOAD_DIR, touch_project, resolve_project, resolve_task,
)
from ..schemas import (
    AttachmentOut, FileFolderCreate, FileFolderOut, FileFolderUpdate,
    TaskFilesOut, AttachmentMoveIn, CommunicationLinkIn,
)
from ..settings_manager import get_max_file_size

router = APIRouter(prefix="/projects/{project_id}/tasks/{task_id}/files", tags=["file_manager"])
comm_router = APIRouter(prefix="/projects/{project_id}/tasks/{task_id}/communications/{comm_id}", tags=["file_manager"])


def _resolve(db, project_id, task_id):
    """解析项目与任务，返回 (Project, Task)"""
    proj = resolve_project(db, project_id)
    task = resolve_task(db, proj.id, task_id)
    return proj, task


def _folder_tree(folders):
    """把扁平文件夹列表组装成树（按名称排序）"""
    by_parent = {}
    for f in folders:
        by_parent.setdefault(f.parent_id, []).append(f)
    for kids in by_parent.values():
        kids.sort(key=lambda x: x.name)

    def build(pid):
        nodes = []
        for f in by_parent.get(pid, []):
            nodes.append({
                "id": f.id,
                "task_id": f.task_id,
                "parent_id": f.parent_id,
                "name": f.name,
                "created_at": f.created_at,
                "children": build(f.id),
            })
        return nodes

    return build(None)


def _folder_path_fn(folders):
    """返回 folder_id -> '父/子' 路径函数（带缓存）"""
    fmap = {f.id: f for f in folders}
    cache = {}

    def path(fid):
        if fid is None:
            return ""
        if fid in cache:
            return cache[fid]
        parts = []
        cur = fmap.get(fid)
        seen = set()
        while cur and cur.id not in seen:
            seen.add(cur.id)
            parts.append(cur.name)
            cur = fmap.get(cur.parent_id)
        s = "/".join(reversed(parts))
        cache[fid] = s
        return s

    return path


# ── 文件树 + 文件列表 ──
@router.get("", response_model=TaskFilesOut)
def get_task_files(project_id: str, task_id: str, db: Session = Depends(get_db)):
    proj, task = _resolve(db, project_id, task_id)
    folders = db.query(FileFolder).filter(FileFolder.task_id == task.id).all()
    attachments = db.query(Attachment).filter(
        Attachment.task_id == task.id
    ).order_by(Attachment.uploaded_at.desc(), Attachment.id.desc()).all()

    # 被引用计数（沟通记录引用）
    link_counts = {}
    if attachments:
        rows = db.query(
            CommunicationFile.attachment_id, func.count(CommunicationFile.id)
        ).filter(
            CommunicationFile.attachment_id.in_([a.id for a in attachments])
        ).group_by(CommunicationFile.attachment_id).all()
        link_counts = {aid: cnt for aid, cnt in rows}

    path_fn = _folder_path_fn(folders)
    files = []
    for a in attachments:
        is_comm = a.comm_id is not None
        files.append({
            "id": a.id,
            "comm_id": a.comm_id,
            "task_id": a.task_id,
            "folder_id": a.folder_id,
            "filename": a.filename,
            "original_filename": a.original_filename,
            "file_size": a.file_size,
            "mime_type": a.mime_type,
            "uploaded_at": a.uploaded_at,
            "folder_path": path_fn(a.folder_id),
            "source": "comm" if is_comm else "manual",
            "source_comm_id": a.comm_id,
            "source_comm_label": f"沟通 #{a.comm_id}" if is_comm else "",
            "linked_count": link_counts.get(a.id, 0),
        })

    return {"folders": _folder_tree(folders), "files": files}


# ── 新建文件夹 ──
@router.post("/folders", response_model=FileFolderOut)
def create_folder(project_id: str, task_id: str, data: FileFolderCreate, db: Session = Depends(get_db)):
    proj, task = _resolve(db, project_id, task_id)
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(400, "文件夹名称不能为空")
    if data.parent_id is not None:
        parent = db.query(FileFolder).filter(
            FileFolder.id == data.parent_id, FileFolder.task_id == task.id
        ).first()
        if not parent:
            raise HTTPException(404, "父文件夹不存在")
    dup = db.query(FileFolder).filter(
        FileFolder.task_id == task.id,
        FileFolder.parent_id == data.parent_id,
        FileFolder.name == name,
    ).first()
    if dup:
        raise HTTPException(400, "同级已存在同名文件夹")
    folder = FileFolder(task_id=task.id, parent_id=data.parent_id, name=name)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    touch_project(db, task.project_id)
    return folder


# ── 重命名 / 移动文件夹 ──
@router.put("/folders/{folder_id}", response_model=FileFolderOut)
def update_folder(project_id: str, task_id: str, folder_id: int, data: FileFolderUpdate, db: Session = Depends(get_db)):
    proj, task = _resolve(db, project_id, task_id)
    folder = db.query(FileFolder).filter(
        FileFolder.id == folder_id, FileFolder.task_id == task.id
    ).first()
    if not folder:
        raise HTTPException(404, "文件夹不存在")

    if data.name is not None:
        name = data.name.strip()
        if not name:
            raise HTTPException(400, "文件夹名称不能为空")
        dup = db.query(FileFolder).filter(
            FileFolder.task_id == task.id,
            FileFolder.parent_id == folder.parent_id,
            FileFolder.name == name,
            FileFolder.id != folder.id,
        ).first()
        if dup:
            raise HTTPException(400, "同级已存在同名文件夹")
        folder.name = name

    if data.parent_id is not None:
        if data.parent_id == folder.id:
            raise HTTPException(400, "不能移动到自身")
        target = db.query(FileFolder).filter(
            FileFolder.id == data.parent_id, FileFolder.task_id == task.id
        ).first()
        if not target:
            raise HTTPException(404, "目标文件夹不存在")
        # 防环：沿目标父链向上，遇到自身则成环
        anc = target
        seen = set()
        while anc is not None and anc.id not in seen:
            seen.add(anc.id)
            if anc.id == folder.id:
                raise HTTPException(400, "不能移动到自身子文件夹（会形成循环）")
            anc = db.query(FileFolder).filter(FileFolder.id == anc.parent_id).first()
        folder.parent_id = data.parent_id

    db.commit()
    db.refresh(folder)
    touch_project(db, task.project_id)
    return folder


# ── 删除文件夹（级联：子孙文件夹 + 其中文件） ──
@router.delete("/folders/{folder_id}")
def delete_folder(project_id: str, task_id: str, folder_id: int, db: Session = Depends(get_db)):
    proj, task = _resolve(db, project_id, task_id)
    folder = db.query(FileFolder).filter(
        FileFolder.id == folder_id, FileFolder.task_id == task.id
    ).first()
    if not folder:
        raise HTTPException(404, "文件夹不存在")

    # 收集全部子孙文件夹 id（BFS）
    ids = [folder.id]
    frontier = [folder.id]
    while frontier:
        kids = db.query(FileFolder.id).filter(
            FileFolder.task_id == task.id, FileFolder.parent_id.in_(frontier)
        ).all()
        frontier = [k[0] for k in kids]
        ids.extend(frontier)

    for fid in ids:
        atts = db.query(Attachment).filter(Attachment.folder_id == fid).all()
        for a in atts:
            if a.comm_id is None:
                # 独立文件：删磁盘 + 解除沟通引用 + 删记录
                db.query(CommunicationFile).filter(CommunicationFile.attachment_id == a.id).delete()
                if a.file_path and os.path.isfile(a.file_path):
                    os.remove(a.file_path)
                db.delete(a)
            else:
                # 沟通附件：文件夹删除后归位根层级，沟通记录不受影响
                a.folder_id = None

    db.query(FileFolder).filter(FileFolder.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    touch_project(db, task.project_id)
    return {"ok": True, "deleted_folders": len(ids)}


# ── 独立上传到文件管理 ──
@router.post("", response_model=AttachmentOut)
async def upload_task_file(
    project_id: str,
    task_id: str,
    folder_id: Optional[int] = Query(None, description="目标文件夹，空=根层级"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    proj, task = _resolve(db, project_id, task_id)
    if folder_id is not None:
        folder = db.query(FileFolder).filter(
            FileFolder.id == folder_id, FileFolder.task_id == task.id
        ).first()
        if not folder:
            raise HTTPException(404, "文件夹不存在")

    sub_dir = f"{proj.display_id}/{task.display_id}/files"
    save_dir = os.path.join(UPLOAD_DIR, sub_dir)
    os.makedirs(save_dir, exist_ok=True)
    ext = os.path.splitext(file.filename)[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(save_dir, unique_name)
    size = 0
    max_size = get_max_file_size()
    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(1024 * 64):
            size += len(chunk)
            if size > max_size:
                await f.close()
                os.remove(file_path)
                raise HTTPException(413, f"文件超过 {max_size // (1024*1024)}MB 限制")
            await f.write(chunk)

    att = Attachment(
        comm_id=None,
        task_id=task.id,
        folder_id=folder_id,
        filename=unique_name,
        original_filename=file.filename,
        file_path=file_path,
        file_size=size,
        mime_type=file.content_type or "",
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    touch_project(db, task.project_id)
    return att


# ── 移动文件到文件夹（folder_id 空=根层级） ──
@router.put("/attachments/{attachment_id}/move", response_model=AttachmentOut)
def move_attachment(project_id: str, task_id: str, attachment_id: int, data: AttachmentMoveIn, db: Session = Depends(get_db)):
    proj, task = _resolve(db, project_id, task_id)
    att = db.query(Attachment).filter(
        Attachment.id == attachment_id, Attachment.task_id == task.id
    ).first()
    if not att:
        raise HTTPException(404, "文件不存在")
    if data.folder_id is not None:
        folder = db.query(FileFolder).filter(
            FileFolder.id == data.folder_id, FileFolder.task_id == task.id
        ).first()
        if not folder:
            raise HTTPException(404, "目标文件夹不存在")
    att.folder_id = data.folder_id
    db.commit()
    db.refresh(att)
    touch_project(db, task.project_id)
    return att


# ── 沟通记录引用文件管理文件（多对多，不随移动失效） ──
@comm_router.post("/links")
def link_files(project_id: str, task_id: str, comm_id: int, data: CommunicationLinkIn, db: Session = Depends(get_db)):
    proj, task = _resolve(db, project_id, task_id)
    comm = db.query(Communication).filter(
        Communication.id == comm_id, Communication.task_id == task.id
    ).first()
    if not comm:
        raise HTTPException(404, "沟通记录不存在")
    added = []
    for aid in data.attachment_ids:
        att = db.query(Attachment).filter(
            Attachment.id == aid, Attachment.task_id == task.id
        ).first()
        if not att:
            raise HTTPException(404, f"附件 {aid} 不存在")
        if att.comm_id is not None:
            raise HTTPException(400, f"附件 {aid} 是沟通上传文件，不能重复引用")
        exists = db.query(CommunicationFile).filter(
            CommunicationFile.communication_id == comm.id,
            CommunicationFile.attachment_id == aid,
        ).first()
        if exists:
            continue
        db.add(CommunicationFile(communication_id=comm.id, attachment_id=aid))
        added.append(att)
    db.commit()
    touch_project(db, task.project_id)
    return {"ok": True, "linked": [a.id for a in added]}


# ── 解除引用（仅解绑，不删文件） ──
@comm_router.delete("/links/{attachment_id}")
def unlink_file(project_id: str, task_id: str, comm_id: int, attachment_id: int, db: Session = Depends(get_db)):
    proj, task = _resolve(db, project_id, task_id)
    comm = db.query(Communication).filter(
        Communication.id == comm_id, Communication.task_id == task.id
    ).first()
    if not comm:
        raise HTTPException(404, "沟通记录不存在")
    link = db.query(CommunicationFile).filter(
        CommunicationFile.communication_id == comm.id,
        CommunicationFile.attachment_id == attachment_id,
    ).first()
    if not link:
        raise HTTPException(404, "引用不存在")
    db.delete(link)
    db.commit()
    touch_project(db, task.project_id)
    return {"ok": True}
