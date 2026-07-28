from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Date, ForeignKey, Boolean, Float, UniqueConstraint, event, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os, random, string

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "taskm.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
CONFIG_DIR = os.path.join(BASE_DIR, "config")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# SQLite WAL 模式：页面挂载瞬间并发多个读请求时，读互不阻塞、读取更快，
# 避免 "database is locked" 与首屏数据加载卡顿。synchronous=NORMAL 在 WAL 下安全且更快。
@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, conn_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

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
    pinned = Column(Boolean, default=False)
    # 书签式分类：存分类 key（空串表示未分类）。分类名称本身维护在 settings.json 的 project_categories。
    category = Column(String(100), default="", nullable=False)

    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    status_pools = relationship("StatusPool", back_populates="project", cascade="all, delete-orphan")
    comm_type_pools = relationship("CommTypePool", back_populates="project", cascade="all, delete-orphan")
    project_contacts = relationship("ProjectContact", back_populates="project", cascade="all, delete-orphan")
    tag_pools = relationship("TagPool", back_populates="project", cascade="all, delete-orphan")
    requirements = relationship("Requirement", back_populates="project", cascade="all, delete-orphan")
    requirement_fields = relationship("RequirementCustomField", back_populates="project", cascade="all, delete-orphan")
    requirement_status_pools = relationship("RequirementStatusPool", back_populates="project", cascade="all, delete-orphan")
    requirement_priority_pools = relationship("RequirementPriorityPool", back_populates="project", cascade="all, delete-orphan")


# ========== 需求模块 ==========

class Requirement(Base):
    """需求表"""
    __tablename__ = "requirements"
    __table_args__ = (
        UniqueConstraint('project_id', 'title', name='uq_req_project_title'),
    )
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    display_id = Column(String(50), unique=True, nullable=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, default="")
    priority = Column(String(20), default="normal")  # low/normal/high/urgent
    status = Column(String(50), default="todo")       # todo/in_progress/done/cancelled
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    project = relationship("Project", back_populates="requirements")
    custom_values = relationship("RequirementCustomValue", back_populates="requirement", cascade="all, delete-orphan")


class RequirementCustomField(Base):
    """需求自定义字段定义"""
    __tablename__ = "requirement_custom_fields"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    field_name = Column(String(100), nullable=False)
    field_type = Column(String(20), nullable=False)  # text/dropdown/multi_dropdown/datetime/date/number
    field_options = Column(Text, default="")  # JSON string for dropdown options
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    is_builtin = Column(Boolean, default=False)  # 是否为内置字段（标题/状态/优先级）
    created_at = Column(DateTime, default=datetime.now)

    project = relationship("Project", back_populates="requirement_fields")
    values = relationship("RequirementCustomValue", back_populates="field", cascade="all, delete-orphan")


class RequirementCustomValue(Base):
    """需求自定义字段值"""
    __tablename__ = "requirement_custom_values"
    id = Column(Integer, primary_key=True, index=True)
    requirement_id = Column(Integer, ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False)
    field_id = Column(Integer, ForeignKey("requirement_custom_fields.id", ondelete="CASCADE"), nullable=False)
    value = Column(Text, default="")

    requirement = relationship("Requirement", back_populates="custom_values")
    field = relationship("RequirementCustomField", back_populates="values")


class RequirementStatusPool(Base):
    """需求状态池"""
    __tablename__ = "requirement_status_pools"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(20), default="#5F5E5A")
    sort_order = Column(Integer, default=0)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    project = relationship("Project", back_populates="requirement_status_pools")


class RequirementPriorityPool(Base):
    """需求优先级池"""
    __tablename__ = "requirement_priority_pools"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(20), default="#5F5E5A")
    sort_order = Column(Integer, default=0)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    project = relationship("Project", back_populates="requirement_priority_pools")


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
    linked_requirements = relationship("Requirement", secondary="task_requirements")


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
    subject = Column(String(300), default="", nullable=False)  # 沟通主题（导出二级标题用，可空）
    # 与 add_communication 中 datetime.now() 保持一致，统一用本地时间，
    # 避免个别记录走默认 utcnow 差 8 小时，影响按日期筛选沟通记录。
    comm_at = Column(DateTime, default=datetime.now)
    comm_type = Column(String(50), default="note")  # note/meeting/email/call
    created_at = Column(DateTime, default=datetime.now)

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
    # 人天体系：当天人天（默认 1.0，加班/并行多项目/调休补班等可 >1），man_day_reason 记录原因
    man_days = Column(Float, default=1.0, nullable=False)
    man_day_reason = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    projects = relationship("Project", secondary="checkin_projects", backref="checkins_ref")
    tasks = relationship("Task", secondary="checkin_tasks", backref="checkins_ref")


class CheckinProject(Base):
    __tablename__ = "checkin_projects"
    checkin_id = Column(Integer, ForeignKey("checkins.id", ondelete="CASCADE"), primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), primary_key=True)
    # 该签到记录下本项目分配的人天（多项目时各项目分别填写，合计=当天人天）
    man_days = Column(Float, default=1.0, nullable=False)


class CheckinTask(Base):
    __tablename__ = "checkin_tasks"
    checkin_id = Column(Integer, ForeignKey("checkins.id", ondelete="CASCADE"), primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), primary_key=True)


class HolidayOverride(Base):
    """节假日用户手动覆盖表"""
    __tablename__ = "holiday_overrides"
    date = Column(Date, primary_key=True)  # 唯一键，同一天只能有一个覆盖
    override_type = Column(String(20), nullable=False)  # 'holiday' | 'workday' | 'normal' | 'off'
    remark = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class HolidayBase(Base):
    """节假日基准数据表（timor.tech 来源），作为本地快速读取源。

    读取路径：请求内只从内存热缓存 _CACHE（启动时由本表预热）取，绝不联网。
    刷新路径：后台线程拉取 timor.tech，与已存数据 diff，有变化才 upsert 本表。
    """
    __tablename__ = "holiday_base"
    year = Column(Integer, primary_key=True)
    data = Column(Text, nullable=False)            # JSON 字符串：{ 'MM-DD': {...} }
    fetched_at = Column(DateTime, default=datetime.utcnow)


class Leave(Base):
    """请假记录（年假/调休/请假），与签到独立的真实请假数据。

    与现有"派生请假"（工作日月≤今天无签到=请假）解耦：本表是用户主动录入的请假，
    日历优先展示本表记录，仅在无本表记录且工作日无签到时才显示"缺口"。
    """
    __tablename__ = "leaves"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)                 # 当日（逐日一条，永远是单日，与签到同构）
    date_end = Column(Date, nullable=True)               # 兼容旧多日记录；逐日记录恒为 NULL
    leave_type = Column(String(20), nullable=False, default="personal")  # annual|compensatory|personal
    subtype = Column(String(50), nullable=True)          # 请假子类型（事假/病假…）
    days = Column(Float, nullable=False, default=1.0)    # 该日请假天数（逐日记录恒为 1.0）
    reason = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="recorded")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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


class TaskRequirement(Base):
    """任务与需求的多对多关联表"""
    __tablename__ = "task_requirements"
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    requirement_id = Column(Integer, ForeignKey("requirements.id", ondelete="CASCADE"), primary_key=True)

# ========== 薪资模块 ==========

class SalaryRecord(Base):
    """薪资记录：每月一条（按 period "YYYY-MM" 唯一）"""
    __tablename__ = "salary_records"
    id = Column(Integer, primary_key=True, index=True)
    period = Column(String(20), unique=True, nullable=False)  # "2026-07"
    pay_date = Column(Date, nullable=True)                    # 发放日
    employer = Column(String(200), default="")               # 单位名称（可选）
    credited_amount = Column(Float, nullable=True)            # 当月到账（实际入卡）
    actual_tax = Column(Float, nullable=True)                  # 实际个税
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    items = relationship("SalaryItem", back_populates="record", cascade="all, delete-orphan", order_by="SalaryItem.sort_order")

class SalaryItem(Base):
    """薪资明细行：挂在某条薪资记录下。

    category 取值：
      income        收入项（基本工资/加班费/奖金/津贴等）
      deduction     五险一金个人部分及其他个人扣款
      tax           个人所得税
      company_cost  公司承担部分（五险一金公司缴纳等，仅参考展示）
    """
    __tablename__ = "salary_items"
    id = Column(Integer, primary_key=True, index=True)
    salary_record_id = Column(Integer, ForeignKey("salary_records.id", ondelete="CASCADE"), nullable=False)
    category = Column(String(20), nullable=False)
    name = Column(String(200), nullable=False)
    amount = Column(Float, default=0.0, nullable=False)
    base = Column(Float, nullable=True)  # 缴费基数（基数×比例自动算时用；可空）
    rate = Column(Float, nullable=True)  # 比例（百分比，如 8 表示 8%）；与 base 同时非空时 amount=base*rate/100
    funded_by = Column(String(20), default="")  # personal / company / 空
    tax_deductible = Column(Boolean, default=False)  # 是否参与个税专项扣除（仅 deduction 类别生效）
    sort_order = Column(Integer, default=0)

    record = relationship("SalaryRecord", back_populates="items")


class TaxAdjustment(Base):
    """个税汇算调整项：其他综合所得收入、专项附加扣除、其他扣除。

    category 取值：
      other_income      其他综合所得收入（劳务报酬/稿酬/特许权使用费）
      special_deduction 专项附加扣除（子女教育/继续教育/大病医疗等7项）
      other_deduction   其他扣除（企业年金/商业健康保险等）

    每个条目可指定时间段（period_from ~ period_to），支持同类型多条记录（如上下半年不同租金）。
    """
    __tablename__ = "tax_adjustments"
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False, index=True)            # 所属年份
    category = Column(String(20), nullable=False, index=True)     # other_income / special_deduction / other_deduction
    item_type = Column(String(50), nullable=False)               # 子类型标识
    label = Column(String(200), default="")                       # 自定义标签（如"上半年租金"）
    period_from = Column(String(10), default="")                  # 起始月份 "YYYY-MM"
    period_to = Column(String(10), default="")                    # 结束月份 "YYYY-MM"
    monthly_amount = Column(Float, default=0.0)                   # 月金额（对按月计算的项）
    tax_paid = Column(Float, default=0.0)                         # 对该项已预缴的个税（如劳务报酬预扣税）
    original_amount = Column(Float, nullable=True)                # 原始金额（对收入项，未乘计入比例前）
    amount = Column(Float, default=0.0)                          # 实际计入金额（period内合计）
    remark = Column(String(200), default="")
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


def ensure_salary_item_columns(engine):
    """幂等迁移：为已存在的 salary_items 表补充 base/rate 列。

    全新库由 Base.metadata.create_all 建表时直接带出这两列；
    仅对已存在但缺列的旧库执行 ALTER，保证「老库无损」。
    """
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if "salary_items" not in inspector.get_table_names():
        return
    cols = [c["name"] for c in inspector.get_columns("salary_items")]
    for col, ddl in (
        ("base", "ALTER TABLE salary_items ADD COLUMN base REAL"),
        ("rate", "ALTER TABLE salary_items ADD COLUMN rate REAL"),
    ):
        if col not in cols:
            with engine.connect() as conn:
                conn.execute(text(ddl))
                conn.commit()


def ensure_salary_record_columns(engine):
    """幂等迁移：为已存在的 salary_records 表补充 credited_amount / actual_tax 列。"""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if "salary_records" not in inspector.get_table_names():
        return
    cols = [c["name"] for c in inspector.get_columns("salary_records")]
    for col, ddl in (
        ("credited_amount", "ALTER TABLE salary_records ADD COLUMN credited_amount REAL"),
        ("actual_tax", "ALTER TABLE salary_records ADD COLUMN actual_tax REAL"),
    ):
        if col not in cols:
            with engine.connect() as conn:
                conn.execute(text(ddl))
                conn.commit()


def ensure_salary_item_tax_deductible(engine):
    """幂等迁移：为 salary_items 表补充 tax_deductible 列。

    同时将现有社保公积金项目自动设为 True。
    """
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if "salary_items" not in inspector.get_table_names():
        return
    cols = [c["name"] for c in inspector.get_columns("salary_items")]
    added = False
    if "tax_deductible" not in cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE salary_items ADD COLUMN tax_deductible BOOLEAN DEFAULT 0"))
            conn.commit()
        added = True
    if added:
        SOCIAL_TAX_NAMES = [
            "养老保险(个人)", "医疗保险(个人)", "失业保险(个人)", "住房公积金(个人)",
        ]
        with engine.connect() as conn:
            for name in SOCIAL_TAX_NAMES:
                conn.execute(
                    text("UPDATE salary_items SET tax_deductible = 1 WHERE name = :n AND category = 'deduction'"),
                    {"n": name},
                )
            conn.commit()


def ensure_tax_adjustment_table(engine):
    """幂等迁移：创建 tax_adjustments 表并补充新列"""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if "tax_adjustments" not in inspector.get_table_names():
        TaxAdjustment.__table__.create(engine)
        print("[migrate] tax_adjustments 表已创建", flush=True)
        return
    # 已存��则补充缺失列
    cols = [c["name"] for c in inspector.get_columns("tax_adjustments")]
    for col, ddl in (
        ("period_from", "ALTER TABLE tax_adjustments ADD COLUMN period_from VARCHAR(10) DEFAULT ''"),
        ("period_to", "ALTER TABLE tax_adjustments ADD COLUMN period_to VARCHAR(10) DEFAULT ''"),
        ("monthly_amount", "ALTER TABLE tax_adjustments ADD COLUMN monthly_amount REAL DEFAULT 0.0"),
        ("label", "ALTER TABLE tax_adjustments ADD COLUMN label VARCHAR(200) DEFAULT ''"),
        ("tax_paid", "ALTER TABLE tax_adjustments ADD COLUMN tax_paid REAL DEFAULT 0.0"),
    ):
        if col not in cols:
            with engine.connect() as conn:
                conn.execute(text(ddl))
                conn.commit()
            print(f"[migrate] tax_adjustments.{col} 列已添加", flush=True)


def ensure_communication_subject_column(engine):
    """幂等迁移：为已存在的 communications 表补充 subject 列。

    全新库由 Base.metadata.create_all 建表时直接带出该列；
    仅对已存在但缺列的旧库执行 ALTER，保证「老库无损」。
    """
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if "communications" not in inspector.get_table_names():
        return
    cols = [c["name"] for c in inspector.get_columns("communications")]
    if "subject" not in cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE communications ADD COLUMN subject VARCHAR(300) DEFAULT ''"))
            conn.commit()
        print("[migrate] communications.subject 列已添加", flush=True)


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


def generate_requirement_display_id(db, project) -> str:
    """生成需求显示ID 格式: Q + 项目ID(不含P) + "-" + 3位序号"""
    proj_id_no_p = project.display_id[1:] if project.display_id and project.display_id.startswith("P") else str(project.id)
    # 查询同一项目下最大序号
    last = db.query(Requirement.display_id).filter(
        Requirement.display_id.like(f"Q{proj_id_no_p}-%")
    ).order_by(Requirement.display_id.desc()).first()
    seq = (int(last[0][-3:]) + 1) if last and last[0][-3:].isdigit() else 1
    seq_str = f"{seq:03d}"
    return f"Q{proj_id_no_p}-{seq_str}"


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


def resolve_requirement(db, project_pk: int, requirement_id: str):
    """解析需求：支持数字 ID 或显示 ID（如 Q20260625001），未找到抛出404"""
    from fastapi import HTTPException
    query = db.query(Requirement).filter(Requirement.project_id == project_pk)
    # 尝试按数字 ID 查询
    try:
        numeric_id = int(requirement_id)
        req = query.filter(Requirement.id == numeric_id).first()
        if req:
            return req
    except (ValueError, TypeError):
        pass
    # 按显示 ID 查询
    req = query.filter(Requirement.display_id == requirement_id).first()
    if not req:
        raise HTTPException(404, "需求不存在")
    return req


def _ensure_project_category_column():
    """为 projects 表补充 category 列（书签分类用）。

    已存在则跳过；SQLite 不支持 ALTER 加带默认值约束的列，故用 NOT NULL DEFAULT '' 直接补齐。
    在应用启动（lifespan）时调用，保证任何查询 Project.category 前列已存在。
    """
    try:
        insp = inspect(engine)
        cols = [c["name"] for c in insp.get_columns("projects")]
        if "category" not in cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE projects ADD COLUMN category VARCHAR(100) NOT NULL DEFAULT ''"))
                conn.commit()
            print("[migrate] projects.category 列已添加", flush=True)
    except Exception as e:
        print(f"[migrate] 检查/添加 category 列失败: {e}", flush=True)


def _ensure_checkin_project_mandays_column():
    """为 checkin_projects 关联表补充 man_days 列（多项目时各项目单独分配人天）。

    已存在则跳过。补齐后把历史 junction 行（仍为默认 1.0）按「当天人天 / 关联项目数」回填，
    保证历史单项目签到 man_days 等于当天人天、多项目签到平均分摊（消除旧版重复计算）。
    """
    try:
        insp = inspect(engine)
        cols = [c["name"] for c in insp.get_columns("checkin_projects")]
        if "man_days" not in cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE checkin_projects ADD COLUMN man_days REAL NOT NULL DEFAULT 1.0"))
                conn.commit()
            print("[migrate] checkin_projects.man_days 列已添加", flush=True)

        # 回填：仅处理仍等于默认 1.0 的历史行（新写入的行已由应用代码赋正确值）
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT cp.checkin_id, cp.project_id, c.man_days "
                "FROM checkin_projects cp JOIN checkins c ON c.id = cp.checkin_id "
                "WHERE cp.man_days = 1.0"
            )).fetchall()
            by_c = {}
            for cid, pid, total in rows:
                by_c.setdefault(cid, {"total": total, "items": []})["items"].append(pid)
            for cid, info in by_c.items():
                n = len(info["items"])
                if n == 0:
                    continue
                total = info["total"] or 0.0
                share = round(total / n, 4)
                for i, pid in enumerate(info["items"]):
                    md = share if i < n - 1 else round(total - share * (n - 1), 4)
                    conn.execute(text(
                        "UPDATE checkin_projects SET man_days = :md "
                        "WHERE checkin_id = :cid AND project_id = :pid"
                    ), {"md": md, "cid": cid, "pid": pid})
            conn.commit()
        print("[migrate] checkin_projects.man_days 回填完成", flush=True)
    except Exception as e:
        print(f"[migrate] 检查/添加 checkin_projects.man_days 列失败: {e}", flush=True)
