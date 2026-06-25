"""
迁移脚本：为 requirement_custom_fields 表添加 is_builtin 列，
并为每个已有项目插入内置字段记录（标题、状态、优先级）。
"""
import sys
import os

# 确保能找到 app 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, SessionLocal
from app.database import Project, RequirementCustomField
from sqlalchemy import inspect, text

BUILTIN_FIELDS = [
    {"field_name": "标题", "field_type": "text", "field_options": "", "sort_order": 0, "is_builtin": True},
    {"field_name": "状态", "field_type": "dropdown", "field_options": "待处理\n进行中\n已完成\n已取消", "sort_order": 1, "is_builtin": True},
    {"field_name": "优先级", "field_type": "dropdown", "field_options": "低\n普通\n高\n紧急", "sort_order": 2, "is_builtin": True},
    {"field_name": "创建时间", "field_type": "datetime", "field_options": "", "sort_order": 3, "is_builtin": True},
    {"field_name": "更新时间", "field_type": "datetime", "field_options": "", "sort_order": 4, "is_builtin": True},
]


def main():
    db = SessionLocal()
    try:
        # 1. 检查列是否已存在
        inspector = inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("requirement_custom_fields")]
        if "is_builtin" not in columns:
            print("添加 is_builtin 列...")
            with engine.connect() as conn:
                conn.execute(text(
                    "ALTER TABLE requirement_custom_fields ADD COLUMN is_builtin BOOLEAN DEFAULT 0"
                ))
                conn.commit()
            print("列添加完成")
        else:
            print("is_builtin 列已存在，跳过")

        # 2. 为每个项目插入内置字段（如果尚未存在）
        projects = db.query(Project).all()
        for proj in projects:
            existing = {
                f.field_name
                for f in db.query(RequirementCustomField).filter(
                    RequirementCustomField.project_id == proj.id,
                    RequirementCustomField.is_builtin == True,
                ).all()
            }

            # 检查是否有旧的 JSON 配置（内置字段已停用状态的迁移）
            old_inactive = set()
            for bf in BUILTIN_FIELDS:
                if bf["field_name"] in existing:
                    print(f"  项目 {proj.display_id}：{bf['field_name']} 已存在，跳过")
                    continue
                # 查看是否有同名非内置字段（旧自定义字段），不要冲突
                conflict = db.query(RequirementCustomField).filter(
                    RequirementCustomField.project_id == proj.id,
                    RequirementCustomField.field_name == bf["field_name"],
                    RequirementCustomField.is_builtin == False,
                ).first()
                if conflict:
                    # 将旧自定义字段标记为内置
                    conflict.is_builtin = True
                    conflict.sort_order = bf["sort_order"]
                    conflict.field_type = bf["field_type"]
                    conflict.field_options = bf["field_options"]
                    print(f"  项目 {proj.display_id}：将已有字段「{bf['field_name']}」标记为内置")
                else:
                    field = RequirementCustomField(
                        project_id=proj.id,
                        field_name=bf["field_name"],
                        field_type=bf["field_type"],
                        field_options=bf["field_options"],
                        sort_order=bf["sort_order"],
                        is_active=True,
                        is_builtin=True,
                    )
                    db.add(field)
                    print(f"  项目 {proj.display_id}：插入内置字段「{bf['field_name']}」")

        db.commit()
        print("\n迁移完成！")

        # 3. 清理旧的 JSON 配置文件（如果存在）
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
        cleaned = 0
        for root, dirs, files in os.walk(config_dir):
            for f in files:
                if f == "builtin_fields.json":
                    path = os.path.join(root, f)
                    os.remove(path)
                    print(f"  清理旧配置：{path}")
                    cleaned += 1
        if cleaned:
            print(f"已清理 {cleaned} 个旧的 builtin_fields.json 文件")
        else:
            print("未发现旧的 builtin_fields.json 文件")

    except Exception as e:
        print(f"错误：{e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
