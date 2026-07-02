"""
备份与恢复路由
"""
import os
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..backup_service import (
    BACKUP_DIR,
    create_backup,
    list_backups,
    delete_backup,
    get_backup_path,
    restore_backup,
    export_single_project,
    get_backup_schedule,
    set_backup_schedule,
    DEFAULT_SCHEDULE,
)
from ..database import SessionLocal, Project

router = APIRouter(prefix="/backup", tags=["backup"])


# ── 数据模型 ──

class BackupCreateRequest(BaseModel):
    scope: str = "full"  # full / db_config / db_only


class RestoreRequest(BaseModel):
    """还原请求：上传文件后通过文件名指定"""
    filename: str
    restore_scope: str = "auto"  # auto / full / db_config / db_only


class RestoreByFilenameRequest(BaseModel):
    """从备份列表直接还原"""
    filename: str
    restore_scope: str = "auto"


class ProjectExportRequest(BaseModel):
    project_id: int
    include_uploads: bool = True


class ScheduleUpdate(BaseModel):
    enabled: bool | None = None
    frequency: str | None = None       # daily/weekly/monthly/manual
    scope: str | None = None            # full/db_config/db_only
    max_keep: int | None = None
    interval_hours: int | None = None


# ── API ──

@router.post("/create")
def api_create_backup(body: BackupCreateRequest):
    """创建备份"""
    try:
        filepath = create_backup(body.scope)
        stat = os.stat(filepath)
        return {
            "success": True,
            "filename": os.path.basename(filepath),
            "size": stat.st_size,
            "scope": body.scope,
        }
    except Exception as e:
        raise HTTPException(500, f"备份创建失败: {e}")


@router.get("/list")
def api_list_backups():
    """列出所有备份"""
    return list_backups()


@router.get("/download/{filename}")
def api_download_backup(filename: str):
    """下载备份文件"""
    fp = get_backup_path(filename)
    if not fp:
        raise HTTPException(404, "备份文件不存在")
    return FileResponse(
        fp,
        filename=filename,
        media_type="application/zip",
    )


@router.delete("/delete/{filename}")
def api_delete_backup(filename: str):
    """删除备份"""
    if delete_backup(filename):
        return {"success": True}
    raise HTTPException(404, "备份文件不存在")


@router.post("/restore")
async def api_restore_backup(
    file: UploadFile = File(...),
    restore_scope: str = Form("auto"),
    confirm: bool = Form(False),
):
    """上传备份文件并还原
    
    - file: ZIP 备份文件
    - restore_scope: auto / full / db_config / db_only
    - confirm: 必须为 true 才会执行还原
    """
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(400, "请上传 .zip 备份文件")

    if not confirm:
        raise HTTPException(400, "请确认还原操作（confirm=true）")

    # 保存上传的备份文件到临时位置
    temp_path = os.path.join(BACKUP_DIR, f"_upload_{file.filename}")
    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        result = restore_backup(temp_path, restore_scope)
        return result
    except Exception as e:
        raise HTTPException(500, f"还原失败: {e}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/restore-by-name")
def api_restore_by_name(body: RestoreByFilenameRequest):
    """从备份目录中的文件直接还原（无需上传）"""
    fp = get_backup_path(body.filename)
    if not fp:
        raise HTTPException(404, "备份文件不存在")
    result = restore_backup(fp, body.restore_scope)
    return result


@router.post("/export-project")
def api_export_project(body: ProjectExportRequest):
    """导出单个项目的所有数据"""
    try:
        # 验证项目存在
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == body.project_id).first()
            if not project:
                raise HTTPException(404, "项目不存在")
        finally:
            db.close()

        filepath = export_single_project(body.project_id, body.include_uploads)
        if not filepath:
            raise HTTPException(500, "导出失败")

        filename = os.path.basename(filepath)
        return FileResponse(
            filepath,
            filename=filename,
            media_type="application/zip",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"项目导出失败: {e}")


@router.get("/projects")
def api_list_projects():
    """列出所有项目（供导出选择）"""
    db = SessionLocal()
    try:
        projects = db.query(Project).order_by(Project.name).all()
        return [
            {"id": p.id, "display_id": p.display_id, "name": p.name}
            for p in projects
        ]
    finally:
        db.close()


@router.post("/backup-project")
def api_backup_project(body: ProjectExportRequest):
    """备份单个项目（将项目数据打包为备份文件，存入备份目录）"""
    try:
        # 验证项目存在
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == body.project_id).first()
            if not project:
                raise HTTPException(404, "项目不存在")
        finally:
            db.close()

        filepath = export_single_project(body.project_id, body.include_uploads)
        if not filepath:
            raise HTTPException(500, "备份失败")

        stat = os.stat(filepath)
        return {
            "success": True,
            "filename": os.path.basename(filepath),
            "size": stat.st_size,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"项目备份失败: {e}")


class ProjectRestoreRequest(BaseModel):
    filename: str
    mode: str = "overwrite"  # overwrite / new


@router.post("/restore-project")
def api_restore_project(body: ProjectRestoreRequest):
    """从项目备份 ZIP 还原项目（按文件名）"""
    try:
        from ..backup_service import restore_project_backup
        result = restore_project_backup(body.filename, body.mode)
        if not result.get("success"):
            raise HTTPException(400, result.get("error", "还原失败"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"项目还原失败: {e}")


@router.post("/restore-project-upload")
async def api_restore_project_upload(
    file: UploadFile = File(...),
    mode: str = Form("overwrite"),
):
    """上传项目备份 ZIP 并还原"""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(400, "请上传 .zip 备份文件")

    # 先保存到备份目录
    safe_name = file.filename.replace("\\", "/").split("/")[-1]
    saved_path = os.path.join(BACKUP_DIR, safe_name)
    try:
        content = await file.read()
        with open(saved_path, "wb") as f:
            f.write(content)

        from ..backup_service import restore_project_backup
        result = restore_project_backup(safe_name, mode)
        if not result.get("success"):
            raise HTTPException(400, result.get("error", "还原失败"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"项目还原失败: {e}")


# ── 调度配置 ──

@router.get("/schedule")
def api_get_schedule():
    """获取备份调度配置"""
    return get_backup_schedule()


@router.put("/schedule")
def api_set_schedule(body: ScheduleUpdate):
    """更新备份调度配置"""
    data = {}
    if body.enabled is not None:
        data["enabled"] = body.enabled
    if body.frequency is not None:
        if body.frequency not in ("daily", "weekly", "monthly", "manual"):
            raise HTTPException(400, "frequency 必须为 daily/weekly/monthly/manual")
        data["frequency"] = body.frequency
    if body.scope is not None:
        if body.scope not in ("full", "db_config", "db_only"):
            raise HTTPException(400, "scope 必须为 full/db_config/db_only")
        data["scope"] = body.scope
    if body.max_keep is not None:
        if body.max_keep < 1 or body.max_keep > 100:
            raise HTTPException(400, "max_keep 必须在 1~100 之间")
        data["max_keep"] = body.max_keep
    if body.interval_hours is not None:
        if body.interval_hours < 1 or body.interval_hours > 720:
            raise HTTPException(400, "interval_hours 必须在 1~720 之间")
        data["interval_hours"] = body.interval_hours
    return set_backup_schedule(data)
