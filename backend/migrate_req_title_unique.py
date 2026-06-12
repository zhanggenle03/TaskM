"""
迁移脚本：为 requirements 表添加唯一约束 (project_id, title)
1. 清理存量重复标题（改名）
2. 创建唯一索引 (SQLite 不支持 ALTER TABLE ADD CONSTRAINT)
"""
import os, sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app.database import engine, Requirement
from sqlalchemy import text
from sqlalchemy.orm import Session

def migrate():
    with Session(engine) as db:
        # 1. 检测重复
        rows = db.execute(text("""
            SELECT project_id, title, COUNT(*) as cnt
            FROM requirements
            GROUP BY project_id, title
            HAVING cnt > 1
        """)).all()

        if not rows:
            print("[OK] 无重复标题，无需清理")
        else:
            total_fixed = 0
            for row in rows:
                project_id, title, cnt = row
                dup_rows = db.execute(text("""
                    SELECT id FROM requirements
                    WHERE project_id = :pid AND title = :t
                    ORDER BY id
                """), {"pid": project_id, "t": title}).all()

                # 第一条保留原名，后续加序号
                for i, (rid,) in enumerate(dup_rows):
                    if i == 0:
                        continue
                    suffix = f"（重复_{i}）"
                    new_title = title
                    # 处理超长标题
                    max_len = 300 - len(suffix)
                    if len(new_title) > max_len:
                        new_title = new_title[:max_len]
                    new_title += suffix
                    db.execute(text("""
                        UPDATE requirements SET title = :new_title
                        WHERE id = :rid
                    """), {"new_title": new_title, "rid": rid})
                    total_fixed += 1

            db.commit()
            print(f"[OK] 修复 {total_fixed} 条重复记录")

        # 2. 创建唯一索引（SQLite 不支持 ALTER TABLE ADD CONSTRAINT）
        try:
            db.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_req_project_title
                ON requirements(project_id, title)
            """))
            db.commit()
            print("[OK] 已创建唯一索引 uq_req_project_title")
        except Exception as e:
            db.rollback()
            print(f"[ERR] 创建唯一索引失败: {e}")
            sys.exit(1)

if __name__ == "__main__":
    migrate()
