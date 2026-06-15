"""
迁移脚本：为 requirements 表添加 description 列
"""
import os, sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app.database import engine, DB_PATH
from sqlalchemy import inspect, text

try:
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns('requirements')]
    if 'description' not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE requirements ADD COLUMN description TEXT DEFAULT ''"))
            conn.commit()
            print("OK - added description column to requirements table")
    else:
        print("OK - description column already exists, skipped")
except Exception as e:
    print(f"ERROR: {e}")
