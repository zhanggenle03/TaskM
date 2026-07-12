"""
迁移脚本：为 checkins 表添加人天体系字段
- man_days        REAL NOT NULL DEFAULT 1.0   当天人天，默认 1.0
- man_day_reason  VARCHAR(200) DEFAULT ''     人天说明（加班/并行多项目/调休补班等）

仅对「已存在 checkins 表」的旧库执行；全新库由 Base.metadata.create_all 在建表时直接带出这两列。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine
from sqlalchemy import inspect, text


def main():
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("checkins")]

    if "man_days" not in columns:
        print("添加 man_days 列...")
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE checkins ADD COLUMN man_days REAL NOT NULL DEFAULT 1.0"
            ))
            conn.commit()
        print("man_days 列添加完成")
    else:
        print("man_days 列已存在，跳过")

    if "man_day_reason" not in columns:
        print("添加 man_day_reason 列...")
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE checkins ADD COLUMN man_day_reason VARCHAR(200) DEFAULT ''"
            ))
            conn.commit()
        print("man_day_reason 列添加完成")
    else:
        print("man_day_reason 列已存在，跳过")

    print("\n人天体系迁移完成！")


if __name__ == "__main__":
    main()
