"""
备份与恢复服务
支持：全量备份、部分备份、备份还原、单项目导出、定时备份调度
"""
import enum
import json
import os
import shutil
import sqlite3
import sys
import threading
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import Session

from .database import DB_PATH, UPLOAD_DIR, CONFIG_DIR, BASE_DIR as APP_BASE_DIR
from .settings_manager import load_settings, save_settings

# ── 备份存储目录（发行版：用 exe 所在目录，避免 PyInstaller 临时路径） ──
if getattr(sys, "frozen", False):
    _BACKUP_BASE = os.path.dirname(os.path.abspath(sys.executable))
else:
    _BACKUP_BASE = APP_BASE_DIR
BACKUP_DIR = os.path.join(_BACKUP_BASE, "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

# ── 备份范围 ──
class BackupScope(str, enum.Enum):
    FULL = "full"            # DB + settings + configs + uploads
    DB_CONFIG = "db_config"  # DB + settings + configs
    DB_ONLY = "db_only"      # DB only

# ── 定时备份线程 ──
_background_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


# ═══════════════════════════════════════════════════════════
#  主备份函数
# ═══════════════════════════════════════════════════════════

def _wal_checkpoint():
    """备份前强制执行 WAL checkpoint(TRUNCATE)，确保 WAL 中未回收的近期数据合并进主库。

    如果 checkpoint 失败（例如被写入线程锁住），静默跳过，不影响备份继续执行。
    """
    if not os.path.exists(DB_PATH):
        return
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.close()
    except Exception as e:
        print(f"[backup] WAL checkpoint 失败（不影响备份）: {e}", flush=True)


def create_backup(scope: str = BackupScope.FULL.value) -> str:
    """创建备份，返回备份文件路径
    
    scope: full / db_config / db_only
    """
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"taskm_backup_{timestamp}_{scope}.zip"
    filepath = os.path.join(BACKUP_DIR, filename)

    # ── 备份前先 WAL checkpoint，确保近期数据已入主库 ──
    _wal_checkpoint()

    with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
        # ── manifest ──
        manifest = {
            "version": "1.0",
            "created_at": now.isoformat(),
            "scope": scope,
            "app": "TaskM Backup",
            "db_path": os.path.basename(DB_PATH),
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

        # ── 数据库（总是包含） ──
        if os.path.exists(DB_PATH):
            zf.write(DB_PATH, "database/taskm.db")

        # ── settings.json ──
        settings_path = os.path.join(APP_BASE_DIR, "settings.json")
        if os.path.exists(settings_path):
            zf.write(settings_path, "settings/settings.json")

        # ── config/ 项目配置 ──
        if scope in (BackupScope.FULL.value, BackupScope.DB_CONFIG.value):
            if os.path.isdir(CONFIG_DIR):
                _add_dir_to_zip(zf, CONFIG_DIR, "config")

        # ── uploads/ ──
        if scope == BackupScope.FULL.value:
            if os.path.isdir(UPLOAD_DIR):
                _add_dir_to_zip(zf, UPLOAD_DIR, "uploads")

    return filepath


def _add_dir_to_zip(zf: zipfile.ZipFile, src_dir: str, arc_prefix: str):
    """将目录递归添加到 ZIP"""
    for root, dirs, files in os.walk(src_dir):
        for fn in files:
            file_path = os.path.join(root, fn)
            rel_path = os.path.relpath(file_path, os.path.dirname(src_dir))
            zf.write(file_path, rel_path)


# ═══════════════════════════════════════════════════════════
#  备份列表管理
# ═══════════════════════════════════════════════════════════

def list_backups() -> list[dict]:
    """列出所有备份文件"""
    backups = []
    if not os.path.isdir(BACKUP_DIR):
        return backups
    for fn in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if not fn.endswith(".zip"):
            continue
        fp = os.path.join(BACKUP_DIR, fn)
        stat = os.stat(fp)
        backups.append({
            "filename": fn,
            "size": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return backups


def delete_backup(filename: str) -> bool:
    """删除指定备份文件"""
    fp = os.path.join(BACKUP_DIR, filename)
    if os.path.exists(fp) and filename.endswith(".zip"):
        os.remove(fp)
        return True
    return False


def get_backup_path(filename: str) -> Optional[str]:
    """获取备份文件的绝对路径"""
    fp = os.path.join(BACKUP_DIR, filename)
    if os.path.exists(fp) and filename.endswith(".zip"):
        return fp
    return None


# ═══════════════════════════════════════════════════════════
#  还原
# ═══════════════════════════════════════════════════════════

def restore_backup(backup_path: str, restore_scope: str = "auto") -> dict:
    """还原备份
    
    restore_scope: auto(从manifest读取) / full / db_config / db_only
    返回还原统计
    """
    if not os.path.exists(backup_path):
        return {"success": False, "error": "备份文件不存在"}

    result = {"success": True, "restored": [], "skipped": []}

    try:
        with zipfile.ZipFile(backup_path, "r") as zf:
            # 读取 manifest
            if "manifest.json" in zf.namelist():
                manifest = json.loads(zf.read("manifest.json"))
                if restore_scope == "auto":
                    restore_scope = manifest.get("scope", "full")
            else:
                restore_scope = "full" if restore_scope == "auto" else restore_scope

            # 还原 database
            if "database/taskm.db" in [n.replace("\\", "/") for n in zf.namelist()]:
                zf.extract("database/taskm.db", BACKUP_DIR)
                db_temp = os.path.join(BACKUP_DIR, "database", "taskm.db")
                # 备份当前DB做安全快照
                if os.path.exists(DB_PATH):
                    snapshot = os.path.join(BACKUP_DIR, f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}_taskm.db")
                    shutil.copy2(DB_PATH, snapshot)
                    result["snapshot"] = snapshot
                shutil.move(db_temp, DB_PATH)
                result["restored"].append("database/taskm.db")
                # 清理临时目录
                _clean_temp_db_dir()
            else:
                result["error"] = "备份文件中未找到数据库文件（database/taskm.db）"
                result["success"] = False
                return result

            # 还原 settings
            if "settings/settings.json" in zf.namelist():
                zf.extract("settings/settings.json", BACKUP_DIR)
                src = os.path.join(BACKUP_DIR, "settings", "settings.json")
                dst = os.path.join(APP_BASE_DIR, "settings.json")
                shutil.copy2(src, dst)
                result["restored"].append("settings/settings.json")
                # 清理
                shutil.rmtree(os.path.join(BACKUP_DIR, "settings"), ignore_errors=True)

            # 还原 config
            should_restore_config = restore_scope in ("full", "db_config")
            if should_restore_config:
                for name in zf.namelist():
                    if name.startswith("config/") and not name.endswith("/"):
                        zf.extract(name, BACKUP_DIR)
                        # 移到正确位置
                        src = os.path.join(BACKUP_DIR, name)
                        dst = os.path.join(APP_BASE_DIR, name)
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(src, dst)
                        result["restored"].append(name)
                # 清理临时目录
                temp_config = os.path.join(BACKUP_DIR, "config")
                if os.path.isdir(temp_config):
                    shutil.rmtree(temp_config, ignore_errors=True)

            # 还原 uploads
            should_restore_uploads = restore_scope == "full"
            if should_restore_uploads:
                for name in zf.namelist():
                    if name.startswith("uploads/") and not name.endswith("/"):
                        zf.extract(name, BACKUP_DIR)
                        src = os.path.join(BACKUP_DIR, name)
                        dst = os.path.join(APP_BASE_DIR, name)
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(src, dst)
                        result["restored"].append(name)
                # 清理临时目录
                temp_uploads = os.path.join(BACKUP_DIR, "uploads")
                if os.path.isdir(temp_uploads):
                    shutil.rmtree(temp_uploads, ignore_errors=True)

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)

    return result


def _clean_temp_db_dir():
    """清理还原时解压的临时数据库目录"""
    db_temp_dir = os.path.join(BACKUP_DIR, "database")
    if os.path.isdir(db_temp_dir):
        shutil.rmtree(db_temp_dir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════
#  单项目导出
# ═══════════════════════════════════════════════════════════

def export_single_project(project_id: int, include_uploads: bool = True) -> Optional[str]:
    """导出单个项目的所有数据为 ZIP，返回文件路径"""
    from .database import SessionLocal
    from .database import (
        Project, Task, Communication, Contact, Requirement,
        StatusPool, CommTypePool, TagPool, ProjectContact,
        RequirementStatusPool, RequirementPriorityPool,
        RequirementCustomField, RequirementCustomValue,
        Checkin, CheckinProject, CheckinTask,
        Attachment, CommunicationContact, TaskTag, TaskRequirement,
        HolidayOverride,
    )
    from sqlalchemy.orm import joinedload

    db: Session = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return None

        display_id = project.display_id or f"P{project_id}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"project_{display_id}_{timestamp}.zip"
        filepath = os.path.join(BACKUP_DIR, filename)

        with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
            # ── project.json ──
            project_data = {
                "id": project.id,
                "display_id": project.display_id,
                "custom_prefix": project.custom_prefix,
                "name": project.name,
                "description": project.description,
                "start_date": project.start_date.isoformat() if project.start_date else None,
                "created_at": project.created_at.isoformat() if project.created_at else None,
                "updated_at": project.updated_at.isoformat() if project.updated_at else None,
                "category": project.category or "",
            }
            zf.writestr("project.json", json.dumps(project_data, indent=2, ensure_ascii=False))

            # ── status_pools ──
            pools = db.query(StatusPool).filter(StatusPool.project_id == project_id).all()
            zf.writestr("status_pools.json", json.dumps(
                [_pool_dict(p) for p in pools], indent=2, ensure_ascii=False
            ))

            # ── comm_type_pools ──
            ct_pools = db.query(CommTypePool).filter(CommTypePool.project_id == project_id).all()
            zf.writestr("comm_type_pools.json", json.dumps(
                [_pool_dict(p) for p in ct_pools], indent=2, ensure_ascii=False
            ))

            # ── tag_pools ──
            tag_pools = db.query(TagPool).filter(TagPool.project_id == project_id).all()
            zf.writestr("tag_pools.json", json.dumps(
                [_pool_dict(p) for p in tag_pools], indent=2, ensure_ascii=False
            ))

            # ── project_contacts ──
            contacts = db.query(ProjectContact).filter(ProjectContact.project_id == project_id).all()
            zf.writestr("project_contacts.json", json.dumps(
                [{
                    "id": c.id, "name": c.name, "role": c.role,
                    "contact_info": c.contact_info, "sort_letter": getattr(c, "sort_letter", ""),
                    "is_active": c.is_active,
                } for c in contacts], indent=2, ensure_ascii=False
            ))

            # ── requirement status/priority pools ──
            req_sp = db.query(RequirementStatusPool).filter(RequirementStatusPool.project_id == project_id).all()
            zf.writestr("requirement_status_pools.json", json.dumps(
                [_pool_dict(p) for p in req_sp], indent=2, ensure_ascii=False
            ))
            req_pp = db.query(RequirementPriorityPool).filter(RequirementPriorityPool.project_id == project_id).all()
            zf.writestr("requirement_priority_pools.json", json.dumps(
                [_pool_dict(p) for p in req_pp], indent=2, ensure_ascii=False
            ))

            # ── requirement_custom_fields ──
            fields = db.query(RequirementCustomField).filter(RequirementCustomField.project_id == project_id).all()
            zf.writestr("requirement_custom_fields.json", json.dumps(
                [{
                    "id": f.id, "field_name": f.field_name, "field_type": f.field_type,
                    "field_options": f.field_options, "sort_order": f.sort_order, "is_active": f.is_active,
                } for f in fields], indent=2, ensure_ascii=False
            ))

            # ── tasks ──
            tasks = db.query(Task).filter(Task.project_id == project_id).all()
            task_ids = [t.id for t in tasks]
            zf.writestr("tasks.json", json.dumps(
                [{
                    "id": t.id, "display_id": t.display_id, "title": t.title,
                    "description": t.description, "status_id": t.status_id,
                    "priority": t.priority, "due_date": t.due_date.isoformat() if t.due_date else None,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                } for t in tasks], indent=2, ensure_ascii=False
            ))

            # ── contacts (task-level) ──
            if task_ids:
                task_contacts = db.query(Contact).filter(
                    Contact.task_id.in_(task_ids)
                ).all()
                zf.writestr("task_contacts.json", json.dumps(
                    [{
                        "id": c.id, "task_id": c.task_id, "name": c.name,
                        "role": c.role, "contact_info": c.contact_info,
                        "project_contact_id": c.project_contact_id,
                    } for c in task_contacts], indent=2, ensure_ascii=False
                ))

                # ── communications ──
                comms = db.query(Communication).filter(
                    Communication.task_id.in_(task_ids)
                ).order_by(Communication.id).all()
                zf.writestr("communications.json", json.dumps(
                    [{
                        "id": c.id, "task_id": c.task_id, "contact_id": c.contact_id,
                        "content": c.content, "comm_type": c.comm_type,
                        "comm_at": c.comm_at.isoformat() if c.comm_at else None,
                        "old_status_id": c.old_status_id, "new_status_id": c.new_status_id,
                    } for c in comms], indent=2, ensure_ascii=False
                ))
                comm_ids = [c.id for c in comms]

                # ── communication_contacts ──
                if comm_ids:
                    cc_links = db.query(CommunicationContact).filter(
                        CommunicationContact.communication_id.in_(comm_ids)
                    ).all()
                    zf.writestr("communication_contacts.json", json.dumps(
                        [{"communication_id": l.communication_id, "contact_id": l.contact_id}
                         for l in cc_links], indent=2, ensure_ascii=False
                    ))

                # ── task_tags ──
                tt_links = db.query(TaskTag).filter(TaskTag.task_id.in_(task_ids)).all()
                zf.writestr("task_tags.json", json.dumps(
                    [{"task_id": l.task_id, "tag_id": l.tag_id} for l in tt_links],
                    indent=2, ensure_ascii=False
                ))

                # ── task_requirements ──
                tr_links = db.query(TaskRequirement).filter(TaskRequirement.task_id.in_(task_ids)).all()
                zf.writestr("task_requirements.json", json.dumps(
                    [{"task_id": l.task_id, "requirement_id": l.requirement_id} for l in tr_links],
                    indent=2, ensure_ascii=False
                ))

                # ── attachments ──
                if comm_ids:
                    atts = db.query(Attachment).filter(
                        Attachment.comm_id.in_(comm_ids)
                    ).all()
                    zf.writestr("attachments.json", json.dumps(
                        [{
                            "id": a.id, "comm_id": a.comm_id,
                            "filename": a.filename, "original_filename": a.original_filename,
                            "file_size": a.file_size, "mime_type": a.mime_type,
                        } for a in atts], indent=2, ensure_ascii=False
                    ))

            # ── requirements ──
            reqs = db.query(Requirement).filter(Requirement.project_id == project_id).all()
            req_ids = [r.id for r in reqs]
            zf.writestr("requirements.json", json.dumps(
                [{
                    "id": r.id, "display_id": r.display_id, "title": r.title,
                    "description": r.description, "status": r.status,
                    "priority": r.priority, "created_at": r.created_at.isoformat() if r.created_at else None,
                } for r in reqs], indent=2, ensure_ascii=False
            ))

            # ── requirement_custom_values ──
            if req_ids:
                rcv = db.query(RequirementCustomValue).filter(
                    RequirementCustomValue.requirement_id.in_(req_ids)
                ).all()
                zf.writestr("requirement_custom_values.json", json.dumps(
                    [{"id": v.id, "requirement_id": v.requirement_id,
                      "field_id": v.field_id, "value": v.value}
                     for v in rcv], indent=2, ensure_ascii=False
                ))

            # ── checkins ──
            checkin_ids_q = (
                db.query(CheckinProject.checkin_id)
                .filter(CheckinProject.project_id == project_id)
            )
            checkin_ids = [row[0] for row in checkin_ids_q.all()]
            if checkin_ids:
                checkins = db.query(Checkin).filter(Checkin.id.in_(checkin_ids)).all()
                zf.writestr("checkins.json", json.dumps(
                    [{
                        "id": c.id, "date": c.date.isoformat() if c.date else None,
                        "content": c.content, "multi_project": c.multi_project,
                    } for c in checkins], indent=2, ensure_ascii=False
                ))
                # checkin_projects
                cp_links = db.query(CheckinProject).filter(
                    CheckinProject.project_id == project_id
                ).all()
                zf.writestr("checkin_projects.json", json.dumps(
                    [{"checkin_id": l.checkin_id, "project_id": l.project_id, "man_days": l.man_days}
                     for l in cp_links], indent=2, ensure_ascii=False
                ))
                # checkin_tasks
                ct_links = db.query(CheckinTask).filter(
                    CheckinTask.checkin_id.in_(checkin_ids)
                ).all()
                zf.writestr("checkin_tasks.json", json.dumps(
                    [{"checkin_id": l.checkin_id, "task_id": l.task_id}
                     for l in ct_links], indent=2, ensure_ascii=False
                ))

            # ── 项目配置（kanban.json, sort.json 等） ──
            proj_config_dir = os.path.join(CONFIG_DIR, display_id)
            if os.path.isdir(proj_config_dir):
                _add_dir_to_zip(zf, proj_config_dir, f"config/{display_id}")

            # ── 附件 ──
            if include_uploads:
                proj_upload_dir = os.path.join(UPLOAD_DIR, display_id)
                if os.path.isdir(proj_upload_dir):
                    _add_dir_to_zip(zf, proj_upload_dir, f"uploads/{display_id}")

    finally:
        db.close()

    return filepath


def _pool_dict(p) -> dict:
    """将池模型转为字典"""
    return {
        "id": p.id, "name": p.name, "color": p.color,
        "sort_order": p.sort_order, "is_default": getattr(p, "is_default", False),
        "is_active": p.is_active,
    }


# ═══════════════════════════════════════════════════════════
#  单项目还原
# ═══════════════════════════════════════════════════════════

def restore_project_backup(filename: str, mode: str = "overwrite") -> dict:
    """从项目备份 ZIP 中还原项目

    mode: overwrite（覆盖现有项目） / new（新建为新项目）
    """
    from .database import SessionLocal
    from .database import (
        Project, Task, Communication, Contact, Requirement,
        StatusPool, CommTypePool, TagPool, ProjectContact,
        RequirementStatusPool, RequirementPriorityPool,
        RequirementCustomField, RequirementCustomValue,
        Checkin, CheckinProject, CheckinTask,
        Attachment, CommunicationContact, TaskTag, TaskRequirement,
        generate_project_display_id, generate_task_display_id,
        generate_requirement_display_id, touch_project,
    )
    from sqlalchemy import text as sa_text
    from datetime import date as dt_date

    filepath = get_backup_path(filename)
    if not filepath:
        return {"success": False, "error": "备份文件不存在"}

    result = {"success": True, "mode": mode}

    try:
        with zipfile.ZipFile(filepath, "r") as zf:
            namelist = [n.replace("\\", "/") for n in zf.namelist()]

            # ── 读取所有 JSON ──
            project_data = json.loads(zf.read("project.json"))
            old_display_id = project_data["display_id"]
            old_proj_no = old_display_id[1:] if old_display_id.startswith("P") else str(project_data["id"])

            status_pools = json.loads(zf.read("status_pools.json")) if "status_pools.json" in namelist else []
            comm_type_pools = json.loads(zf.read("comm_type_pools.json")) if "comm_type_pools.json" in namelist else []
            tag_pools = json.loads(zf.read("tag_pools.json")) if "tag_pools.json" in namelist else []
            project_contacts = json.loads(zf.read("project_contacts.json")) if "project_contacts.json" in namelist else []
            req_status_pools = json.loads(zf.read("requirement_status_pools.json")) if "requirement_status_pools.json" in namelist else []
            req_priority_pools = json.loads(zf.read("requirement_priority_pools.json")) if "requirement_priority_pools.json" in namelist else []
            req_custom_fields = json.loads(zf.read("requirement_custom_fields.json")) if "requirement_custom_fields.json" in namelist else []
            tasks = json.loads(zf.read("tasks.json")) if "tasks.json" in namelist else []
            task_contacts = json.loads(zf.read("task_contacts.json")) if "task_contacts.json" in namelist else []
            comms = json.loads(zf.read("communications.json")) if "communications.json" in namelist else []
            comm_contacts = json.loads(zf.read("communication_contacts.json")) if "communication_contacts.json" in namelist else []
            task_tags = json.loads(zf.read("task_tags.json")) if "task_tags.json" in namelist else []
            task_reqs = json.loads(zf.read("task_requirements.json")) if "task_requirements.json" in namelist else []
            atts = json.loads(zf.read("attachments.json")) if "attachments.json" in namelist else []
            reqs = json.loads(zf.read("requirements.json")) if "requirements.json" in namelist else []
            req_custom_values = json.loads(zf.read("requirement_custom_values.json")) if "requirement_custom_values.json" in namelist else []
            checkins = json.loads(zf.read("checkins.json")) if "checkins.json" in namelist else []
            checkin_projs = json.loads(zf.read("checkin_projects.json")) if "checkin_projects.json" in namelist else []
            checkin_tasks = json.loads(zf.read("checkin_tasks.json")) if "checkin_tasks.json" in namelist else []

        db: Session = SessionLocal()
        try:
            # ── 查找或创建项目 ──
            project = db.query(Project).filter(
                Project.display_id == old_display_id
            ).first()

            if mode == "overwrite" and project:
                # 删除现有项目（级联删除所有关联数据）
                db.delete(project)
                db.commit()
                project = None
            elif mode == "new":
                # 新建模式：忽略同名已有项目，强制创建新项目
                project = None

            if not project:
                # 新建项目
                if mode == "new":
                    # 新建模式：生成新 display_id
                    prefix = project_data.get("custom_prefix") or ""
                    new_display_id, _ = generate_project_display_id(db, prefix)
                else:
                    # 覆盖模式：保留原 display_id
                    new_display_id = old_display_id
                project = Project(
                    display_id=new_display_id,
                    custom_prefix=project_data.get("custom_prefix"),
                    name=project_data["name"],
                    description=project_data.get("description", ""),
                    category=project_data.get("category", ""),
                )
                if project_data.get("start_date"):
                    try:
                        project.start_date = dt_date.fromisoformat(project_data["start_date"][:10])
                    except Exception:
                        pass
                db.add(project)
                db.commit()
                db.refresh(project)
                result["new_project_id"] = project.id
                result["new_display_id"] = project.display_id
            else:
                # 覆盖模式下已存在但没删掉的（理论上不会）
                result["new_project_id"] = project.id
                result["new_display_id"] = project.display_id

            new_project_id = project.id
            proj_id_no_p = project.display_id[1:] if project.display_id.startswith("P") else str(project.id)

            # ── ID 映射表（旧ID → 新ID） ──
            old_status_id_map = {}
            old_comm_type_id_map = {}
            old_tag_id_map = {}
            old_contact_id_map = {}
            old_task_contact_id_map = {}  # 任务对接人（Contact表）
            old_req_status_id_map = {}
            old_req_priority_id_map = {}
            old_cf_id_map = {}
            old_task_id_map = {}
            old_comm_id_map = {}
            old_req_id_map = {}
            old_checkin_id_map = {}

            # ── 还原状态池 ──
            for p in status_pools:
                new_p = StatusPool(
                    project_id=new_project_id, name=p["name"],
                    color=p.get("color", "#5F5E5A"),
                    sort_order=p.get("sort_order", 0),
                    is_default=p.get("is_default", False),
                    is_active=p.get("is_active", True),
                )
                db.add(new_p)
                db.flush()
                old_status_id_map[p["id"]] = new_p.id

            # ── 还原沟通类型池 ──
            for p in comm_type_pools:
                new_p = CommTypePool(
                    project_id=new_project_id, name=p["name"],
                    color=p.get("color", "#5F5E5A"),
                    sort_order=p.get("sort_order", 0),
                    is_default=p.get("is_default", False),
                    is_active=p.get("is_active", True),
                )
                db.add(new_p)
                db.flush()
                old_comm_type_id_map[p["id"]] = new_p.id

            # ── 还原标签池 ──
            for p in tag_pools:
                new_p = TagPool(
                    project_id=new_project_id, name=p["name"],
                    color=p.get("color", "#5F5E5A"),
                    sort_order=p.get("sort_order", 0),
                    is_active=p.get("is_active", True),
                )
                db.add(new_p)
                db.flush()
                old_tag_id_map[p["id"]] = new_p.id

            # ── 还原项目联系人 ──
            for c in project_contacts:
                new_c = ProjectContact(
                    project_id=new_project_id, name=c["name"],
                    role=c.get("role", ""),
                    contact_info=c.get("contact_info", ""),
                    is_active=c.get("is_active", True),
                )
                # sort_letter 可能不存在（旧版数据库无此字段）
                if c.get("sort_letter"):
                    try:
                        new_c.sort_letter = c["sort_letter"]
                    except Exception:
                        pass
                db.add(new_c)
                db.flush()
                old_contact_id_map[c["id"]] = new_c.id

            # ── 还原需求状态池 ──
            for p in req_status_pools:
                new_p = RequirementStatusPool(
                    project_id=new_project_id, name=p["name"],
                    color=p.get("color", "#5F5E5A"),
                    sort_order=p.get("sort_order", 0),
                    is_default=p.get("is_default", False),
                    is_active=p.get("is_active", True),
                )
                db.add(new_p)
                db.flush()
                old_req_status_id_map[p["id"]] = new_p.id

            # ── 还原需求优先级池 ──
            for p in req_priority_pools:
                new_p = RequirementPriorityPool(
                    project_id=new_project_id, name=p["name"],
                    color=p.get("color", "#5F5E5A"),
                    sort_order=p.get("sort_order", 0),
                    is_default=p.get("is_default", False),
                    is_active=p.get("is_active", True),
                )
                db.add(new_p)
                db.flush()
                old_req_priority_id_map[p["id"]] = new_p.id

            # ── 还原自定义字段 ──
            for f in req_custom_fields:
                new_f = RequirementCustomField(
                    project_id=new_project_id,
                    field_name=f["field_name"],
                    field_type=f["field_type"],
                    field_options=f.get("field_options", ""),
                    sort_order=f.get("sort_order", 0),
                    is_active=f.get("is_active", True),
                    is_builtin=f.get("is_builtin", False),
                )
                db.add(new_f)
                db.flush()
                old_cf_id_map[f["id"]] = new_f.id

            # ── 还原任务 ──
            for t in tasks:
                # 新建模式重新生成 display_id
                if mode == "overwrite":
                    task_display_id = t.get("display_id") or generate_task_display_id(db, project)
                else:
                    task_display_id = generate_task_display_id(db, project)
                new_t = Task(
                    project_id=new_project_id,
                    display_id=task_display_id,
                    title=t["title"],
                    description=t.get("description", ""),
                    status_id=old_status_id_map.get(t.get("status_id")),
                    priority=t.get("priority", "normal"),
                    due_date=dt_date.fromisoformat(t["due_date"][:10]) if t.get("due_date") else None,
                )
                db.add(new_t)
                db.flush()
                old_task_id_map[t["id"]] = new_t.id

            # ── 还原任务对接人 ──
            for c in task_contacts:
                new_c = Contact(
                    task_id=old_task_id_map.get(c["task_id"]),
                    name=c["name"],
                    role=c.get("role", ""),
                    contact_info=c.get("contact_info", ""),
                    project_contact_id=old_contact_id_map.get(c.get("project_contact_id")),
                )
                db.add(new_c)
                db.flush()
                old_task_contact_id_map[c["id"]] = new_c.id

            # ── 还原沟通记录 ──
            for c in comms:
                new_c = Communication(
                    task_id=old_task_id_map.get(c["task_id"]),
                    contact_id=old_task_contact_id_map.get(c.get("contact_id")),
                    content=c["content"],
                    comm_type=c.get("comm_type", "note"),
                    old_status_id=old_status_id_map.get(c.get("old_status_id")),
                    new_status_id=old_status_id_map.get(c.get("new_status_id")),
                    comm_at=datetime.fromisoformat(c["comm_at"]) if c.get("comm_at") else None,
                )
                db.add(new_c)
                db.flush()
                old_comm_id_map[c["id"]] = new_c.id

            # ── 还原沟通-对接人关联 ──
            for link in comm_contacts:
                new_cc_id = old_comm_id_map.get(link["communication_id"])
                new_ct_id = old_task_contact_id_map.get(link["contact_id"])
                if new_cc_id and new_ct_id:
                    db.execute(
                        sa_text(
                            "INSERT OR IGNORE INTO communication_contacts (communication_id, contact_id) "
                            "VALUES (:cid, :ctid)"
                        ),
                        {"cid": new_cc_id, "ctid": new_ct_id},
                    )

            # ── 还原任务标签 ──
            for link in task_tags:
                new_tid = old_task_id_map.get(link["task_id"])
                new_tgid = old_tag_id_map.get(link["tag_id"])
                if new_tid and new_tgid:
                    db.execute(
                        sa_text(
                            "INSERT OR IGNORE INTO task_tags (task_id, tag_id) VALUES (:tid, :tgid)"
                        ),
                        {"tid": new_tid, "tgid": new_tgid},
                    )

            # ── 还原任务需求关联 ──
            for link in task_reqs:
                new_tid = old_task_id_map.get(link["task_id"])
                new_rid = old_req_id_map.get(link["requirement_id"])
                if new_tid and new_rid:
                    db.execute(
                        sa_text(
                            "INSERT OR IGNORE INTO task_requirements (task_id, requirement_id) VALUES (:tid, :rid)"
                        ),
                        {"tid": new_tid, "rid": new_rid},
                    )

            # ── 还原需求 ──
            for r in reqs:
                if mode == "overwrite":
                    req_display_id = r.get("display_id") or generate_requirement_display_id(db, project)
                else:
                    req_display_id = generate_requirement_display_id(db, project)
                new_r = Requirement(
                    project_id=new_project_id,
                    display_id=req_display_id,
                    title=r["title"],
                    description=r.get("description", ""),
                    priority=r.get("priority", "normal"),
                    status=r.get("status", "todo"),
                )
                db.add(new_r)
                db.flush()
                old_req_id_map[r["id"]] = new_r.id

            # ── 还原需求自定义值 ──
            for v in req_custom_values:
                new_rid = old_req_id_map.get(v["requirement_id"])
                new_fid = old_cf_id_map.get(v["field_id"])
                if new_rid and new_fid:
                    new_v = RequirementCustomValue(
                        requirement_id=new_rid,
                        field_id=new_fid,
                        value=v.get("value", ""),
                    )
                    db.add(new_v)

            # ── 还原签到 ──
            for c in checkins:
                new_c = Checkin(
                    date=dt_date.fromisoformat(c["date"][:10]) if c.get("date") else None,
                    content=c.get("content", ""),
                    multi_project=c.get("multi_project", False),
                )
                db.add(new_c)
                db.flush()
                old_checkin_id_map[c["id"]] = new_c.id

            # ── 还原签到-项目关联 ──
            for link in checkin_projs:
                new_ckid = old_checkin_id_map.get(link["checkin_id"])
                if new_ckid:
                    try:
                        db.execute(
                            sa_text(
                                "INSERT INTO checkin_projects (checkin_id, project_id, man_days) "
                                "VALUES (:ckid, :pid, :md)"
                            ),
                            {"ckid": new_ckid, "pid": new_project_id,
                             "md": float(link.get("man_days", 1.0) or 1.0)},
                        )
                    except Exception:
                        pass

            # ── 还原签到-任务关联 ──
            for link in checkin_tasks:
                new_ckid = old_checkin_id_map.get(link["checkin_id"])
                new_tid = old_task_id_map.get(link["task_id"])
                if new_ckid and new_tid:
                    try:
                        db.execute(
                            sa_text(
                                "INSERT INTO checkin_tasks (checkin_id, task_id) VALUES (:ckid, :tid)"
                            ),
                            {"ckid": new_ckid, "tid": new_tid},
                        )
                    except Exception:
                        pass

            # ── 还原附件文件 ──
            upload_prefix = f"uploads/{old_display_id}/"
            new_upload_dir = os.path.join(UPLOAD_DIR, project.display_id)
            file_count = 0
            for name in namelist:
                if name.startswith(upload_prefix) and not name.endswith("/"):
                    # 计算新路径
                    rel_path = name[len(upload_prefix):]
                    target = os.path.join(new_upload_dir, rel_path)
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    # 从 ZIP 提取
                    data = zf.read(name)
                    with open(target, "wb") as f:
                        f.write(data)
                    file_count += 1

            # ── 还原项目配置 ──
            config_prefix = f"config/{old_display_id}/"
            new_config_dir = os.path.join(CONFIG_DIR, project.display_id)
            os.makedirs(new_config_dir, exist_ok=True)
            for name in namelist:
                if name.startswith(config_prefix) and not name.endswith("/"):
                    rel_path = name[len(config_prefix):]
                    target = os.path.join(new_config_dir, rel_path)
                    data = zf.read(name)
                    with open(target, "wb") as f:
                        f.write(data)

            touch_project(db, new_project_id)
            db.commit()

            result["project_id"] = new_project_id
            result["display_id"] = project.display_id
            result["file_count"] = file_count
            result["summary"] = (
                f"项目「{project.name}」还原完成 "
                f"（{len(status_pools)}状态池+{len(comm_type_pools)}沟通类型+{len(tag_pools)}标签"
                f"+{len(tasks)}任务+{len(comms)}沟通+{len(reqs)}需求+{len(checkins)}签到）"
            )

        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)

    return result


# ═══════════════════════════════════════════════════════════
#  定时备份调度
# ═══════════════════════════════════════════════════════════

# ── 频率 → 间隔映射 ──
FREQUENCY_TO_HOURS = {
    "daily": 24,
    "weekly": 168,
    "monthly": 720,
    "manual": 0,
}

DEFAULT_SCHEDULE = {
    "enabled": False,
    "frequency": "daily",      # daily / weekly / monthly / manual
    "scope": "full",
    "max_keep": 10,
    "interval_hours": 24,      # 由 frequency 自动映射，也可手工设置
    "last_backup_at": None,    # ISO 格式的上次备份时间戳
}


def _migrate_schedule(schedule: dict) -> dict:
    """向后兼容：旧配置含 hour/day_of_week/day_of_month → 迁移到 interval_hours"""
    if "interval_hours" in schedule:
        return schedule  # 已是最新格式
    freq = schedule.get("frequency", "daily")
    schedule["interval_hours"] = FREQUENCY_TO_HOURS.get(freq, 24)
    schedule["last_backup_at"] = None
    # 清理旧字段
    schedule.pop("hour", None)
    schedule.pop("day_of_week", None)
    schedule.pop("day_of_month", None)
    return schedule


def get_backup_schedule() -> dict:
    """读取备份调度配置（自动迁移旧格式）"""
    settings = load_settings()
    raw = settings.get("backup_schedule", dict(DEFAULT_SCHEDULE))
    return _migrate_schedule(raw)


def set_backup_schedule(schedule: dict) -> dict:
    """保存备份调度配置"""
    current = get_backup_schedule()
    current.update(schedule)
    # 根据 frequency 自动更新 interval_hours（除非调用方显式传入了 interval_hours）
    freq = current.get("frequency", "daily")
    if "interval_hours" not in schedule:
        current["interval_hours"] = FREQUENCY_TO_HOURS.get(freq, 24)
    # 清理旧字段（防残留）
    current.pop("hour", None)
    current.pop("day_of_week", None)
    current.pop("day_of_month", None)
    save_settings({"backup_schedule": current})
    return current


def _is_overdue(schedule: dict) -> bool:
    """检查上次备份是否已过期（距上次备份 >= interval_hours）"""
    if not schedule.get("enabled"):
        return False
    interval = schedule.get("interval_hours", 24)
    if interval <= 0:
        return False  # manual 不自动触发
    last_str = schedule.get("last_backup_at")
    if not last_str:
        return True  # 从未备份 → 立即执行
    try:
        last_dt = datetime.fromisoformat(last_str)
    except (ValueError, TypeError):
        return True
    return (datetime.now() - last_dt) >= timedelta(hours=interval)


def update_last_backup_at(timestamp: str | None = None):
    """更新上次备份时间戳（备份成功后调用）"""
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    schedule = get_backup_schedule()
    schedule["last_backup_at"] = timestamp
    save_settings({"backup_schedule": schedule})


def _cleanup_old_backups(max_keep: int):
    """清理超出保留数的旧备份"""
    backups = list_backups()
    if len(backups) <= max_keep:
        return
    # 按时间升序（旧的在前）
    backups.sort(key=lambda b: b["created_at"])
    for b in backups[:-max_keep]:
        delete_backup(b["filename"])


def _run_scheduled_backup():
    """执行一次定时备份，成功后更新 last_backup_at"""
    schedule = get_backup_schedule()
    if not schedule.get("enabled"):
        return
    try:
        filepath = create_backup(schedule.get("scope", "full"))
        _cleanup_old_backups(schedule.get("max_keep", 10))
        update_last_backup_at()
        print(f"[backup] 定时备份完成: {filepath}", flush=True)
    except Exception as e:
        print(f"[backup] 定时备份失败: {e}", flush=True)


def start_background_scheduler(interval_seconds: int = 3600):
    """启动后台备份调度线程（每小时检查一次，启动时先检查是否过期）"""
    global _background_thread, _stop_event
    if _background_thread and _background_thread.is_alive():
        return

    _stop_event.clear()

    # 启动时立即检查：如果距上次备份已超过间隔，补执行
    try:
        if _is_overdue(get_backup_schedule()):
            print("[backup] 启动检测：备份已过期，立即执行", flush=True)
            _run_scheduled_backup()
    except Exception as e:
        print(f"[backup] 启动时补偿检查失败: {e}", flush=True)

    def _loop():
        while not _stop_event.is_set():
            try:
                if _is_overdue(get_backup_schedule()):
                    _run_scheduled_backup()
            except Exception as e:
                print(f"[backup] 调度检查异常: {e}", flush=True)
            _stop_event.wait(interval_seconds)

    _background_thread = threading.Thread(target=_loop, daemon=True, name="backup-scheduler")
    _background_thread.start()
    print(f"[backup] 后台调度线程已启动 (interval={interval_seconds}s)", flush=True)


def stop_background_scheduler():
    """停止后台调度线程"""
    global _background_thread
    _stop_event.set()
    _background_thread = None
    print("[backup] 后台调度线程已停止", flush=True)
