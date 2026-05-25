from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Date, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

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


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    start_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    status_pools = relationship("StatusPool", back_populates="project", cascade="all, delete-orphan")
    comm_type_pools = relationship("CommTypePool", back_populates="project", cascade="all, delete-orphan")
    project_contacts = relationship("ProjectContact", back_populates="project", cascade="all, delete-orphan")


class StatusPool(Base):
    __tablename__ = "status_pools"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(20), default="#5F5E5A")
    sort_order = Column(Integer, default=0)
    is_default = Column(Boolean, default=False)

    project = relationship("Project", back_populates="status_pools")
    tasks = relationship("Task", back_populates="status")


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    status_id = Column(Integer, ForeignKey("status_pools.id"), nullable=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, default="")
    priority = Column(String(20), default="normal")  # low/normal/high/urgent
    due_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="tasks")
    status = relationship("StatusPool", back_populates="tasks")
    contacts = relationship("Contact", back_populates="task", cascade="all, delete-orphan")
    communications = relationship("Communication", back_populates="task", cascade="all, delete-orphan", order_by="Communication.comm_at")


class ProjectContact(Base):
    __tablename__ = "project_contacts"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(String(100), default="")
    contact_info = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

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
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)

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
