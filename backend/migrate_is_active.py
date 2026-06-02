"""
迁移脚本：为存量数据添加 is_active 列
运行：python migrate_is_active.py
"""
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app.database import engine, Base, StatusPool, CommTypePool, TagPool, ProjectContact
from sqlalchemy import text, inspect


def column_exists(table_name, column_name):
    """检查表中是否存在某列"""
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def migrate():
    print("=== 开始迁移 is_active 列 ===")

    tables = [
        ("status_pools", StatusPool.__table__),
        ("comm_type_pools", CommTypePool.__table__),
        ("tag_pools", TagPool.__table__),
        ("project_contacts", ProjectContact.__table__),
    ]

    with engine.connect() as conn:
        for table_name, _ in tables:
            if column_exists(table_name, "is_active"):
                print(f"  [{table_name}] is_active 列已存在，跳过")
            else:
                print(f"  [{table_name}] 添加 is_active 列 (default=1)...")
            conn.execute(text(
                f"ALTER TABLE {table_name} ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"
            ))
            print(f"  [{table_name}] OK")

        conn.commit()

    print("=== 迁移完成 ===")


if __name__ == "__main__":
    migrate()
