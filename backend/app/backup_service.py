"""
备份与恢复服务
支持：全量备份、部分备份、备份还原、单项目导出、定时备份调度
"""
import enum
import json
import os
import shutil
import threading
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import Session

from .database import DB_PATH, UPLOAD_DIR, CONFIG_DIR, BASE_DIR
from .settings_manager import load_settings, save_settings

# ── 备份存储目录 ──
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
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

def create_backup(scope: str = BackupScope.FULL.value) -> str:
    """创建备份，返回备份文件路径
    
    scope: full / db_config / db_only
    """
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"taskm_backup_{timestamp}_{scope}.zip"
    filepath = os.path.join(BACKUP_DIR, filename)

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
        settings_path = os.path.join(BASE_DIR, "settings.json")
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
            if zf.extract("database/taskm.db", BACKUP_DIR):
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

            # 还原 settings
            if "settings/settings.json" in zf.namelist():
                zf.extract("settings/settings.json", BACKUP_DIR)
                src = os.path.join(BACKUP_DIR, "settings", "settings.json")
                dst = os.path.join(BASE_DIR, "settings.json")
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
                        dst = os.path.join(BASE_DIR, name)
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
                        dst = os.path.join(BASE_DIR, name)
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
                    "contact_info": c.contact_info, "sort_letter": c.sort_letter,
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
                    [{"checkin_id": l.checkin_id, "project_id": l.project_id}
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
        "sort_order": p.sort_order, "is_default": p.is_default,
        "is_active": p.is_active,
    }


# ═══════════════════════════════════════════════════════════
#  定时备份调度
# ═══════════════════════════════════════════════════════════

DEFAULT_SCHEDULE = {
    "enabled": False,
    "frequency": "daily",      # daily / weekly / monthly / manual
    "scope": "full",
    "max_keep": 10,
    "hour": 3,                 # 凌晨 3 点
    "day_of_week": 0,          # 周一（weekly）
    "day_of_month": 1,         # 1 号（monthly）
}


def get_backup_schedule() -> dict:
    """读取备份调度配置"""
    settings = load_settings()
    return settings.get("backup_schedule", dict(DEFAULT_SCHEDULE))


def set_backup_schedule(schedule: dict) -> dict:
    """保存备份调度配置"""
    current = get_backup_schedule()
    current.update(schedule)
    save_settings({"backup_schedule": current})
    return current


def _should_run_now(schedule: dict) -> bool:
    """检查当前时间是否到达了备份时刻"""
    if not schedule.get("enabled"):
        return False

    now = datetime.now()
    frequency = schedule.get("frequency", "manual")
    hour = schedule.get("hour", 3)

    if frequency == "manual":
        return False
    if frequency == "daily":
        return now.hour == hour
    if frequency == "weekly":
        return now.hour == hour and now.weekday() == schedule.get("day_of_week", 0)
    if frequency == "monthly":
        return now.hour == hour and now.day == schedule.get("day_of_month", 1)

    return False


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
    """执行一次定时备份"""
    schedule = get_backup_schedule()
    if not schedule.get("enabled"):
        return
    try:
        filepath = create_backup(schedule.get("scope", "full"))
        _cleanup_old_backups(schedule.get("max_keep", 10))
        print(f"[backup] 定时备份完成: {filepath}", flush=True)
    except Exception as e:
        print(f"[backup] 定时备份失败: {e}", flush=True)


def start_background_scheduler(interval_seconds: int = 3600):
    """启动后台备份调度线程（每小时检查一次）"""
    global _background_thread, _stop_event
    if _background_thread and _background_thread.is_alive():
        return

    _stop_event.clear()

    def _loop():
        last_check_date = None
        while not _stop_event.is_set():
            now = datetime.now()
            # 每天只检查/执行一次
            check_date = now.strftime("%Y-%m-%d")
            if check_date != last_check_date:
                if _should_run_now(get_backup_schedule()):
                    _run_scheduled_backup()
                last_check_date = check_date
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
