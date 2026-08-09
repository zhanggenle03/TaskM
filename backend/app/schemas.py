from __future__ import annotations
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
    subject: str = ""
    old_status_id: Optional[int] = None
    new_status_id: Optional[int] = None

class CommunicationUpdate(BaseModel):
    content: Optional[str] = None
    contact_ids: Optional[List[int]] = None
    comm_at: Optional[datetime] = None
    comm_type: Optional[str] = None
    subject: Optional[str] = None
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
    subject: str = ""
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

# 任务搜索命中信息（仅 list_tasks 带 search 参数时返回）
class SearchCommHit(BaseModel):
    """任务内命中的一条沟通记录摘要"""
    id: int
    comm_at: Optional[datetime] = None
    subject: str = ""
    comm_type: str = ""
    snippet: str = ""          # 剥离 HTML 后的正文片段（含关键词上下文）
    contacts: List[str] = []

class SearchHits(BaseModel):
    """单个任务在综合搜索中的命中信息"""
    task_fields: List[str] = []   # 命中的任务字段：title/description/display_id/tag/contact
    comms: List[SearchCommHit] = []

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
    search_hits: Optional[SearchHits] = None
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
    # 多项目时各项目分配的天数：{project_id: days}，用户自填；缺省时统计端按人天占比兜底
    project_days: Dict[int, float] = {}

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
    status_id: Optional[int] = None
    status_name: Optional[str] = None
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
    project_days: Dict[int, Optional[float]] = {}  # 各项目分配的天数（NULL=未填，按人天占比兜底）
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
    tax_deductible: bool = False                    # 是否参与个税专项扣除（仅 deduction 类别生效）
    taxable: bool = True                            # 是否计入个税（仅 income 类别生效；False=转账等非计税收入）
    sort_order: int = 0

class SalaryItemOut(BaseModel):
    id: int
    category: str
    name: str
    amount: float
    base: Optional[float] = None
    rate: Optional[float] = None
    funded_by: str = ""
    tax_deductible: bool = False
    taxable: bool = True
    sort_order: int = 0
    class Config:
        from_attributes = True

class SalaryRecordCreate(BaseModel):
    period: str                                      # "YYYY-MM"
    record_type: str = "salary"                      # salary=工资 / bonus=奖金
    pay_date: Optional[str] = None                  # "YYYY-MM-DD"
    employer: str = ""
    credited_amount: Optional[float] = None          # 实际到账（入卡金额）
    actual_tax: Optional[float] = None               # 实际个税
    remark: str = ""
    items: List[SalaryItemCreate] = []

class SalarySlipRename(BaseModel):
    """工资条重命名请求"""
    original_filename: str


class SalarySlipOut(BaseModel):
    """工资条附件信息（每月可多张）"""
    id: int
    filename: str                       # 存储文件名（uuid.ext）
    original_filename: str              # 原始文件名
    file_size: int
    mime_type: str
    uploaded_at: datetime
    url: str = ""                       # 预览相对路径 /uploads/salary/{filename}

    class Config:
        from_attributes = True


class SalaryRecordOut(BaseModel):
    id: int
    period: str
    record_type: str = "salary"                      # salary=工资 / bonus=奖金
    pay_date: Optional[date] = None
    employer: str = ""
    credited_amount: Optional[float] = None          # 实际到账（入卡金额）
    actual_tax: Optional[float] = None               # 实际个税
    remark: str = ""
    created_at: datetime
    updated_at: datetime
    items: List[SalaryItemOut] = []
    slips: List[SalarySlipOut] = []                  # 工资条附件列表（每月可多张）
    # 汇总（后端计算，不冗余存储）
    gross: float = 0.0                              # 应发合计 = Σ income
    personal_deduction: float = 0.0                 # 个人扣除 = Σ deduction + Σ tax
    net: float = 0.0                                # 实发 = gross - personal_deduction
    company_cost: float = 0.0                       # 公司承担合计 = Σ company_cost
    personal_social_total: float = 0.0              # 个人社保合计 = Σ deduction(funded_by=personal)
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
    total_theoretical_tax: float = 0.0              # 理论税额合计（明细 tax 类目）

class SalaryCardOrderIn(BaseModel):
    """指标卡布局更新：order（顺序，可选）+ hidden（隐藏，可选），至少传一项"""
    order: Optional[List[str]] = None
    hidden: Optional[List[str]] = None

class SalaryTaxSummaryOut(BaseModel):
    """个税年度汇算汇总（按年累计，含综合汇算调整）"""
    year: int
    month_count: int = 0                             # 有记录月份数
    data_month: int = 0                              # 薪资数据已有最新月份（折算截止月；0=无数据）
    total_gross: float = 0.0                         # 薪资年度累计应发（仅计税收入）
    non_taxable_income: float = 0.0                  # 薪资非计税收入合计（转账等，不计入汇算）
    total_social_insurance: float = 0.0              # 薪资累计专项扣除（三险一金个人部分）
    actual_tax_paid: float = 0.0                     # 当年实缴税额（各月实际个税之和）
    deduction_fee: float = 0.0                       # 基本减除费用

    # 调整项汇总
    other_income_included: float = 0.0               # 其他综合所得收入合计（已乘计入比例）
    special_deduction_total: float = 0.0             # 专项附加扣除合计
    other_deduction_total: float = 0.0               # 其他扣除合计

    # 综合计算
    total_income: float = 0.0                        # 综合所得收入额 = total_gross + other_income_included
    total_deductions: float = 0.0                    # 各项扣除合计 = deduction_fee + total_social_insurance + special_deduction + other_deduction
    taxable_income: float = 0.0                      # 应纳税所得额 = total_income - total_deductions
    tax_rate: float = 0.0                            # 当前税率（百分比）
    tax_rate_label: str = ""                         # 税率标注字符串
    bracket_min: float = 0.0                         # 当前级距下限
    bracket_max: float = 0.0                         # 当前级距上限（0 表示无上限）
    quick_deduction: float = 0.0                     # 速算扣除数
    remaining_to_next: float = 0.0                   # 距下一级距剩余额度
    next_bracket_threshold: float = 0.0              # 下一级距门槛（0 表示无下一级）
    next_tax_rate: float = 0.0                       # 下一级距税率
    tax_payable: float = 0.0                         # 当年应交税额（应纳税所得额×税率−速算扣除数）
    tax_difference: float = 0.0                      # 差值（应交−实缴）

    # 调整项列表（供前端编辑）
    adjustments: List['TaxAdjustmentOut'] = []

class SalaryCalcTaxIn(BaseModel):
    """计算本月应扣个税的请求参数"""
    period: str                                      # "YYYY-MM"
    items: List[SalaryItemCreate] = []
    edit_id: Optional[int] = None                    # 编辑模式传入当前记录 ID 以排除自身
    use_items: bool = False                          # True=从历史明细行汇总个税，False=从 actual_tax 字段

# ── 薪资通用配置（存于 settings.json 的 salary_config，非独立表）──
class SalaryConfigOut(BaseModel):
    employer: str = ""                               # 默认单位名称
    social_bases: dict = {}                           # 各项缴费基数（通用稳定），key 为险种名；各项最低基数不同，故分项配置
    social_rates: dict = {}                           # 各险种比例（百分比，如 8=8%），key 为险种名
    default_pay_month: str = "current"                # 默认发放月份：current=当月 / next=次月
    default_pay_day: int = 10                         # 默认发放日（1~31）
    default_income_items: List[dict] = []             # 默认收入项模板 [{name, amount, taxable}]
    class Config:
        from_attributes = True

class SalaryConfigUpdate(BaseModel):
    employer: Optional[str] = None
    social_bases: Optional[dict] = None
    social_rates: Optional[dict] = None
    default_pay_month: Optional[str] = None            # current / next
    default_pay_day: Optional[int] = None
    default_income_items: Optional[List[dict]] = None


# ── 薪资配置模板（多套命名模板，存于 salary_config_templates 表）──

class SalaryConfigTemplateOut(BaseModel):
    id: int
    name: str
    config: SalaryConfigOut                            # 展开的完整配置
    is_active: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class SalaryConfigTemplateListOut(BaseModel):
    templates: List[SalaryConfigTemplateOut]
    active_id: Optional[int] = None

class SalaryConfigTemplateCreate(BaseModel):
    name: str
    base_id: Optional[int] = None                      # 以某模板为底复制；缺省=以当前激活为底
    activate: bool = True                              # 创建后是否立即设为激活

class SalaryConfigTemplateUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[SalaryConfigUpdate] = None

class SalaryConfigActiveUpdate(BaseModel):
    template_id: int


# ── 个税汇算调整项 ──

# 其他综合所得收入类型（含计入比例）
INCOME_CONVERSION_TYPES = {
    "labor_service": {"label": "劳务报酬", "rate": 0.80},
    "remuneration": {"label": "稿酬", "rate": 0.56},
    "royalty": {"label": "特许权使用费", "rate": 0.80},
}

# 专项附加扣除类型
SPECIAL_DEDUCTION_TYPES = {
    "children_education": "子女教育",
    "continuing_education": "继续教育",
    "medical_treatment": "大病医疗",
    "housing_loan_interest": "住房贷款利息",
    "housing_rent": "住房租金",
    "elderly_care": "赡养老人",
    "infant_care": "3岁以下婴幼儿照护",
}

# 其他扣除类型
OTHER_DEDUCTION_TYPES = {
    "enterprise_annuity": "企业年金/职业年金",
    "commercial_health": "商业健康保险",
    "deferred_pension": "税收递延型商业养老保险",
    "other_deduction_other": "其他",
}


class TaxAdjustmentCreate(BaseModel):
    year: int
    category: str
    item_type: str
    label: str = ""
    period_from: str = ""
    period_to: str = ""
    monthly_amount: float = 0.0
    tax_paid: float = 0.0
    original_amount: Optional[float] = None
    amount: float = 0.0
    remark: str = ""
    sort_order: int = 0


class TaxAdjustmentUpdate(BaseModel):
    label: Optional[str] = None
    period_from: Optional[str] = None
    period_to: Optional[str] = None
    monthly_amount: Optional[float] = None
    tax_paid: Optional[float] = None
    original_amount: Optional[float] = None
    amount: Optional[float] = None
    remark: Optional[str] = None
    sort_order: Optional[int] = None


class TaxAdjustmentOut(BaseModel):
    id: int
    year: int
    category: str
    item_type: str
    label: str = ""
    period_from: str = ""
    period_to: str = ""
    monthly_amount: float = 0.0
    tax_paid: float = 0.0
    original_amount: Optional[float] = None
    amount: float
    remark: str = ""
    sort_order: int = 0

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
    linked_tasks: List[TaskBrief] = []
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
