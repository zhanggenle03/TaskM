from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date


# ---- Project ----
class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    start_date: Optional[date] = None
    custom_prefix: Optional[str] = None  # 3字母前缀，创建后不可更改

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None

class ProjectOut(BaseModel):
    id: int
    display_id: Optional[str]
    custom_prefix: Optional[str]
    name: str
    description: str
    start_date: Optional[date]
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True


# ---- HolidayOverride ----
class HolidayOverrideSet(BaseModel):
    date: str  # "YYYY-MM-DD"
    override_type: Optional[str] = None  # 'holiday'|'workday'|'normal'|'off' — None 表示清除
    remark: str = ""

class HolidayOverrideOut(BaseModel):
    date: date
    override_type: str
    remark: str
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
    is_active: bool = True
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
    is_active: bool = True
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
    is_active: bool = True
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
    is_active: bool = True
    class Config:
        from_attributes = True

class TagBrief(BaseModel):
    id: int
    name: str
    color: str
    class Config:
        from_attributes = True


class RequirementBrief(BaseModel):
    id: int
    display_id: Optional[str] = None
    title: str
    priority: str
    status: str
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
    display_id: Optional[str]
    project_id: int
    title: str
    description: str
    priority: str
    due_date: Optional[date]
    status_id: Optional[int]
    last_comm_at: Optional[datetime] = None
    last_comm_contact_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    contacts: List[ContactOut] = []
    tags: List[TagBrief] = []
    class Config:
        from_attributes = True

class TaskDetail(TaskOut):
    communications: List[CommunicationOut] = []
    linked_requirements: List[RequirementBrief] = []
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
    display_id: Optional[str]
    name: str
    class Config:
        from_attributes = True

class TaskBrief(BaseModel):
    id: int
    display_id: Optional[str]
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


# ---- Requirement ----
class RequirementCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    priority: str = "normal"
    status: str = "todo"
    custom_values: Optional[dict] = {}  # {field_id: value}

class RequirementUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    custom_values: Optional[dict] = None

class RequirementCustomValueOut(BaseModel):
    field_id: int
    field_name: str
    field_type: str
    value: str
    class Config:
        from_attributes = True

class RequirementOut(BaseModel):
    id: int
    project_id: int
    display_id: Optional[str] = None
    title: str
    description: Optional[str] = ""
    priority: str
    status: str
    created_at: datetime
    updated_at: datetime
    custom_values: List[RequirementCustomValueOut] = []
    class Config:
        from_attributes = True

class RequirementListResponse(BaseModel):
    items: List[RequirementOut]
    total: int


# ---- Requirement Custom Field ----
class RequirementCustomFieldCreate(BaseModel):
    field_name: str
    field_type: str  # text/dropdown/multi_dropdown/datetime/date/number
    field_options: str = ""  # JSON for dropdown
    sort_order: int = 0

class RequirementCustomFieldUpdate(BaseModel):
    field_name: Optional[str] = None
    field_type: Optional[str] = None
    field_options: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None

class RequirementCustomFieldOut(BaseModel):
    id: int
    project_id: int
    field_name: str
    field_type: str
    field_options: str
    sort_order: int
    is_active: bool = True
    is_builtin: bool = False
    created_at: datetime
    class Config:
        from_attributes = True


# ---- Kanban ----
class KanbanTaskSimple(BaseModel):
    id: int
    display_id: Optional[str]
    title: str
    priority: str
    due_date: Optional[date]
    contact_names: str = ""
    status_duration_hours: float = 0
    status_duration_text: str = ""

class KanbanColumn(BaseModel):
    status_id: int
    status_name: str
    color: str
    tasks: List[KanbanTaskSimple] = []

class KanbanData(BaseModel):
    columns: List[KanbanColumn] = []


# ---- Dashboard ----
class StatusDistribution(BaseModel):
    name: str
    value: int

class PriorityDistribution(BaseModel):
    name: str
    value: int

class TrendPoint(BaseModel):
    date: str
    count: int

class ProjectProgress(BaseModel):
    name: str
    value: int
    color: str

class DashboardData(BaseModel):
    status_distribution: List[StatusDistribution] = []
    priority_distribution: List[PriorityDistribution] = []
    project_progress: List[ProjectProgress] = []
    trend: List[TrendPoint] = []


# ---- Requirement Status Pool ----
class RequirementStatusPoolCreate(BaseModel):
    name: str
    color: str = "#5F5E5A"
    sort_order: int = 0
    is_default: bool = False

class RequirementStatusPoolUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None
    is_default: Optional[bool] = None

class RequirementStatusPoolOut(BaseModel):
    id: int
    project_id: int
    name: str
    color: str
    sort_order: int
    is_default: bool = False
    is_active: bool = True
    class Config:
        from_attributes = True


# ---- Requirement Priority Pool ----
class RequirementPriorityPoolCreate(BaseModel):
    name: str
    color: str = "#5F5E5A"
    sort_order: int = 0
    is_default: bool = False

class RequirementPriorityPoolUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None
    is_default: Optional[bool] = None

class RequirementPriorityPoolOut(BaseModel):
    id: int
    project_id: int
    name: str
    color: str
    sort_order: int
    is_default: bool = False
    is_active: bool = True
    class Config:
        from_attributes = True
