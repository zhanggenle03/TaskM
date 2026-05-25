"""
数据迁移脚本：将任务级别对接人迁移到项目级别对接人库
"""
from app.database import engine, SessionLocal, ProjectContact, Contact, Task
from sqlalchemy import text, inspect

def migrate_project_contacts():
    """
    迁移步骤：
    1. 创建 project_contacts 表（如果不存在）
    2. 遍历所有任务级别对接人，去重后添加到 project_contacts
    3. 更新 contacts 表的 project_contact_id 字段
    """
    db = SessionLocal()
    try:
        inspector = inspect(engine)
        
        # 1. 检查 project_contacts 表是否存在
        if not inspector.has_table("project_contacts"):
            print("创建 project_contacts 表...")
            ProjectContact.__table__.create(engine)
            print("✓ project_contacts 表创建成功")
        
        # 2. 检查 contacts 表是否有 project_contact_id 列
        columns = [col['name'] for col in inspector.get_columns('contacts')]
        if 'project_contact_id' not in columns:
            print("添加 project_contact_id 列到 contacts 表...")
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE contacts ADD COLUMN project_contact_id INTEGER REFERENCES project_contacts(id)"))

                # 同时添加 project_id 列到 contacts 表（用于数据迁移查找 project_id）
                if 'project_id' not in columns:
                    conn.execute(text("ALTER TABLE contacts ADD COLUMN project_id INTEGER REFERENCES projects(id)"))
                conn.commit()
            print("✓ 列添加成功")
        
        # 3. 填充 contacts 表的 project_id（通过 task_id 关联）
        print("填充 contacts 表的 project_id...")
        db.execute(text("""
            UPDATE contacts 
            SET project_id = (SELECT project_id FROM tasks WHERE tasks.id = contacts.task_id)
            WHERE project_id IS NULL
        """))
        db.commit()
        print("✓ project_id 填充完成")
        
        # 4. 去重并添加对接人到 project_contacts
        print("迁移对接人到项目级别库...")
        # 获取所有需要迁移的对接人（按 project_id + name 去重）
        existing_contacts = db.execute(text("""
            SELECT DISTINCT project_id, name, role, contact_info
            FROM contacts
            WHERE project_id IS NOT NULL
        """)).fetchall()
        
        for row in existing_contacts:
            project_id, name, role, contact_info = row
            # 检查是否已存在
            exists = db.query(ProjectContact).filter_by(
                project_id=project_id,
                name=name
            ).first()
            if not exists:
                pc = ProjectContact(
                    project_id=project_id,
                    name=name,
                    role=role or "",
                    contact_info=contact_info or ""
                )
                db.add(pc)
        
        db.commit()
        print(f"✓ 添加了 {len(existing_contacts)} 个对接人到项目库")
        
        # 5. 更新 contacts 表的 project_contact_id
        print("更新 contacts 表的 project_contact_id...")
        
        # 使用 SQL 直接更新，而不是 ORM
        with engine.connect() as conn:
            # 获取所有 project_contacts
            project_contacts = conn.execute(text("""
                SELECT id, project_id, name FROM project_contacts
            """)).fetchall()
            
            for pc in project_contacts:
                pc_id, pc_project_id, pc_name = pc
                # 更新对应的 contacts
                conn.execute(text("""
                    UPDATE contacts 
                    SET project_contact_id = :pc_id
                    WHERE project_id = :project_id AND name = :name AND project_contact_id IS NULL
                """), {"pc_id": pc_id, "project_id": pc_project_id, "name": pc_name})
            
            conn.commit()
        
        print("✓ project_contact_id 更新完成")
        
        print("\n✅ 数据迁移完成！")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 迁移失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate_project_contacts()
