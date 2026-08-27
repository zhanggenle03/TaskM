from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, Response, HTMLResponse
from sqlalchemy.orm import Session
import uuid
import os
import html as html_mod
from urllib.parse import quote
import aiofiles
from ..database import get_db, Attachment, Communication, Task, Project, UPLOAD_DIR, touch_project, resolve_project, CommunicationFile
from ..schemas import AttachmentOut, AttachmentUpdate
from ..office_convert import is_office_file, convert_to_pdf

router = APIRouter(tags=["attachments"])

ALLOWED_MIME_TYPES = None  # None = 允许所有类型

from ..settings_manager import get_max_file_size


async def save_upload(file: UploadFile, project_display_id: str, task_display_id: str, comm_id: int) -> dict:
    sub_dir = f"{project_display_id}/{task_display_id}/comm_{comm_id}"
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
    return {
        "filename": unique_name,
        "original_filename": file.filename,
        "file_path": file_path,
        "file_size": size,
        "mime_type": file.content_type or "",
    }


# 上传到沟通记录
@router.post("/projects/{project_id}/tasks/{task_id}/communications/{comm_id}/attachments", response_model=AttachmentOut)
async def upload_comm_attachment(
    project_id: str, task_id: str, comm_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    proj = resolve_project(db, project_id)
    task = db.query(Task).filter(Task.display_id == task_id, Task.project_id == proj.id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    comm = db.query(Communication).filter(Communication.id == comm_id, Communication.task_id == task.id).first()
    if not comm:
        raise HTTPException(404, "沟通记录不存在")
    meta = await save_upload(file, proj.display_id, task.display_id, comm_id)
    # 回填 task_id：附件归属任务（文件管理按任务聚合展示）
    att = Attachment(comm_id=comm_id, task_id=task.id, **meta)
    db.add(att)
    db.commit()
    db.refresh(att)
    touch_project(db, task.project_id)
    return att


# 下载附件
@router.get("/attachments/{attachment_id}/download")
def download_attachment(attachment_id: int, db: Session = Depends(get_db)):
    att = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not att or not os.path.exists(att.file_path):
        raise HTTPException(404, "文件不存在")
    encoded_name = quote(att.original_filename, safe='')
    return FileResponse(
        att.file_path,
        media_type=att.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"}
    )


# 预览附件（浏览器内联打开）
@router.get("/attachments/{attachment_id}/preview")
def preview_attachment(attachment_id: int, db: Session = Depends(get_db)):
    att = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not att or not os.path.exists(att.file_path):
        raise HTTPException(404, "文件不存在")

    file_path = att.file_path
    mime_type = att.mime_type or ""

    # Office 文档 → 转换为 PDF 后预览
    if is_office_file(file_path):
        pdf_path = convert_to_pdf(file_path, os.path.dirname(file_path))
        if pdf_path:
            file_path = pdf_path
            mime_type = "application/pdf"
            display_name = os.path.splitext(att.original_filename)[0] + ".pdf"
        else:
            # 转换失败，回退为下载
            encoded_name = quote(att.original_filename, safe='')
            return FileResponse(
                att.file_path,
                media_type=att.mime_type or "application/octet-stream",
                headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"}
            )
    else:
        display_name = att.original_filename
        # 纯文本类扩展名 → 读取内容以 text/plain 返回，.txt 后缀绕过浏览器强制下载
        ext = os.path.splitext(file_path)[1].lower()
        text_exts = {'.txt', '.log', '.md', '.sql', '.py', '.js', '.ts', '.html', '.css',
                     '.json', '.xml', '.yaml', '.yml', '.ini', '.cfg', '.conf',
                     '.sh', '.bat', '.ps1', '.csv', '.env', '.gitignore', '.dockerfile',
                     '.vue', '.java', '.c', '.cpp', '.h', '.go', '.rs', '.rb', '.php'}
        if ext in text_exts:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            safe_name = os.path.splitext(display_name)[0] + '.txt'
            # 用 HTML 包裹，浏览器一定渲染不会下载
            html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>{html_mod.escape(display_name)}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#f8f8f8;padding:16px;font-family:'Cascadia Code','JetBrains Mono','Consolas',monospace;font-size:14px;line-height:1.7}}
pre{{background:#fff;border:1px solid #e0e0e0;border-radius:6px;padding:16px;white-space:pre-wrap;word-break:break-all;color:#333}}
</style></head>
<body><pre>{html_mod.escape(content)}</pre></body></html>'''
            return HTMLResponse(
                content=html_content,
                headers={
                    "Content-Disposition": f"inline; filename*=UTF-8''{quote(safe_name, safe='')}",
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                }
            )

    encoded_name = quote(display_name, safe='')
    return FileResponse(
        file_path,
        media_type=mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_name}",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        }
    )


# 重命名附件
@router.put("/attachments/{attachment_id}", response_model=AttachmentOut)
def rename_attachment(attachment_id: int, data: AttachmentUpdate, db: Session = Depends(get_db)):
    att = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not att:
        raise HTTPException(404, "附件不存在")
    att.original_filename = data.original_filename
    db.commit()
    db.refresh(att)
    # 通过 Communication → Task → Project 链路更新时间
    comm = db.query(Communication).filter(Communication.id == att.comm_id).first()
    if comm:
        task = db.query(Task).filter(Task.id == comm.task_id).first()
        if task:
            touch_project(db, task.project_id)
    return att


# 删除附件
@router.delete("/attachments/{attachment_id}")
def delete_attachment(attachment_id: int, db: Session = Depends(get_db)):
    att = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not att:
        raise HTTPException(404, "附件不存在")
    # 清理沟通记录引用（文件管理独立文件被引用时，删文件同步解除引用）
    db.query(CommunicationFile).filter(CommunicationFile.attachment_id == att.id).delete()
    if os.path.exists(att.file_path):
        os.remove(att.file_path)
    db.delete(att)
    db.commit()
    # 通过 Communication → Task → Project 链路更新时间
    comm = db.query(Communication).filter(Communication.id == att.comm_id).first()
    if comm:
        task = db.query(Task).filter(Task.id == comm.task_id).first()
        if task:
            touch_project(db, task.project_id)
    return {"ok": True}
