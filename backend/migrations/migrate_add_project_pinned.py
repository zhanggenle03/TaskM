"""
迁移脚本：为 projects 表添加 pinned 列（置顶功能）
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from sqlalchemy import inspect, text


def main():
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("projects")]
    if "pinned" not in columns:
        print("添加 pinned 列到 projects 表...")
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE projects ADD COLUMN pinned BOOLEAN DEFAULT 0"
            ))
            conn.commit()
        print("列添加完成")
    else:
        print("pinned 列已存在，跳过")


if __name__ == "__main__":
    main()
