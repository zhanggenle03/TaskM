from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Date, ForeignKey, Boolean, Float, UniqueConstraint, event, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os, random, string, json

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


def reconcile_task_status(db, task_id, authoritative_ids=None):
    """
    整链重建（2026-08-01 v4：权威延展+衔接修正）。

    按 (comm_at, id) 升序遍历该任务全部沟通记录，保证相邻真变更记录的 old→new 衔接，
    最终状态写回 Task.status_id。

    原则：
    - authoritative_ids 中的记录为"用户本次编辑的记录"：old/new 字段绝不被衔接修正覆盖；
      其中权威伪变更（new == old）视为"用户显式声明状态"，推进 current 到 new（解决"改了没反应"）。
    - 非权威真变更（new ≠ old）：old 与 current 不符 → 修正 old = current（保证链衔接）；
      修正前预测是否会变伪变：若修正后 old == new，跳过修正保留原貌（避免毁掉真实状态记录）。
    - 非权威伪变更（new == old）：清 new（数据矛盾兜底；前端提交时已提示并自动转空）。
    - **无变更带 old 记录的权威延展（v4 修复"修改中间无状态变更的纯文字记录后前后不连续"，v4.1 覆盖无new权威，v4.4 延伸到最近真变更）**：
      权威记录前后的"无变更带 old"记录做衔接，不跨真变更——若路径上有非权威真变更，
      衔接最近真变更的 old(记录在真变更前)/new(记录在真变更后)；无障碍则直接衔接权威。

    触发于 update_task / add_communication / update_communication / delete_communication /
    状态池硬删后对受影响任务的重接。update_communication 传入本次编辑的 comm.id 作权威。
    返回最终状态；任务不存在返回 None。
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return None
    comms = db.query(Communication).filter(
        Communication.task_id == task_id
    ).order_by(Communication.comm_at, Communication.id).all()

    auth = authoritative_ids or set()

    # === 第一遍：识别权威区段，预先衔接权威前后的"无变更带 old"记录 ===
    # 收集"权威延展目标值"
    # - 真变：anchor_old=权威 old(可空)、tail_new=权威 new
    # - 伪变：anchor_old=权威 new(伪变 old==new)、tail_new=权威 new
    # - 无变更(只有 old 无 new)：anchor_old=权威 old、tail_new=权威 old（前后统一锚定到同一状态）
    auth_targets = {}  # idx -> (anchor_old_for_prev, tail_new_for_next)
    for i, c in enumerate(comms):
        if c.id not in auth:
            continue
        if c.new_status_id is None and c.old_status_id is None:
            continue  # 权威纯文字(两字段都空)不延展
        if c.new_status_id is None:
            # 权威无变更(只有 old 无 new)：前后都按 old（v4.1 修复：只改 old 不改 new 导致链断）
            auth_targets[i] = (c.old_status_id, c.old_status_id)
        elif c.new_status_id == c.old_status_id:
            # 权威伪变：前后都按 new
            auth_targets[i] = (c.new_status_id, c.new_status_id)
        else:
            # 权威真变：前按 old、后按 new（old 为空时退回 current，延展时跳过）
            auth_targets[i] = (c.old_status_id, c.new_status_id)

    # 找出每条记录"前/后最近权威索引"——权威的"影响方向"决定衔接值
    # auth_after[i]: i 之后最近的权威(i 早于该权威)→ 衔接权威 old(i 是权威前的记录)
    # auth_before[i]: i 之前最近的权威(i 晚于该权威)→ 衔接权威 new(i 是权威后的记录)
    auth_indices = sorted(auth_targets.keys())
    auth_after = {}
    auth_before = {}
    if auth_indices:
        for i in range(len(comms)):
            after_list = [a for a in auth_indices if a > i]
            before_list = [a for a in auth_indices if a < i]
            auth_after[i] = after_list[0] if after_list else None
            auth_before[i] = before_list[-1] if before_list else None

        # 对"无变更带 old"记录做衔接（v4.4：延伸到最近真变更，而非放弃）
        # 每条无变更带old记录衔接它前后"最近的链状态"——优先权威，若被真变更阻断则衔接该真变更
        for i, c in enumerate(comms):
            if c.id in auth:
                continue
            if c.new_status_id is not None:
                continue
            if c.old_status_id is None:
                continue
            ba = auth_before.get(i)
            af = auth_after.get(i)
            target = None

            # 决定方向（优先距离更近的权威）
            use_ba = None
            if ba is not None and af is not None:
                use_ba = (i - ba) <= (af - i)
            elif ba is not None:
                use_ba = True
            elif af is not None:
                use_ba = False
            else:
                continue  # 无权威，不处理

            if use_ba:
                # 权威在之前，记录在权威之后——找"权威到记录之间最后一条真变更(非权威)"的 new
                # 若无真变更则直接用权威的 tail_new
                found = None
                for prev in reversed(comms[(ba + 1):i]):
                    if prev.new_status_id is not None and prev.new_status_id != prev.old_status_id and prev.id not in auth:
                        found = prev
                        break
                if found is not None:
                    target = found.new_status_id
                else:
                    target = auth_targets[ba][1]
            else:
                # 权威在之后，记录在权威之前——找"记录到权威之间第一条真变更(非权威)"的 old
                # 若无真变更则直接用权威的 anchor_old
                found = None
                for mid in comms[(i + 1):af]:
                    if mid.new_status_id is not None and mid.new_status_id != mid.old_status_id and mid.id not in auth:
                        found = mid
                        break
                if found is not None:
                    target = found.old_status_id
                else:
                    target = auth_targets[af][0]

            if target is not None and c.old_status_id != target:
                c.old_status_id = target

    # === 第二遍：计算 current（权威锚定 + 真变更/伪变更/非权威衔接；v4.2 权威反向修正） ===
    current = task.status_id
    anchor_set = False

    def _reverse_fix_prev_new(idx, new_current):
        """权威 current 改变后，反向修正前面最近一条非权威真变更的 new 值"""
        for prev in reversed(comms[:idx]):
            if prev.new_status_id is not None and prev.new_status_id != prev.old_status_id:
                if prev.id not in auth and prev.new_status_id != new_current:
                    prev.new_status_id = new_current
                break  # 只修正最近一条真变更

    for i, c in enumerate(comms):
        if c.new_status_id is not None:
            if c.new_status_id != c.old_status_id:
                # 真变更
                if c.id in auth:
                    if c.old_status_id is not None:
                        if current != c.old_status_id:
                            _reverse_fix_prev_new(i, c.old_status_id)
                        current = c.old_status_id
                    anchor_set = True
                elif not anchor_set:
                    if c.old_status_id is not None:
                        current = c.old_status_id
                    anchor_set = True
                elif c.old_status_id is not None and c.old_status_id != current:
                    if current != c.new_status_id:
                        c.old_status_id = current
                elif c.old_status_id is None:
                    c.old_status_id = current
                current = c.new_status_id
            else:
                # 伪变更（new == old）
                if c.id in auth or c.protected_fake:
                    if current != c.new_status_id:
                        _reverse_fix_prev_new(i, c.new_status_id)
                    current = c.new_status_id
                    anchor_set = True
                else:
                    c.new_status_id = None
        elif c.id in auth and c.old_status_id is not None:
            # 权威无变更（只有 old 无 new，v4.1）：以权威 old 重锚起点
            if current != c.old_status_id:
                _reverse_fix_prev_new(i, c.old_status_id)
            current = c.old_status_id
            anchor_set = True

    task.status_id = current
    db.commit()
    return current


def derive_task_status(db, task_id):
    """
    从沟通记录推导任务的最终状态（只读）。
    逻辑：以人为设置的沟通时间(comm_at)为准，取最新一条沟通记录：
    - 该记录发生了状态变更（new_status_id 非空）→ 当前状态即 new_status_id；
    - 否则（未发生状态变更）→ 当前状态沿用其 old_status_id；
    - 最新记录无任何状态信息（纯文字记录）→ 返回 None，由调用方回退 Task.status_id 字段。
    说明：链由 reconcile_task_status 保证自洽后，本结果与字段一致。
    """
    last_comm = db.query(Communication.old_status_id, Communication.new_status_id).filter(
        Communication.task_id == task_id
    ).order_by(Communication.comm_at.desc(), Communication.id.desc()).first()
    if not last_comm:
        return None
    if last_comm.new_status_id is not None:
        return last_comm.new_status_id
    return last_comm.old_status_id


sync_task_status = reconcile_task_status  # 兼容旧调用点：状态同步统一走整链重建


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
    # 用户编辑沟通时显式设置了"新状态"等于"旧状态"（即 new==old）会被标记为 True，
    # 代表"用户显式声明任务状态=此值"。后续 reconcile 看到此标记不清除 new、推进 current，
    # 保护用户编辑意图不被后续删除等操作撤销（2026-08-01）。
    protected_fake = Column(Boolean, default=False, nullable=False)

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
    # 该签到记录下本项目分配的天数（多项目时用户自填；NULL=未填，统计端按人天占比兜底）
    days = Column(Float, nullable=True)


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
    """薪资记录：按月记录（period "YYYY-MM" + record_type 组合唯一，同月可有多条：工资/奖金）"""
    __tablename__ = "salary_records"
    id = Column(Integer, primary_key=True, index=True)
    period = Column(String(20), nullable=False)  # "2026-07"
    record_type = Column(String(10), default="salary", nullable=False)  # salary=工资 / bonus=奖金
    pay_date = Column(Date, nullable=True)                    # 发放日
    employer = Column(String(200), default="")               # 单位名称（可选）
    credited_amount = Column(Float, nullable=True)            # 当月到账（实际入卡）
    actual_tax = Column(Float, nullable=True)                  # 实际个税
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    items = relationship("SalaryItem", back_populates="record", cascade="all, delete-orphan", order_by="SalaryItem.sort_order")
    slips = relationship("SalarySlip", back_populates="record", cascade="all, delete-orphan", order_by="SalarySlip.id")

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
    taxable = Column(Boolean, default=True)  # 是否计入个税（仅 income 类别生效；False=转账等非计税收入）
    sort_order = Column(Integer, default=0)

    record = relationship("SalaryRecord", back_populates="items")


class SalarySlip(Base):
    """工资条附件：每条薪资记录可挂多张（一对多）。

    文件存 uploads/salary/{uuid}.{ext}；完整备份（FULL）自动打包 uploads 目录。
    删除薪资记录时：ORM cascade 删本表记录，物理文件由 salary 路由删除接口负责。
    """
    __tablename__ = "salary_slips"
    id = Column(Integer, primary_key=True, index=True)
    salary_record_id = Column(
        Integer,
        ForeignKey("salary_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename = Column(String(300), nullable=False)            # 存储文件名（uuid + ext）
    original_filename = Column(String(300), nullable=False)   # 原始文件名
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)
    mime_type = Column(String(100), default="")
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    record = relationship("SalaryRecord", back_populates="slips")


class SalaryConfigTemplate(Base):
    """薪资配置模板：多套命名模板（基础设置 + 五险一金）。

    同一时刻最多一条 is_active=True（当前激活模板，用于「新增薪资自动带入」）。
    config_json 存全量配置 JSON：employer / social_bases / social_rates /
    default_pay_month / default_pay_day / default_income_items。
    """
    __tablename__ = "salary_config_templates"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)                 # 模板名，如「2025 深圳」
    config_json = Column(Text, nullable=False, default="{}")   # 全量配置 JSON 字符串
    is_active = Column(Boolean, default=False)                 # 当前激活模板
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


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


def _ensure_salary_record_type_column():
    """幂等迁移：salary_records 加 record_type 列（salary/bonus），并把 period 唯一约束改为 (period, record_type) 组合唯一。

    SQLite 的列唯一约束（sqlite_autoindex）无法直接删除，需重建表：
      旧表 → 新表（含 record_type、UNIQUE(period, record_type)），旧数据 record_type 一律 'salary'，
      id 原样保留 → salary_items / salary_slips 外键按 id 匹配不受影响。
    """
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if "salary_records" not in inspector.get_table_names():
        return
    cols = [c["name"] for c in inspector.get_columns("salary_records")]
    period_unique = any(
        ix.get("unique") and ix.get("column_names") == ["period"]
        for ix in inspector.get_indexes("salary_records")
    )
    # 已迁移（有列且唯一约束已移除）则跳过
    if "record_type" in cols and not period_unique:
        return

    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(text("BEGIN"))
        try:
            conn.execute(text("ALTER TABLE salary_records RENAME TO salary_records_old"))
            conn.execute(text("""
                CREATE TABLE salary_records (
                    id INTEGER NOT NULL,
                    period VARCHAR(20) NOT NULL,
                    record_type VARCHAR(10) NOT NULL DEFAULT 'salary',
                    pay_date DATE,
                    employer VARCHAR(200) DEFAULT '',
                    credited_amount FLOAT,
                    actual_tax FLOAT,
                    remark TEXT DEFAULT '',
                    created_at DATETIME,
                    updated_at DATETIME,
                    PRIMARY KEY (id),
                    UNIQUE (period, record_type)
                )
            """))
            conn.execute(text("""
                INSERT INTO salary_records
                    (id, period, record_type, pay_date, employer, credited_amount, actual_tax, remark, created_at, updated_at)
                SELECT id, period, 'salary', pay_date, employer, credited_amount, actual_tax, remark, created_at, updated_at
                FROM salary_records_old
            """))
            conn.execute(text("DROP TABLE salary_records_old"))
            conn.execute(text("COMMIT"))
        except Exception:
            conn.execute(text("ROLLBACK"))
            raise
        finally:
            conn.execute(text("PRAGMA foreign_keys=ON"))
    # SQLite 重命名表会把其他表指向它的外键一并改写（salary_items / salary_slips 的 REFERENCES 变成 salary_records_old），
    # 需重建子表把引用改回 salary_records
    _fix_salary_child_foreign_keys(engine)


def _fix_salary_child_foreign_keys(engine):
    """修复 ALTER TABLE RENAME 改写的外键引用（salary_items / salary_slips 的 REFERENCES salary_records_old → salary_records）。

    SQLite 的 ALTER TABLE RENAME 会同步更新其他表外键中对该表的引用，
    导致重建 salary_records 后子表外键指向已删除的 salary_records_old，插入明细时报 "no such table"。
    幂等：仅当外键仍指向 salary_records_old 时重建子表。
    """
    from sqlalchemy import inspect, text
    for table in ("salary_items", "salary_slips"):
        with engine.connect() as conn:
            fks = conn.execute(text(f"PRAGMA foreign_key_list({table})")).fetchall()
        if not any("salary_records_old" in str(fk) for fk in fks):
            continue
        # 在 RENAME 前读取原建表 SQL 与显式索引 SQL（RENAME 后索引随表改名，届时按旧名查不到）
        with engine.connect() as conn:
            old_sql = conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:n"), {"n": table}
            ).scalar()
            idx_sqls = [r[0] for r in conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=:t AND sql IS NOT NULL AND name NOT LIKE 'sqlite_%'"),
                {"t": table},
            )]
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            conn.execute(text("BEGIN"))
            try:
                new_sql = old_sql.replace("salary_records_old", "salary_records")
                conn.execute(text(f"ALTER TABLE {table} RENAME TO {table}_old"))
                conn.execute(text(new_sql))
                cols = [r[1] for r in conn.execute(text(f"PRAGMA table_info({table}_old)"))]
                collist = ", ".join(cols)
                conn.execute(text(f"INSERT INTO {table} ({collist}) SELECT {collist} FROM {table}_old"))
                conn.execute(text(f"DROP TABLE {table}_old"))
                # 重建显式索引
                for s in idx_sqls:
                    if s:
                        conn.execute(text(s))
                conn.execute(text("COMMIT"))
            except Exception:
                conn.execute(text("ROLLBACK"))
                raise
            finally:
                conn.execute(text("PRAGMA foreign_keys=ON"))


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


def ensure_salary_item_taxable(engine):
    """幂等迁移：为 salary_items 表补充 taxable 列。

    仅加列不改旧数据：默认 1（计税），历史记录行为与现状完全一致；
    转账等非计税收入由用户在明细行取消勾选后写入 0。
    """
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if "salary_items" not in inspector.get_table_names():
        return
    cols = [c["name"] for c in inspector.get_columns("salary_items")]
    if "taxable" not in cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE salary_items ADD COLUMN taxable BOOLEAN DEFAULT 1"))
            conn.commit()
        print("[migrate] salary_items.taxable 列已添加（历史数据默认计税）", flush=True)


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


def ensure_communication_protected_fake_column(engine):
    """幂等迁移：为已存在的 communications 表补充 protected_fake 列。

    标记用户显式设置的"伪变更"记录（new==old 表示"确认状态=X"），使后续 reconcile 永远不清其 new。
    """
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if "communications" not in inspector.get_table_names():
        return
    cols = [c["name"] for c in inspector.get_columns("communications")]
    if "protected_fake" not in cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE communications ADD COLUMN protected_fake BOOLEAN DEFAULT 0 NOT NULL"))
            conn.commit()
        print("[migrate] communications.protected_fake 列已添加", flush=True)


def ensure_salary_slip_table(engine):
    """幂等迁移：创建 salary_slips 表（工资条附件，每月一条）。

    全新库由 Base.metadata.create_all 直接建出；此处仅兜底已存在的旧库。
    """
    from sqlalchemy import inspect
    inspector = inspect(engine)
    if "salary_slips" not in inspector.get_table_names():
        SalarySlip.__table__.create(engine)
        print("[migrate] salary_slips 表已创建", flush=True)


def ensure_salary_slip_multi(engine):
    """幂等迁移：salary_slips 去掉 salary_record_id 唯一约束（每月可多张工资条）。

    SQLite 不支持 ALTER DROP CONSTRAINT，需重建表：建新表→拷贝数据→删旧表→改名。
    """
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if "salary_slips" not in inspector.get_table_names():
        return
    # 检查是否存在 salary_record_id 的唯一索引
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='salary_slips'"
        )).fetchall()
    unique_idx = [r[0] for r in rows if r[0].startswith("sqlite_autoindex") or "salary_record" in (r[0] or "")]
    if not unique_idx:
        return  # 已是多附件结构
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE salary_slips_new (
                id INTEGER NOT NULL PRIMARY KEY,
                salary_record_id INTEGER NOT NULL,
                filename VARCHAR(300) NOT NULL,
                original_filename VARCHAR(300) NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                file_size INTEGER,
                mime_type VARCHAR(100),
                uploaded_at DATETIME,
                FOREIGN KEY(salary_record_id) REFERENCES salary_records (id) ON DELETE CASCADE
            )
        """))
        conn.execute(text(
            "INSERT INTO salary_slips_new (id, salary_record_id, filename, original_filename, file_path, file_size, mime_type, uploaded_at) "
            "SELECT id, salary_record_id, filename, original_filename, file_path, file_size, mime_type, uploaded_at FROM salary_slips"
        ))
        conn.execute(text("DROP TABLE salary_slips"))
        conn.execute(text("ALTER TABLE salary_slips_new RENAME TO salary_slips"))
        conn.commit()
    print("[migrate] salary_slips 已去除唯一约束（每月多张）", flush=True)


def ensure_salary_config_template_table(engine):
    """幂等迁移：创建 salary_config_templates 表（薪资配置模板）。

    全新库由 Base.metadata.create_all 直接建出；此处仅兜底已存在的旧库。
    """
    from sqlalchemy import inspect
    inspector = inspect(engine)
    if "salary_config_templates" not in inspector.get_table_names():
        SalaryConfigTemplate.__table__.create(engine)
        print("[migrate] salary_config_templates 表已创建", flush=True)


def migrate_salary_config_from_settings():
    """把旧版 settings.json 中的 salary_config 迁移进 salary_config_templates 表。

    幂等：表内已有记录即跳过。旧数据成为第一套模板（名称「默认配置」、标记激活），
    迁移完成后移除 settings.json 中的旧键，此后配置读写统一走数据库表。
    若无旧配置（全新库），则兜底创建一条空的激活模板「默认配置」，保证永远至少一套。
    """
    try:
        from .settings_manager import load_settings, remove_settings_key
        db = SessionLocal()
        try:
            if db.query(SalaryConfigTemplate).count() > 0:
                return
            settings = load_settings()
            raw = settings.get("salary_config") or {}
            cfg_json = json.dumps(raw, ensure_ascii=False)
            db.add(SalaryConfigTemplate(
                name="默认配置",
                config_json=cfg_json, is_active=True,
            ))
            db.commit()
            remove_settings_key("salary_config")
            if raw:
                print("[migrate] salary_config 已迁移为「默认配置」模板", flush=True)
            else:
                print("[migrate] 已创建默认薪资配置模板", flush=True)
        finally:
            db.close()
    except Exception as e:
        print(f"[migrate] salary_config 迁移失败: {e}", flush=True)


def ensure_salary_config_template_drop_effective_from(engine):
    """幂等迁移：salary_config_templates 表删除 effective_from 列（生效月份已无用途）。

    SQLite 旧版本不支持 ALTER DROP COLUMN，采用重建表：建新表→拷贝数据→删旧表→改名。
    数据完整性：仅丢弃 effective_from 列，其余列原样保留。
    """
    from sqlalchemy import inspect
    inspector = inspect(engine)
    if "salary_config_templates" not in inspector.get_table_names():
        return
    cols = [c["name"] for c in inspector.get_columns("salary_config_templates")]
    if "effective_from" not in cols:
        return
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE salary_config_templates_new (
                id INTEGER NOT NULL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                config_json TEXT NOT NULL,
                is_active BOOLEAN,
                created_at DATETIME,
                updated_at DATETIME
            )
        """))
        conn.execute(text(
            "INSERT INTO salary_config_templates_new (id, name, config_json, is_active, created_at, updated_at) "
            "SELECT id, name, config_json, is_active, created_at, updated_at FROM salary_config_templates"
        ))
        conn.execute(text("DROP TABLE salary_config_templates"))
        conn.execute(text("ALTER TABLE salary_config_templates_new RENAME TO salary_config_templates"))
        conn.commit()
    print("[migrate] salary_config_templates 已删除 effective_from 列", flush=True)


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
    """根据显示ID查找任务，未找到抛出404（兼容数字 ID 兜底）"""
    from fastapi import HTTPException
    query = db.query(Task).filter(Task.project_id == project_pk)
    # 尝试按数字 ID 查询
    try:
        numeric_id = int(task_display_id)
        task = query.filter(Task.id == numeric_id).first()
        if task:
            return task
    except (ValueError, TypeError):
        pass
    task = query.filter(Task.display_id == task_display_id).first()
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


def _ensure_checkin_project_days_column():
    """为 checkin_projects 关联表补充 days 列（多项目时各项目单独填写的天数）。

    已存在则跳过。历史行不强制回填（置 NULL），统计端遇到 NULL 时按人天占比兜底，
    与新功能上线前的行为保持一致。"""
    try:
        insp = inspect(engine)
        cols = [c["name"] for c in insp.get_columns("checkin_projects")]
        if "days" not in cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE checkin_projects ADD COLUMN days REAL"))
                conn.commit()
            print("[migrate] checkin_projects.days 列已添加", flush=True)
        else:
            print("[migrate] checkin_projects.days 列已存在", flush=True)
    except Exception as e:
        print(f"[migrate] 检查/添加 checkin_projects.days 列失败: {e}", flush=True)
