# -*- coding: utf-8 -*-
"""一次性迁移(2026-09-04):存量需求正文文件补录到 requirement_files。跑完即弃。

背景:需求文件 id 化改造后,新上传走 POST /files 落库;历史正文 <a href> 引用的
文件此前无库记录。本脚本把「正文引用 + 磁盘存在」的存量文件一次性补录为
RequirementFile 行,与 GET /files 的惰性补录逻辑一致(只补缺、不删除、幂等)。

用法(任意目录): D:/python310/python.exe backend/migrations/migrate_req_files_20260904.py
"""
import os
import re
import sys
import sqlite3
import shutil
from datetime import datetime

# 脚本在 backend/migrations/ 下，上溯一级才是 backend/（app 包与 taskm.db 所在）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app.database import (                                      # noqa: E402
    engine, Base, SessionLocal, Project, Requirement, RequirementFile, UPLOAD_DIR,
)

HREF_RE = re.compile(r"/uploads/[^/]+/requirements/[^/]+/files/([^\"\s)]+)")

DB_PATH = os.path.join(BASE_DIR, "taskm.db")


def backup_db():
    """WAL 安全备份:用 sqlite backup API,而非裸拷主库文件。"""
    bak_dir = os.path.join(BASE_DIR, "backups")
    os.makedirs(bak_dir, exist_ok=True)
    bak = os.path.join(bak_dir, "taskm_pre_req_files_20260904.db")
    src = sqlite3.connect(DB_PATH)
    try:
        dst = sqlite3.connect(bak)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    print(f"[backup] 已备份数据库 -> {bak} ({os.path.getsize(bak)//1024} KB)")
    return bak


def main():
    bak = backup_db()

    # 1) 幂等建表:后端若已重启过 create_all,此步为空操作
    Base.metadata.create_all(engine)
    print("[schema] requirement_files 表就绪")

    db = SessionLocal()
    try:
        projs = {p.id: p for p in db.query(Project).all()}
        reqs = db.query(Requirement).all()

        total_href = 0      # 正文引用(去重)总数
        added = 0           # 本次补录
        existed = 0         # 已在库
        orphan = []         # 引用存在但磁盘缺失(不补录)
        for req in reqs:
            proj = projs.get(req.project_id)
            if proj is None:
                continue
            refs = set(HREF_RE.findall(req.description or ""))
            if not refs:
                continue
            total_href += len(refs)

            req_display = req.display_id or f"req_{req.id}"
            files_dir = os.path.join(
                UPLOAD_DIR, proj.display_id, "requirements", req_display, "files",
            )
            have = {r.filename for r in req.files}
            for name in refs:
                if name in have:
                    existed += 1
                    continue
                fp = os.path.join(files_dir, name)
                if not os.path.isfile(fp):
                    orphan.append((proj.display_id, req_display, name))
                    continue
                db.add(RequirementFile(
                    requirement_id=req.id, filename=name, original_filename=name,
                    file_path=fp, file_size=os.path.getsize(fp), mime_type="",
                    uploaded_at=datetime.utcnow(),
                ))
                added += 1
        db.commit()
    finally:
        db.close()

    print(f"\n[result] 扫描需求 {len(reqs)} 个;正文引用文件(去重)共 {total_href} 个")
    print(f"[result] 已在库 {existed} | 本次补录 {added} | 磁盘缺失(未补) {len(orphan)}")
    if orphan:
        print("\n[warning] 以下引用在磁盘找不到文件(正文死链,已跳过):")
        for o in orphan[:20]:
            print("   ", *o)
    print("\n[ok] 迁移完成。后端重启 create_all 幂等跳过;此后 GET /files 不再有新增写入。")
    print(f"     确认无误后可删除备份: {bak}")


if __name__ == "__main__":
    main()
