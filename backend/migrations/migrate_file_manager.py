"""
迁移脚本：任务文件管理（2026-08-27）
- 新建 file_folders 表：任务文件管理的文件夹（无限层级，parent_id 自引用）
- 新建 communication_files 表：沟通记录引用文件管理文件的关联（多对多）
- 重建 attachments 表：comm_id 改为可空（独立上传为 NULL），新增 task_id / folder_id 列
- 回填 attachments.task_id：旧数据按 comm → task 链路补齐

数据安全：
- 重建表采用 SQLite 标准流程（新表→拷贝→校验行数→删旧表→改名），行数不一致则中止
- 全程幂等：已迁移（存在 task_id 列）自动跳过
- 支持 TASKM_MIGRATE_DB 环境变量指向测试库，默认使用应用真实库
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, inspect, text

_DB_OVERRIDE = os.environ.get("TASKM_MIGRATE_DB", "")
if _DB_OVERRIDE:
    engine = create_engine(f"sqlite:///{_DB_OVERRIDE}", connect_args={"check_same_thread": False})
else:
    # 指向 backend/ 目录（app 包所在位置）
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.database import engine

FILE_FOLDERS_SQL = """CREATE TABLE IF NOT EXISTS file_folders (
    id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    parent_id INTEGER,
    name VARCHAR(200) NOT NULL,
    created_at DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(task_id) REFERENCES tasks (id),
    FOREIGN KEY(parent_id) REFERENCES file_folders (id)
)"""

COMM_FILES_SQL = """CREATE TABLE IF NOT EXISTS communication_files (
    id INTEGER NOT NULL,
    communication_id INTEGER NOT NULL,
    attachment_id INTEGER NOT NULL,
    created_at DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(communication_id) REFERENCES communications (id) ON DELETE CASCADE,
    FOREIGN KEY(attachment_id) REFERENCES attachments (id) ON DELETE CASCADE
)"""

ATTACHMENTS_NEW_SQL = """CREATE TABLE attachments_new (
    id INTEGER NOT NULL,
    comm_id INTEGER,
    task_id INTEGER,
    folder_id INTEGER,
    filename VARCHAR(300) NOT NULL,
    original_filename VARCHAR(300) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER,
    mime_type VARCHAR(100),
    uploaded_at DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(comm_id) REFERENCES communications (id),
    FOREIGN KEY(task_id) REFERENCES tasks (id),
    FOREIGN KEY(folder_id) REFERENCES file_folders (id)
)"""


def main():
    inspector = inspect(engine)
    with engine.connect() as conn:
        # 1. 新建表（幂等）
        if "file_folders" not in inspector.get_table_names():
            conn.execute(text(FILE_FOLDERS_SQL))
            conn.commit()
            print("已创建 file_folders 表")
        else:
            print("file_folders 表已存在，跳过")

        if "communication_files" not in inspector.get_table_names():
            conn.execute(text(COMM_FILES_SQL))
            conn.commit()
            print("已创建 communication_files 表")
        else:
            print("communication_files 表已存在，跳过")

        # 2. 重建 attachments（comm_id 可空 + task_id/folder_id），仅当未迁移过
        att_cols = [c["name"] for c in inspector.get_columns("attachments")]
        if "task_id" not in att_cols:
            old_count = conn.execute(text("SELECT COUNT(*) FROM attachments")).scalar()
            print(f"重建 attachments 表（当前 {old_count} 行）...")
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            conn.execute(text("DROP TABLE IF EXISTS attachments_new"))
            conn.execute(text(ATTACHMENTS_NEW_SQL))
            conn.execute(text(
                "INSERT INTO attachments_new (id, comm_id, filename, original_filename, file_path, file_size, mime_type, uploaded_at) "
                "SELECT id, comm_id, filename, original_filename, file_path, file_size, mime_type, uploaded_at FROM attachments"
            ))
            conn.execute(text("DROP TABLE attachments"))
            conn.execute(text("ALTER TABLE attachments_new RENAME TO attachments"))
            # 重建主键索引（SQLAlchemy 对 Integer PK 自动生成的索引，须随表重建）
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_attachments_id ON attachments (id)"))
            conn.commit()
            new_count = conn.execute(text("SELECT COUNT(*) FROM attachments")).scalar()
            if new_count != old_count:
                print(f"!! 行数校验失败：{old_count} -> {new_count}，已中止（请用备份恢复）")
                sys.exit(1)
            print(f"attachments 重建完成，行数 {new_count}（校验一致）")
        else:
            print("attachments 已含 task_id，跳过重建")

        # 3. 回填 task_id（沟通上传附件按 comm → task 链路补齐）
        conn.execute(text(
            "UPDATE attachments SET task_id = ("
            "  SELECT c.task_id FROM communications c WHERE c.id = attachments.comm_id"
            ") WHERE task_id IS NULL AND comm_id IS NOT NULL"
        ))
        conn.commit()
        missing = conn.execute(text(
            "SELECT COUNT(*) FROM attachments WHERE task_id IS NULL AND comm_id IS NOT NULL"
        )).scalar()
        orphan = conn.execute(text(
            "SELECT COUNT(*) FROM attachments WHERE task_id IS NULL AND comm_id IS NULL"
        )).scalar()
        print(f"task_id 回填完成；缺 task_id 的沟通附件 {missing} 条，独立文件（comm_id 空）{orphan} 条")

    print("\n文件管理迁移完成！")


if __name__ == "__main__":
    main()
