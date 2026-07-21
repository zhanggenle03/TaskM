from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, date


# ---- Project ----
class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    start_date: Optional[date] = None
    custom_prefix: Optional[str] = None  # 3字母前缀，创建后不可更改
    category: str = ""  # 书签分类 key，空串表示未分类

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    pinned: Optional[bool] = None
    category: Optional[str] = None  # 书签分类 key

class ProjectOut(BaseModel):
    id: int
    display_id: Optional[str]
    custom_prefix: Optional[str]
    name: str
    description: str
    start_date: Optional[date]
    created_at: datetime
    updated_at: datetime
    pinned: bool = False
    category: str = ""
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
    man_days: float = 1.0      # 当天人天（合计），默认 1.0，加班/并行等可 >1
    man_day_reason: str = ""   # 人天说明（自由文本）
    # 多项目时各项目分配的人天：{project_id: man_days}，合计应等于当天 man_days
    project_man_days: Dict[int, float] = {}

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
    man_days: float = 1.0
    man_day_reason: str = ""
    created_at: datetime
    projects: List[ProjectBrief] = []
    tasks: List[TaskBrief] = []
    project_man_days: Dict[int, float] = {}  # 各项目分配的人天
    class Config:
        from_attributes = True

# ---- Salary ----
# 明细行 category 取值：income 收入 / deduction 五险一金个人及扣款 / tax 个税 / company_cost 公司承担
VALID_SALARY_CATEGORIES = ["income", "deduction", "tax", "company_cost"]

class SalaryItemCreate(BaseModel):
    category: str                                   # income/deduction/tax/company_cost
    name: str                                        # 如「基本工资」「养老保险(个人)」
    amount: float = 0.0
    base: Optional[float] = None                    # 缴费基数（基数×比例自动算时用）
    rate: Optional[float] = None                    # 比例（百分比，如 8 表示 8%）
    funded_by: str = ""                             # personal/company/空
    sort_order: int = 0

class SalaryItemOut(BaseModel):
    id: int
    category: str
    name: str
    amount: float
    base: Optional[float] = None
    rate: Optional[float] = None
    funded_by: str = ""
    sort_order: int = 0
    class Config:
        from_attributes = True

class SalaryRecordCreate(BaseModel):
    period: str                                      # "YYYY-MM"
    pay_date: Optional[str] = None                  # "YYYY-MM-DD"
    employer: str = ""
    credited_amount: Optional[float] = None          # 实际到账（入卡金额）
    actual_tax: Optional[float] = None               # 实际个税
    remark: str = ""
    items: List[SalaryItemCreate] = []

class SalaryRecordOut(BaseModel):
    id: int
    period: str
    pay_date: Optional[date] = None
    employer: str = ""
    credited_amount: Optional[float] = None          # 实际到账（入卡金额）
    actual_tax: Optional[float] = None               # 实际个税
    remark: str = ""
    created_at: datetime
    updated_at: datetime
    items: List[SalaryItemOut] = []
    # 汇总（后端计算，不冗余存储）
    gross: float = 0.0                              # 应发合计 = Σ income
    personal_deduction: float = 0.0                 # 个人扣除 = Σ deduction + Σ tax
    net: float = 0.0                                # 实发 = gross - personal_deduction
    company_cost: float = 0.0                       # 公司承担合计 = Σ company_cost
    class Config:
        from_attributes = True

class SalarySummaryOut(BaseModel):
    period_from: Optional[str] = None               # YYYY-MM
    period_to: Optional[str] = None                 # YYYY-MM
    record_count: int
    total_gross: float = 0.0
    total_personal_deduction: float = 0.0
    total_net: float = 0.0
    total_company_cost: float = 0.0
    avg_net: float = 0.0                            # 月均实发
    total_credited: float = 0.0                     # 到账合计
    total_actual_tax: float = 0.0                   # 实际个税合计

# ── 薪资通用配置（存于 settings.json 的 salary_config，非独立表）──
class SalaryConfigOut(BaseModel):
    employer: str = ""                               # 默认单位名称
    social_bases: dict = {}                           # 各项缴费基数（通用稳定），key 为险种名；各项最低基数不同，故分项配置
    social_rates: dict = {}                           # 各险种比例（百分比，如 8=8%），key 为险种名
    default_pay_month: str = "current"                # 默认发放月份：current=当月 / next=次月
    default_pay_day: int = 10                         # 默认发放日（1~31）
    default_income_items: List[dict] = []             # 默认收入项模板 [{name, amount}]
    class Config:
        from_attributes = True

class SalaryConfigUpdate(BaseModel):
    employer: Optional[str] = None
    social_bases: Optional[dict] = None
    social_rates: Optional[dict] = None
    default_pay_month: Optional[str] = None            # current / next
    default_pay_day: Optional[int] = None
    default_income_items: Optional[List[dict]] = None


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
    status_name: str = ""

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

class DistributionItem(BaseModel):
    name: str
    value: int

class DashboardData(BaseModel):
    status_distribution: List[StatusDistribution] = []
    priority_distribution: List[PriorityDistribution] = []
    project_progress: List[ProjectProgress] = []
    trend: List[TrendPoint] = []
    extra_distributions: dict[str, list[DistributionItem]] = {}
    """自定义字段分布，key=字段名, value=分布列表"""
    available_chart_fields: list[dict] = []
    """可用于图表展示的字段列表 [{key, label}]"""


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
