from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Date, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os, random, string

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "taskm.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_DIR, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def touch_project(db, project_id):
    """项目内部有任何变动时，同步更新项目的 updated_at 时间戳"""
    from datetime import datetime
    db.query(Project).filter(Project.id == project_id).update(
        {"updated_at": datetime.now()},
        synchronize_session=False
    )
    db.commit()


def derive_task_status(db, task_id):
    """
    从沟通记录推导任务的最终状态。
    逻辑：遍历所有沟通记录，找到最后一条有 new_status_id 的记录，
    该记录的 new_status_id 即为任务当前状态。
    如果没有任何状态变更记录，返回 None。
    """
    last_comm = db.query(Communication.new_status_id).filter(
        Communication.task_id == task_id,
        Communication.new_status_id.isnot(None)
    ).order_by(Communication.id.desc()).first()
    return last_comm[0] if last_comm else None


def sync_task_status(db, task_id):
    """
    根据沟通记录推导出正确的 status_id，写回 Task 表并 commit。
    如果没有沟通记录涉及状态变更，保留现有 status_id 不变。
    返回最终的 status_id。
    """
    derived = derive_task_status(db, task_id)
    if derived is not None:
        db.query(Task).filter(Task.id == task_id).update(
            {"status_id": derived},
            synchronize_session=False
        )
        db.commit()
        return derived
    # 无状态变更记录 → 保留现有 status_id 不变
    task = db.query(Task.status_id).filter(Task.id == task_id).first()
    return task[0] if task else None


def cleanup_comm_files(project_display_id, task_display_id, comm_id):
    """删除指定沟通记录的附件目录及所有文件"""
    import shutil
    dir_path = os.path.join(UPLOAD_DIR, project_display_id, task_display_id, f"comm_{comm_id}")
    if os.path.isdir(dir_path):
        shutil.rmtree(dir_path)


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    display_id = Column(String(50), unique=True, nullable=True)
    custom_prefix = Column(String(3), nullable=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    start_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    status_pools = relationship("StatusPool", back_populates="project", cascade="all, delete-orphan")
    comm_type_pools = relationship("CommTypePool", back_populates="project", cascade="all, delete-orphan")
    project_contacts = relationship("ProjectContact", back_populates="project", cascade="all, delete-orphan")
    tag_pools = relationship("TagPool", back_populates="project", cascade="all, delete-orphan")


class StatusPool(Base):
    __tablename__ = "status_pools"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(20), default="#5F5E5A")
    sort_order = Column(Integer, default=0)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    project = relationship("Project", back_populates="status_pools")
    tasks = relationship("Task", back_populates="status")


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    display_id = Column(String(50), unique=True, nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    status_id = Column(Integer, ForeignKey("status_pools.id"), nullable=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, default="")
    priority = Column(String(20), default="normal")  # low/normal/high/urgent
    due_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    project = relationship("Project", back_populates="tasks")
    status = relationship("StatusPool", back_populates="tasks")
    contacts = relationship("Contact", back_populates="task", cascade="all, delete-orphan")
    communications = relationship("Communication", back_populates="task", cascade="all, delete-orphan", order_by="Communication.comm_at")
    tags = relationship("TagPool", secondary="task_tags", back_populates="tasks", passive_deletes=True)


class ProjectContact(Base):
    __tablename__ = "project_contacts"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(String(100), default="")
    contact_info = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    project = relationship("Project")


class Contact(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    project_contact_id = Column(Integer, ForeignKey("project_contacts.id"), nullable=True)
    name = Column(String(100), nullable=False)
    role = Column(String(100), default="")
    contact_info = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="contacts")
    project_contact = relationship("ProjectContact")


class Communication(Base):
    __tablename__ = "communications"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    old_status_id = Column(Integer, ForeignKey("status_pools.id"), nullable=True)
    new_status_id = Column(Integer, ForeignKey("status_pools.id"), nullable=True)
    content = Column(Text, nullable=False)
    comm_at = Column(DateTime, default=datetime.utcnow)
    comm_type = Column(String(50), default="note")  # note/meeting/email/call
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="communications")
    contact = relationship("Contact", foreign_keys=[contact_id])
    communication_contacts = relationship("CommunicationContact", back_populates="communication", cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="communication", cascade="all, delete-orphan")

    @property
    def contacts(self):
        return [cc.contact for cc in self.communication_contacts]


class CommunicationContact(Base):
    """沟通记录与对接人的关联表（多对多）"""
    __tablename__ = "communication_contacts"
    id = Column(Integer, primary_key=True, index=True)
    communication_id = Column(Integer, ForeignKey("communications.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)

    communication = relationship("Communication", back_populates="communication_contacts")
    contact = relationship("Contact")


class Attachment(Base):
    __tablename__ = "attachments"
    id = Column(Integer, primary_key=True, index=True)
    comm_id = Column(Integer, ForeignKey("communications.id"), nullable=False)
    filename = Column(String(300), nullable=False)
    original_filename = Column(String(300), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)
    mime_type = Column(String(100), default="")
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    communication = relationship("Communication", back_populates="attachments")


class CommTypePool(Base):
    __tablename__ = "comm_type_pools"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(20), default="#5F5E5A")
    sort_order = Column(Integer, default=0)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    project = relationship("Project", back_populates="comm_type_pools")


class Checkin(Base):
    __tablename__ = "checkins"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    content = Column(Text, default="")
    multi_project = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    projects = relationship("Project", secondary="checkin_projects", backref="checkins_ref")
    tasks = relationship("Task", secondary="checkin_tasks", backref="checkins_ref")


class CheckinProject(Base):
    __tablename__ = "checkin_projects"
    checkin_id = Column(Integer, ForeignKey("checkins.id", ondelete="CASCADE"), primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), primary_key=True)


class CheckinTask(Base):
    __tablename__ = "checkin_tasks"
    checkin_id = Column(Integer, ForeignKey("checkins.id", ondelete="CASCADE"), primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), primary_key=True)


class TagPool(Base):
    """标签池 —— 项目级别的标签定义"""
    __tablename__ = "tag_pools"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(20), default="#5F5E5A")
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    project = relationship("Project", back_populates="tag_pools")
    tasks = relationship("Task", secondary="task_tags", back_populates="tags", passive_deletes=True)


class TaskTag(Base):
    """任务与标签的多对多关联表"""
    __tablename__ = "task_tags"
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tag_pools.id", ondelete="CASCADE"), primary_key=True)


# ---- 显示ID生成工具函数 ----

def _random_prefix() -> str:
    """生成随机的3个大写字母前缀"""
    return ''.join(random.choices(string.ascii_uppercase, k=3))


def generate_project_display_id(db, prefix: str) -> tuple:
    """生成项目显示ID，返回 (display_id, sequence_number)"""
    today = datetime.now().strftime("%Y%m%d")
    # 查询当天同前缀的最大序号
    last = db.query(Project.display_id).filter(
        Project.display_id.like(f"P{prefix}{today}%")
    ).order_by(Project.display_id.desc()).first()
    seq = (int(last[0][-2:]) + 1) if last and last[0][-2:].isdigit() else 1
    seq_str = f"{seq:02d}"
    return f"P{prefix}{today}{seq_str}", seq


def generate_task_display_id(db, project) -> str:
    """生成任务显示ID 格式: T + 项目ID(不含P) + "-" + 4位序号"""
    proj_id_no_p = project.display_id[1:] if project.display_id and project.display_id.startswith("P") else str(project.id)
    # 查询同一项目下最大序号
    last = db.query(Task.display_id).filter(
        Task.display_id.like(f"T{proj_id_no_p}-%")
    ).order_by(Task.display_id.desc()).first()
    seq = (int(last[0][-4:]) + 1) if last and last[0][-4:].isdigit() else 1
    seq_str = f"{seq:04d}"
    return f"T{proj_id_no_p}-{seq_str}"


# ---- 显示ID查找工具函数 ----

def resolve_project(db, project_display_id: str):
    """根据显示ID查找项目，未找到抛出404"""
    from fastapi import HTTPException
    proj = db.query(Project).filter(Project.display_id == project_display_id).first()
    if not proj:
        raise HTTPException(404, "项目不存在")
    return proj


def resolve_task(db, project_pk: int, task_display_id: str):
    """根据显示ID查找任务，未找到抛出404"""
    from fastapi import HTTPException
    task = db.query(Task).filter(Task.display_id == task_display_id, Task.project_id == project_pk).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    return task
