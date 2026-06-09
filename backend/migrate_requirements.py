"""
需求模块数据迁移脚本。
创建需求相关表，添加 display_id 列，创建状态池和优先级池表并填充默认数据。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base, SessionLocal
from sqlalchemy import inspect, text

from app.database import (
    Requirement, RequirementCustomField, RequirementCustomValue,
    RequirementStatusPool, RequirementPriorityPool,
    generate_requirement_display_id, Project,
)

def migrate():
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # 1. create tables
    new_models = [Requirement, RequirementCustomField, RequirementCustomValue,
                  RequirementStatusPool, RequirementPriorityPool]
    tables_to_create = []
    for model in new_models:
        if model.__tablename__ not in existing_tables:
            tables_to_create.append(model.__tablename__)

    if tables_to_create:
        print("Creating tables:", ', '.join(tables_to_create))
        Base.metadata.create_all(bind=engine, tables=[m.__table__ for m in new_models])
        print("Tables created")
    else:
        print("All tables exist")

    # 2. add display_id column
    cols = [c['name'] for c in inspector.get_columns('requirements')]
    if 'display_id' not in cols:
        print("Adding display_id column...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE requirements ADD COLUMN display_id VARCHAR(50)"))
            conn.commit()
        print("display_id column added")

        # assign display_ids
        db = SessionLocal()
        try:
            reqs = db.query(Requirement).all()
            for req in reqs:
                proj = db.query(Project).filter(Project.id == req.project_id).first()
                if proj:
                    req.display_id = generate_requirement_display_id(db, proj)
                    db.commit()
            print(f"Assigned display_id to {len(reqs)} requirements")
        finally:
            db.close()

    # 3. seed default status and priority pools for existing projects
    db = SessionLocal()
    try:
        projects = db.query(Project).all()
        for proj in projects:
            # seed status pools
            existing_statuses = db.query(RequirementStatusPool).filter(
                RequirementStatusPool.project_id == proj.id
            ).count()
            if existing_statuses == 0:
                default_statuses = [
                    ("待处理", "#e6a23c", 0, True),
                    ("进行中", "#409eff", 1, False),
                    ("已完成", "#67c23a", 2, False),
                    ("已取消", "#909399", 3, False),
                ]
                for name, color, sort, is_def in default_statuses:
                    db.add(RequirementStatusPool(
                        project_id=proj.id, name=name, color=color, sort_order=sort, is_default=is_def
                    ))
                print(f"Seeded {len(default_statuses)} statuses for project {proj.display_id or proj.id}")

            # seed priority pools
            existing_priorities = db.query(RequirementPriorityPool).filter(
                RequirementPriorityPool.project_id == proj.id
            ).count()
            if existing_priorities == 0:
                default_priorities = [
                    ("低", "#909399", 0, False),
                    ("普通", "#67c23a", 1, True),
                    ("高", "#e6a23c", 2, False),
                    ("紧急", "#e53e3e", 3, False),
                ]
                for name, color, sort, is_def in default_priorities:
                    db.add(RequirementPriorityPool(
                        project_id=proj.id, name=name, color=color, sort_order=sort, is_default=is_def
                    ))
                print(f"Seeded {len(default_priorities)} priorities for project {proj.display_id or proj.id}")

        db.commit()
    finally:
        db.close()

    print("Migration complete")

if __name__ == "__main__":
    migrate()
