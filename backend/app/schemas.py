from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date


# ---- Project ----
class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    start_date: Optional[date] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None

class ProjectOut(BaseModel):
    id: int
    name: str
    description: str
    start_date: Optional[date]
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True


# ---- StatusPool ----
class StatusPoolCreate(BaseModel):
    name: str
    color: str = "#5F5E5A"
    sort_order: int = 0
    is_default: bool = False

class StatusPoolUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None
    is_default: Optional[bool] = None

class StatusPoolOut(BaseModel):
    id: int
    project_id: int
    name: str
    color: str
    sort_order: int
    is_default: bool
    class Config:
        from_attributes = True


# ---- CommTypePool ----
class CommTypePoolCreate(BaseModel):
    name: str
    color: str = "#5F5E5A"
    sort_order: int = 0
    is_default: bool = False

class CommTypePoolUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None
    is_default: Optional[bool] = None

class CommTypePoolOut(BaseModel):
    id: int
    project_id: int
    name: str
    color: str
    sort_order: int
    is_default: bool
    class Config:
        from_attributes = True


# ---- Contact ----
class ContactCreate(BaseModel):
    name: str
    role: str = ""
    contact_info: str = ""

class ContactUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    contact_info: Optional[str] = None

class ContactOut(BaseModel):
    id: int
    task_id: int
    name: str
    role: str
    contact_info: str
    created_at: datetime
    class Config:
        from_attributes = True


# ---- ProjectContact ----
class ProjectContactCreate(BaseModel):
    name: str
    role: str = ""
    contact_info: str = ""

class ProjectContactUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    contact_info: Optional[str] = None

class ProjectContactOut(BaseModel):
    id: int
    project_id: int
    name: str
    role: str
    contact_info: str
    created_at: datetime
    class Config:
        from_attributes = True


# ---- Attachment ----
class AttachmentUpdate(BaseModel):
    original_filename: str

class AttachmentOut(BaseModel):
    id: int
    comm_id: int
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    uploaded_at: datetime
    class Config:
        from_attributes = True


# ---- Communication ----
class CommunicationCreate(BaseModel):
    content: str
    contact_ids: List[int] = []
    comm_at: Optional[datetime] = None
    comm_type: str = "note"
    old_status_id: Optional[int] = None
    new_status_id: Optional[int] = None

class CommunicationUpdate(BaseModel):
    content: Optional[str] = None
    contact_ids: Optional[List[int]] = None
    comm_at: Optional[datetime] = None
    comm_type: Optional[str] = None
    old_status_id: Optional[int] = None
    new_status_id: Optional[int] = None

class ContactBrief(BaseModel):
    id: int
    name: str
    role: str
    class Config:
        from_attributes = True

class CommunicationOut(BaseModel):
    id: int
    task_id: int
    contact_id: Optional[int]
    old_status_id: Optional[int] = None
    new_status_id: Optional[int] = None
    content: str
    comm_at: datetime
    comm_type: str
    created_at: datetime
    attachments: List[AttachmentOut] = []
    contact: Optional[ContactBrief] = None
    contacts: List[ContactBrief] = []
    class Config:
        from_attributes = True


# ---- TagPool ----
class TagPoolCreate(BaseModel):
    name: str
    color: str = "#5F5E5A"
    sort_order: int = 0

class TagPoolUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None

class TagPoolOut(BaseModel):
    id: int
    project_id: int
    name: str
    color: str
    sort_order: int
    class Config:
        from_attributes = True

class TagBrief(BaseModel):
    id: int
    name: str
    color: str
    class Config:
        from_attributes = True


# ---- Task ----
class TaskCreate(BaseModel):
    title: str
    description: str = ""
    status_id: Optional[int] = None
    priority: str = "normal"
    due_date: Optional[date] = None
    tag_ids: List[int] = []

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status_id: Optional[int] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    tag_ids: Optional[List[int]] = None

class TaskOut(BaseModel):
    id: int
    project_id: int
    title: str
    description: str
    priority: str
    due_date: Optional[date]
    status_id: Optional[int]
    last_comm_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    contacts: List[ContactOut] = []
    tags: List[TagBrief] = []
    class Config:
        from_attributes = True

class TaskDetail(TaskOut):
    communications: List[CommunicationOut] = []
    class Config:
        from_attributes = True


# ---- Checkin ----
class BatchDeleteIds(BaseModel):
    ids: List[int]

class CheckinCreate(BaseModel):
    project_ids: List[int] = []
    task_ids: List[int] = []
    multi_project: bool = False
    date: Optional[str] = None  # "YYYY-MM-DD" 字符串
    content: str = ""

class ProjectBrief(BaseModel):
    id: int
    name: str
    class Config:
        from_attributes = True

class TaskBrief(BaseModel):
    id: int
    title: str
    class Config:
        from_attributes = True

class CheckinOut(BaseModel):
    id: int
    date: date
    content: str
    multi_project: bool
    created_at: datetime
    projects: List[ProjectBrief] = []
    tasks: List[TaskBrief] = []
    class Config:
        from_attributes = True
