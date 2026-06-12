#!/usr/bin/env python3
"""迁移脚本：删除 requirements 表中的 description 和 due_date 列"""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from app.database import engine
from sqlalchemy import text, inspect


def main():
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("requirements")]

    if "description" not in columns and "due_date" not in columns:
        print("[迁移] 列 description/due_date 已不存在，跳过")
        return

    print(f"[迁移] 当前 requirements 列: {columns}")
    print("[迁移] 创建新表 (不含 description, due_date)...")

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            # 1. 创建新临时表（不含 description / due_date）
            conn.execute(text("""
                CREATE TABLE requirements_new (
                    id INTEGER NOT NULL PRIMARY KEY,
                    project_id INTEGER NOT NULL REFERENCES projects(id),
                    display_id VARCHAR(50) UNIQUE,
                    title VARCHAR(300) NOT NULL,
                    priority VARCHAR(20),
                    status VARCHAR(50),
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """))

            # 2. 复制数据（跳过 description / due_date）
            conn.execute(text("""
                INSERT INTO requirements_new (id, project_id, display_id, title, priority, status, created_at, updated_at)
                SELECT id, project_id, display_id, title, priority, status, created_at, updated_at
                FROM requirements
            """))

            old_count = conn.execute(text("SELECT COUNT(*) FROM requirements")).scalar()
            new_count = conn.execute(text("SELECT COUNT(*) FROM requirements_new")).scalar()
            print(f"[迁移] 旧表 {old_count} 行 → 新表 {new_count} 行")

            # 3. 删除旧表
            conn.execute(text("DROP TABLE requirements"))

            # 4. 重命名新表
            conn.execute(text("ALTER TABLE requirements_new RENAME TO requirements"))

            # 5. 重建索引
            conn.execute(text("""
                CREATE INDEX ix_requirements_id ON requirements (id)
            """))

            trans.commit()
            print("[迁移] 完成！已删除 description 和 due_date 列")

        except Exception as e:
            trans.rollback()
            print(f"[迁移] 失败: {e}")
            raise


if __name__ == "__main__":
    main()
