"""迁移脚本：创建 task_requirements 关联表（任务与需求的多对多）"""
import sys
import os

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, Base
from sqlalchemy import Table, Column, Integer, ForeignKey, MetaData

def migrate():
    """检查并创建 task_requirements 表"""
    meta = MetaData()
    meta.reflect(bind=engine)
    
    if "task_requirements" not in meta.tables:
        print("正在创建 task_requirements 表...")
        # 使用 Base.metadata 创建（TaskRequirement 模型已定义在 database.py 中）
        TaskRequirement = Table(
            "task_requirements", meta,
            Column("task_id", Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
            Column("requirement_id", Integer, ForeignKey("requirements.id", ondelete="CASCADE"), primary_key=True),
            extend_existing=True
        )
        TaskRequirement.create(bind=engine)
        print("task_requirements 表创建成功！")
    else:
        print("task_requirements 表已存在，跳过创建。")

if __name__ == "__main__":
    migrate()
