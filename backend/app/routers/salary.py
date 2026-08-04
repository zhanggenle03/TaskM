"""薪资记录模块：按月记录薪资发放、明细与五险一金等。

数据模型：
  SalaryRecord（每月一条，period="YYYY-MM" 唯一）
    └─ SalaryItem（明细行，category ∈ income/deduction/tax/company_cost）

汇总口径（前端展示用，后端计算不冗余存储）：
  应发合计     = Σ income
  个人扣除合计 = Σ deduction + Σ tax
  实发         = 应发合计 − 个人扣除合计
  公司承担合计 = Σ company_cost
"""
import urllib.parse
from datetime import datetime, date
import re
import uuid
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db, SalaryRecord, SalaryItem, TaxAdjustment, SalarySlip, UPLOAD_DIR
from ..schemas import (
    SalaryRecordCreate,
    SalaryRecordOut,
    SalaryItemOut,
    SalarySlipOut,
    SalarySummaryOut,
    SalaryTaxSummaryOut,
    SalaryCalcTaxIn,
    SalaryConfigOut,
    SalaryConfigUpdate,
    TaxAdjustmentCreate,
    TaxAdjustmentUpdate,
    TaxAdjustmentOut,
)
from ..schemas import VALID_SALARY_CATEGORIES
from ..settings_manager import load_settings, save_settings, get_max_file_size
from ..salary_export_service import generate_salary_export

router = APIRouter(prefix="/salary")

# 五险一金比例的标准键（与前端 SOCIAL_TEMPLATE 名称保持一致）
SOCIAL_RATE_KEYS = [
    "养老保险(个人)", "医疗保险(个人)", "失业保险(个人)", "住房公积金(个人)",
    "养老保险(公司)", "医疗保险(公司)", "失业保险(公司)",
    "工伤保险(公司)", "生育保险(公司)", "住房公积金(公司)",
]
# 个人社保合计（卡片展示）=养老+医疗+失业，不含公积金
SOCIAL_PERSONAL_NAMES = {"养老保险(个人)", "医疗保险(个人)", "失业保险(个人)"}
# 个税专项扣除 = 养老+医疗+失业+公积金（用于 calc-tax 和 tax-summary）
SOCIAL_TAX_NAMES = SOCIAL_PERSONAL_NAMES | {"住房公积金(个人)"}
DEFAULT_SALARY_CONFIG = {
    "employer": "",
    "social_bases": {},
    "social_rates": {
        "养老保险(个人)": 8, "医疗保险(个人)": 2, "失业保险(个人)": 0.5, "住房公积金(个人)": 5,
        "养老保险(公司)": 16, "医疗保险(公司)": 9, "失业保险(公司)": 0.5,
        "工伤保险(公司)": 0.4, "生育保险(公司)": 0.8, "住房公积金(公司)": 5,
    },
    "default_pay_day": 10,
    "default_pay_month": "current",
    "default_income_items": [],
}

_PERIOD_RE = re.compile(r"^\d{4}-\d{2}$")

# ── 工资条附件 ──
SALARY_SLIP_DIR = os.path.join(UPLOAD_DIR, "salary")          # uploads/salary/
ALLOWED_SLIP_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def _slip_to_out(slip) -> Optional[SalarySlipOut]:
    """构造工资条输出（补预览 URL）"""
    if not slip:
        return None
    return SalarySlipOut(
        id=slip.id,
        filename=slip.filename,
        original_filename=slip.original_filename,
        file_size=slip.file_size,
        mime_type=slip.mime_type,
        uploaded_at=slip.uploaded_at,
        url=f"/uploads/salary/{slip.filename}",
    )


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _compute_totals(record):
    """返回 (gross, personal_deduction, net, company_cost, personal_social_total)"""
    gross = sum(i.amount for i in record.items if i.category == "income")
    personal_deduction = sum(i.amount for i in record.items if i.category in ("deduction", "tax"))
    company_cost = sum(i.amount for i in record.items if i.category == "company_cost")
    personal_social = sum(i.amount for i in record.items
                          if i.category == "deduction" and i.name in SOCIAL_PERSONAL_NAMES)
    net = gross - personal_deduction
    return gross, personal_deduction, net, company_cost, personal_social


def _to_out(record: SalaryRecord) -> SalaryRecordOut:
    gross, pd, net, cc, pst = _compute_totals(record)
    return SalaryRecordOut(
        id=record.id,
        period=record.period,
        pay_date=record.pay_date,
        employer=record.employer or "",
        credited_amount=record.credited_amount,
        actual_tax=record.actual_tax,
        remark=record.remark or "",
        created_at=record.created_at,
        updated_at=record.updated_at,
        items=[
            SalaryItemOut(
                id=i.id,
                category=i.category,
                name=i.name,
                amount=i.amount,
                base=i.base,
                rate=i.rate,
                funded_by=i.funded_by or "",
                tax_deductible=i.tax_deductible or False,
                sort_order=i.sort_order,
            )
            for i in sorted(record.items, key=lambda x: x.sort_order)
        ],
        gross=round(gross, 2),
        personal_deduction=round(pd, 2),
        net=round(net, 2),
        company_cost=round(cc, 2),
        personal_social_total=round(pst, 2),
        slip=_slip_to_out(record.slip),
    )


def _validate_items(items):
    for it in items:
        if it.category not in VALID_SALARY_CATEGORIES:
            raise HTTPException(400, f"非法明细类别 category: {it.category}")
    return items


def _item_amount(it):
    """明细金额：base 与 rate 同时非空时按 基数×比例/100 自动算，否则用传入 amount。"""
    if it.base is not None and it.rate is not None:
        return round((it.base or 0) * (it.rate or 0) / 100.0, 2)
    return round(it.amount or 0.0, 2)


def _funded_by(category: str) -> str:
    if category == "company_cost":
        return "company"
    if category in ("deduction", "tax"):
        return "personal"
    return ""


def _make_salary_item(it, idx, salary_record_id=None):
    """构造一条 SalaryItem（自动换算 amount 并推导 funded_by，前端传值仅作为覆盖提示）"""
    return SalaryItem(
        salary_record_id=salary_record_id,
        category=it.category,
        name=it.name,
        amount=_item_amount(it),
        base=it.base,
        rate=it.rate,
        funded_by=_funded_by(it.category) or it.funded_by or "",
        tax_deductible=it.tax_deductible or False,
        sort_order=it.sort_order or idx,
    )


def _sync_items(db: Session, record_id: int, items):
    """删除旧明细并按传入重建（PUT 全量更新用）"""
    db.query(SalaryItem).filter(SalaryItem.salary_record_id == record_id).delete(synchronize_session=False)
    for idx, it in enumerate(items):
        db.add(_make_salary_item(it, idx, record_id))


# ──────────────────────────────────────────────── 列表 / 年份 ────────────────────────────────────────────────

@router.get("/records", response_model=List[SalaryRecordOut])
def list_salary_records(
    period_from: Optional[str] = None,
    period_to: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(SalaryRecord)
    if period_from:
        q = q.filter(SalaryRecord.period >= period_from)
    if period_to:
        q = q.filter(SalaryRecord.period <= period_to)
    records = q.order_by(SalaryRecord.period.desc()).all()
    return [_to_out(r) for r in records]


@router.get("/years", response_model=List[int])
def list_salary_years(db: Session = Depends(get_db)):
    rows = db.query(SalaryRecord.period).all()
    years = sorted({int(p[:4]) for (p,) in rows if p and p[:4].isdigit()})
    # 没有任何记录时，至少返回当前年份，方便首次录入
    if not years:
        years = [datetime.now().year]
    return years


# ──────────────────────────────────────────────── 详情 / 增删改 ────────────────────────────────────────────────

@router.get("/records/{record_id}", response_model=SalaryRecordOut)
def get_salary_record(record_id: int, db: Session = Depends(get_db)):
    rec = db.query(SalaryRecord).filter(SalaryRecord.id == record_id).first()
    if not rec:
        raise HTTPException(404, "薪资记录不存在")
    return _to_out(rec)


@router.post("/records", response_model=SalaryRecordOut)
def create_salary_record(data: SalaryRecordCreate, db: Session = Depends(get_db)):
    if not _PERIOD_RE.match(data.period or ""):
        raise HTTPException(400, "period 格式应为 YYYY-MM")
    if db.query(SalaryRecord).filter(SalaryRecord.period == data.period).first():
        raise HTTPException(409, f"已存在 {data.period} 的薪资记录")
    _validate_items(data.items)

    rec = SalaryRecord(
        period=data.period,
        pay_date=_parse_date(data.pay_date),
        employer=data.employer or "",
        credited_amount=data.credited_amount,
        actual_tax=data.actual_tax,
        remark=data.remark or "",
    )
    for idx, it in enumerate(data.items):
        rec.items.append(_make_salary_item(it, idx))
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _to_out(rec)


@router.put("/records/{record_id}", response_model=SalaryRecordOut)
def update_salary_record(record_id: int, data: SalaryRecordCreate, db: Session = Depends(get_db)):
    rec = db.query(SalaryRecord).filter(SalaryRecord.id == record_id).first()
    if not rec:
        raise HTTPException(404, "薪资记录不存在")
    if not _PERIOD_RE.match(data.period or ""):
        raise HTTPException(400, "period 格式应为 YYYY-MM")
    dup = db.query(SalaryRecord).filter(
        SalaryRecord.period == data.period,
        SalaryRecord.id != record_id,
    ).first()
    if dup:
        raise HTTPException(409, f"已存在 {data.period} 的薪资记录")
    _validate_items(data.items)

    rec.period = data.period
    rec.pay_date = _parse_date(data.pay_date)
    rec.employer = data.employer or ""
    rec.credited_amount = data.credited_amount
    rec.actual_tax = data.actual_tax
    rec.remark = data.remark or ""
    _sync_items(db, record_id, data.items)
    db.commit()
    db.refresh(rec)
    return _to_out(rec)


@router.delete("/records/{record_id}")
def delete_salary_record(record_id: int, db: Session = Depends(get_db)):
    rec = db.query(SalaryRecord).filter(SalaryRecord.id == record_id).first()
    if not rec:
        raise HTTPException(404, "薪资记录不存在")
    # 删除工资条物理文件（DB 记录由 ORM cascade="all, delete-orphan" 级联删除）
    if rec.slip and os.path.exists(rec.slip.file_path):
        try:
            os.remove(rec.slip.file_path)
        except OSError:
            pass
    db.delete(rec)
    db.commit()
    return {"ok": True}


# ──────────────────────────────────────────────── 工资条附件（每月一条，上传/查询/删除） ────────────────────────────────────────────────

@router.get("/records/{record_id}/slip", response_model=Optional[SalarySlipOut])
def get_salary_slip(record_id: int, db: Session = Depends(get_db)):
    """查询工资条附件信息（无则返回 null）"""
    rec = db.query(SalaryRecord).filter(SalaryRecord.id == record_id).first()
    if not rec:
        raise HTTPException(404, "薪资记录不存在")
    return _slip_to_out(rec.slip)


@router.post("/records/{record_id}/slip", response_model=SalarySlipOut)
async def upload_salary_slip(
    record_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传 / 替换工资条图片。仅图片类型；已有附件时先删旧文件再写，保证每月一条。"""
    rec = db.query(SalaryRecord).filter(SalaryRecord.id == record_id).first()
    if not rec:
        raise HTTPException(404, "薪资记录不存在")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_SLIP_EXTS or not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "仅支持图片文件（jpg / png / webp / gif / bmp）")

    # 替换：先删旧附件（记录与文件）
    old = rec.slip
    if old:
        if os.path.exists(old.file_path):
            try:
                os.remove(old.file_path)
            except OSError:
                pass
        db.delete(old)
        db.flush()

    # 保存新文件
    os.makedirs(SALARY_SLIP_DIR, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(SALARY_SLIP_DIR, unique_name)
    size = 0
    max_size = get_max_file_size()
    try:
        import aiofiles
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(1024 * 64):
                size += len(chunk)
                if size > max_size:
                    raise HTTPException(413, f"文件超过 {max_size // (1024 * 1024)}MB 限制")
                await f.write(chunk)
    except Exception:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        raise

    slip = SalarySlip(
        salary_record_id=record_id,
        filename=unique_name,
        original_filename=file.filename or unique_name,
        file_path=file_path,
        file_size=size,
        mime_type=file.content_type or "",
    )
    db.add(slip)
    db.commit()
    db.refresh(slip)
    return _slip_to_out(slip)


@router.delete("/records/{record_id}/slip")
def delete_salary_slip(record_id: int, db: Session = Depends(get_db)):
    """删除工资条（文件 + 记录）"""
    rec = db.query(SalaryRecord).filter(SalaryRecord.id == record_id).first()
    if not rec:
        raise HTTPException(404, "薪资记录不存在")
    slip = rec.slip
    if not slip:
        raise HTTPException(404, "该记录暂无工资条")
    if os.path.exists(slip.file_path):
        try:
            os.remove(slip.file_path)
        except OSError:
            pass
    db.delete(slip)
    db.commit()
    return {"ok": True}


# ──────────────────────────────────────────────── 年度汇总 ────────────────────────────────────────────────

@router.get("/summary", response_model=SalarySummaryOut)
def salary_summary(
    period_from: Optional[str] = None,
    period_to: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(SalaryRecord)
    if period_from:
        q = q.filter(SalaryRecord.period >= period_from)
    if period_to:
        q = q.filter(SalaryRecord.period <= period_to)
    records = q.all()
    tg = tp = tn = tc = tcrd = tact = 0.0
    for r in records:
        g, pd, net, cc, pst = _compute_totals(r)
        tg += g
        tp += pd
        tn += net
        tc += cc
        tcrd += r.credited_amount or 0.0
        tact += r.actual_tax or 0.0
    count = len(records)
    avg = round(tn / count, 2) if count else 0.0
    return SalarySummaryOut(
        period_from=period_from or "",
        period_to=period_to or "",
        record_count=count,
        total_gross=round(tg, 2),
        total_personal_deduction=round(tp, 2),
        total_net=round(tn, 2),
        total_company_cost=round(tc, 2),
        avg_net=avg,
        total_credited=round(tcrd, 2),
        total_actual_tax=round(tact, 2),
    )


# ──────────────────────────────────────────────── 年度汇算清缴 ────────────────────────────────────────────────

# 综合所得个税税率表（全年应纳税所得额，元）
# 每项：(上限, 税率%, 速算扣除数)，上限为 0 表示最后一级无上限
TAX_BRACKETS = [
    (36_000, 3, 0),
    (144_000, 10, 2_520),
    (300_000, 20, 16_920),
    (420_000, 25, 31_920),
    (660_000, 30, 52_920),
    (960_000, 35, 85_920),
    (0, 45, 181_920),
]

MONTHLY_DEDUCTION = 5000  # 每月基本减除费用


def _prorate_amount(a: TaxAdjustment, year: int, current_month: int) -> float:
    """当年汇算时，对超出当前月份的调整项做比例折算。

    仅对当年（year == 当前年）生效：超出 current_month 的部分不计入。
    对往年年份返回全额。
    对没有 period 的项返回全额。
    """
    if year != datetime.now().year:
        return a.amount or 0
    if not a.period_from or not a.period_to or not a.amount:
        return a.amount or 0

    try:
        from_m = int(a.period_from.split('-')[1])
        to_m = int(a.period_to.split('-')[1])
    except (IndexError, ValueError):
        return a.amount or 0

    # 全部在已过月份内 → 全额
    if to_m <= current_month:
        return a.amount
    # 全部在未来 → 不计
    if from_m > current_month:
        return 0.0

    # 部分跨月：按月份比例折算
    total_m = to_m - from_m + 1
    effective_m = current_month - from_m + 1

    if a.monthly_amount:
        return round(a.monthly_amount * effective_m, 2)
    else:
        return round(a.amount * effective_m / total_m, 2)


@router.get("/tax-summary", response_model=SalaryTaxSummaryOut)
def salary_tax_summary(
    year: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """按年计算个税汇算汇总（含综合汇算调整项）"""
    if year is None:
        year = datetime.now().year

    # ── 1. 计算薪资基础数据 ──
    records = (
        db.query(SalaryRecord)
        .filter(SalaryRecord.period.like(f"{year}%"))
        .order_by(SalaryRecord.period.asc())
        .all()
    )

    total_gross = 0.0
    total_social_insurance = 0.0
    actual_tax_paid = 0.0
    month_count = len(records)

    for r in records:
        if r.actual_tax is not None:
            actual_tax_paid += r.actual_tax
        for i in r.items:
            if i.category == "income":
                total_gross += i.amount
            elif i.category == "deduction" and i.tax_deductible:
                total_social_insurance += i.amount

    # 减除费用：过去年份按整年，当年按实际月数
    deduction_months = 12 if year < datetime.now().year else (month_count or 1)
    deduction_fee = MONTHLY_DEDUCTION * deduction_months

    # ── 2. 加载调整项（当年按月份折算） ──
    adj_items = (
        db.query(TaxAdjustment)
        .filter(TaxAdjustment.year == year)
        .order_by(TaxAdjustment.category, TaxAdjustment.sort_order)
        .all()
    )

    current_month = datetime.now().month
    is_current_year = (year == datetime.now().year)

    other_income_included = 0.0
    special_deduction_total = 0.0
    other_deduction_total = 0.0
    tax_paid_from_adjustments = 0.0

    for a in adj_items:
        # 对当年数据做月份比例折算（超出当前月不计入）
        eff_amt = _prorate_amount(a, year, current_month) if is_current_year else (a.amount or 0)

        if a.category == "other_income":
            other_income_included += eff_amt
        elif a.category == "special_deduction":
            special_deduction_total += eff_amt
        elif a.category == "other_deduction":
            other_deduction_total += eff_amt
        if a.tax_paid:
            tax_paid_from_adjustments += a.tax_paid

    # ── 3. 综合计算 ──
    total_income = round(total_gross + other_income_included, 2)
    total_deductions = round(deduction_fee + total_social_insurance + special_deduction_total + other_deduction_total, 2)
    taxable_income = round(total_income - total_deductions, 2)

    # ── 4. 查找税率级距 ──
    bracket_min = bracket_max = 0.0
    tax_rate = 0.0
    quick_deduction = 0.0
    remaining_to_next = 36_000.0
    next_threshold = 36_000.0
    next_rate = 3.0

    if taxable_income > 0:
        prev_upper = 0
        bracket_index = -1
        for i, (upper, rate, qd) in enumerate(TAX_BRACKETS):
            if upper == 0 or taxable_income <= upper:
                bracket_index = i
                bracket_min = round(float(prev_upper), 2)
                bracket_max = upper if upper != 0 else 0.0
                tax_rate = rate
                quick_deduction = float(qd)
                break
            prev_upper = upper

        if bracket_index >= 0:
            upper_bound = TAX_BRACKETS[bracket_index][0]
            if upper_bound != 0 and taxable_income < upper_bound:
                remaining_to_next = round(upper_bound - taxable_income, 2)
                if bracket_index + 1 < len(TAX_BRACKETS):
                    nu, nr, _ = TAX_BRACKETS[bracket_index + 1]
                    next_threshold = nu if nu != 0 else 0.0
                    next_rate = nr
                else:
                    next_threshold = 0.0
                    next_rate = 0.0
            else:
                remaining_to_next = 0.0
                next_threshold = 0.0
                next_rate = 0.0
    elif taxable_income <= 0:
        remaining_to_next = round(36_000.0 + abs(taxable_income), 2)

    tax_rate_label = f"{tax_rate:.0f}%" if tax_rate == int(tax_rate) else f"{tax_rate:.1f}%"

    # ── 5. 税额 ──
    tax_payable = round(max(taxable_income * (tax_rate / 100) - quick_deduction, 0), 2)
    actual_tax_paid = round(actual_tax_paid + tax_paid_from_adjustments, 2)
    tax_difference = round(tax_payable - actual_tax_paid, 2)

    # ── 6. 构建响应 ──
    adjustments_out = []
    for a in adj_items:
        adjustments_out.append(TaxAdjustmentOut(
            id=a.id, year=a.year, category=a.category,
            item_type=a.item_type, label=a.label or '',
            period_from=a.period_from or '', period_to=a.period_to or '',
            monthly_amount=a.monthly_amount or 0,
            tax_paid=a.tax_paid or 0,
            original_amount=a.original_amount,
            amount=a.amount, remark=a.remark, sort_order=a.sort_order,
        ))

    return SalaryTaxSummaryOut(
        year=year,
        month_count=month_count,
        total_gross=round(total_gross, 2),
        total_social_insurance=round(total_social_insurance, 2),
        actual_tax_paid=actual_tax_paid,
        deduction_fee=round(deduction_fee, 2),
        other_income_included=round(other_income_included, 2),
        special_deduction_total=round(special_deduction_total, 2),
        other_deduction_total=round(other_deduction_total, 2),
        total_income=total_income,
        total_deductions=total_deductions,
        taxable_income=taxable_income,
        tax_rate=tax_rate,
        tax_rate_label=tax_rate_label,
        bracket_min=bracket_min,
        bracket_max=bracket_max,
        quick_deduction=quick_deduction,
        remaining_to_next=remaining_to_next,
        next_bracket_threshold=next_threshold,
        next_tax_rate=next_rate,
        tax_payable=tax_payable,
        tax_difference=tax_difference,
        adjustments=adjustments_out,
    )


# ── 个税汇算调整项 CRUD ──

@router.get("/tax-adjustments", response_model=List[TaxAdjustmentOut])
def list_tax_adjustments(
    year: int = Query(..., description="年份"),
    db: Session = Depends(get_db),
):
    """获取指定年份的所有个税调整项"""
    items = (
        db.query(TaxAdjustment)
        .filter(TaxAdjustment.year == year)
        .order_by(TaxAdjustment.category, TaxAdjustment.sort_order)
        .all()
    )
    return items


@router.post("/tax-adjustments", response_model=TaxAdjustmentOut)
def create_tax_adjustment(
    data: TaxAdjustmentCreate,
    db: Session = Depends(get_db),
):
    """创建个税调整项"""
    item = TaxAdjustment(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/tax-adjustments/{item_id}", response_model=TaxAdjustmentOut)
def update_tax_adjustment(
    item_id: int,
    data: TaxAdjustmentUpdate,
    db: Session = Depends(get_db),
):
    """更新个税调整项"""
    item = db.query(TaxAdjustment).filter(TaxAdjustment.id == item_id).first()
    if not item:
        raise HTTPException(404, "调整项不存在")
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/tax-adjustments/{item_id}")
def delete_tax_adjustment(
    item_id: int,
    db: Session = Depends(get_db),
):
    """删除个税调整项"""
    item = db.query(TaxAdjustment).filter(TaxAdjustment.id == item_id).first()
    if not item:
        raise HTTPException(404, "调整项不存在")
    db.delete(item)
    db.commit()
    return {"ok": True}


def _cumulate_for_tax(items):
    """从明细列表计算收入总额与专项扣除（按名称过滤社保公积金，不含其他扣款）"""
    income = 0.0
    social = 0.0
    for it in items:
        amt = it.amount or 0.0
        if it.category == "income":
            income += amt
        elif it.category == "deduction" and it.tax_deductible:
            social += amt
    return round(income, 2), round(social, 2)


@router.post("/calc-tax")
def calc_tax(body: SalaryCalcTaxIn, db: Session = Depends(get_db)):
    """根据当前填写明细 + 本年度历史记录（累计预扣法），计算本月应扣个税。

    累计预扣法：
        累计应纳税所得额 = 累计收入 − 累计减除费用(5000×月数) − 累计专项扣除
        累计应预扣预缴税额 = 累计应纳税所得额 × 税率 − 速算扣除数
        本月应预扣预缴税额 = 累计应预扣预缴税额 − 本年已累计预扣预缴税额
    """
    year_str = body.period[:4]
    if not year_str.isdigit():
        return {"tax_amount": 0.0}
    year = int(year_str)

    # 查询本年历史记录（编辑模式排除自身）
    q = db.query(SalaryRecord).filter(SalaryRecord.period.like(f"{year}%"))
    if body.edit_id:
        q = q.filter(SalaryRecord.id != body.edit_id)
    prev_records = q.order_by(SalaryRecord.period.asc()).all()

    # 累计历史数据
    prev_income = 0.0
    prev_social = 0.0
    prev_actual_tax = 0.0
    prev_month_count = 0

    for r in prev_records:
        for i in r.items:
            if i.category == "income":
                prev_income += i.amount
            elif i.category == "deduction" and i.tax_deductible:
                prev_social += i.amount
        if body.use_items:
            # 从历史明细行 category=tax 汇总个税（往期理论计算）
            tax_from_items = sum(round(i.amount, 2) for i in r.items if i.category == "tax")
            prev_actual_tax = round(prev_actual_tax + tax_from_items, 2)
        else:
            prev_actual_tax += r.actual_tax or 0.0
        prev_month_count += 1
    prev_income = round(prev_income, 2)
    prev_social = round(prev_social, 2)

    # 当月数据
    cur_income, cur_social = _cumulate_for_tax(body.items)

    # 累计计算
    cumulative_income = prev_income + cur_income
    cumulative_months = prev_month_count + 1
    cumulative_deduction = prev_social + cur_social
    cumulative_taxable = round(
        cumulative_income - MONTHLY_DEDUCTION * cumulative_months - cumulative_deduction, 2
    )

    if cumulative_taxable <= 0:
        tax_amount = 0.0
    else:
        # 查税率表
        for upper, rate, qd in TAX_BRACKETS:
            if upper == 0 or cumulative_taxable <= upper:
                cumulative_tax_due = round(cumulative_taxable * rate / 100 - qd, 2)
                break
        else:
            cumulative_tax_due = 0.0

        tax_amount = round(max(cumulative_tax_due - prev_actual_tax, 0), 2)

    return {"tax_amount": tax_amount}


# ──────────────────────────────────────────────── 薪资导出 ────────────────────────────────────────────────

@router.get("/export")
def export_salary(
    period_from: Optional[str] = Query(None, description="开始月份 (YYYY-MM)"),
    period_to: Optional[str] = Query(None, description="结束月份 (YYYY-MM)"),
    db: Session = Depends(get_db),
):
    """导出薪资记录 DOCX 报告：含明细表、总览合计、五险一金基数比例变化。"""
    try:
        # 查询记录
        q = db.query(SalaryRecord)
        if period_from:
            q = q.filter(SalaryRecord.period >= period_from)
        if period_to:
            q = q.filter(SalaryRecord.period <= period_to)
        records = q.order_by(SalaryRecord.period.asc()).all()

        # 统计汇总
        tg = tp = tn = tc = tcrd = tact = 0.0
        for r in records:
            g = sum(i.amount for i in r.items if i.category == "income")
            pd = sum(i.amount for i in r.items if i.category in ("deduction", "tax"))
            cc = sum(i.amount for i in r.items if i.category == "company_cost")
            tg += g
            tp += pd
            tn += g - pd
            tc += cc
            tcrd += r.credited_amount or 0.0
            tact += r.actual_tax or 0.0
        count = len(records)
        summary = {
            "record_count": count,
            "total_gross": round(tg, 2),
            "total_personal_deduction": round(tp, 2),
            "total_net": round(tn, 2),
            "total_company_cost": round(tc, 2),
            "avg_net": round(tn / count, 2) if count else 0.0,
            "total_credited": round(tcrd, 2),
            "total_actual_tax": round(tact, 2),
        }

        # 个税汇算摘要
        tax_summary = None
        if records:
            last_year = int(records[-1].period[:4])
            # 选取有完整数据的最后一年
            target_year = last_year
            year_records = [r for r in records if r.period.startswith(str(target_year))]
            if year_records:
                total_gross = 0.0
                total_social = 0.0
                for r in year_records:
                    for i in r.items:
                        if i.category == "income":
                            total_gross += i.amount
                        elif i.category == "deduction" and i.tax_deductible:
                            total_social += i.amount
                month_count = len(year_records)
                taxable = round(total_gross - 5000 * 12 - total_social, 2)

                # 税率级距查找（TAX_BRACKETS 定义在本模块顶部）
                tax_rate = 0.0
                qd = 0.0
                if taxable > 0:
                    for upper, rate, quick_d in TAX_BRACKETS:
                        if upper == 0 or taxable <= upper:
                            tax_rate = rate
                            qd = quick_d
                            break

                tax_summary = {
                    "year": target_year,
                    "month_count": month_count,
                    "total_gross": round(total_gross, 2),
                    "total_social_insurance": round(total_social, 2),
                    "taxable_income": taxable,
                    "tax_rate_label": f"{tax_rate:.0f}%",
                    "quick_deduction": round(qd, 2),
                }

        # 配置信息
        from ..settings_manager import load_settings
        raw_cfg = load_settings().get("salary_config", {})
        salary_config = {
            "employer": raw_cfg.get("employer", ""),
            "social_bases": raw_cfg.get("social_bases", {}),
            "social_rates": raw_cfg.get("social_rates", {}),
        }

        xlsx_bytes = generate_salary_export(
            db, records, period_from, period_to,
            summary, tax_summary, salary_config,
        )

        # 文件名
        pf = period_from or "earliest"
        pt = period_to or "latest"
        file_ts = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f'薪资导出_{pf}_{pt}_{file_ts}.xlsx'
        encoded_filename = urllib.parse.quote(filename)

        return Response(
            content=xlsx_bytes,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}",
                'Content-Length': str(len(xlsx_bytes)),
            }
        )
    except Exception as e:
        raise HTTPException(500, f"导出失败: {str(e)}")


# ──────────────────────────────────────────────── 薪资通用配置 ────────────────────────────────────────────────

def _merge_config(raw: dict) -> dict:
    """用默认值补齐缺失键，保证返回结构稳定"""
    cfg = dict(DEFAULT_SALARY_CONFIG)
    if isinstance(raw, dict):
        cfg.update({k: v for k, v in raw.items() if k in DEFAULT_SALARY_CONFIG})
    # 比例字段再补一层缺省，防止旧配置缺某项
    rates = dict(DEFAULT_SALARY_CONFIG["social_rates"])
    if isinstance(cfg.get("social_rates"), dict):
        rates.update(cfg["social_rates"])
    cfg["social_rates"] = rates
    # 各项缴费基数同样分项补齐
    bases = dict(DEFAULT_SALARY_CONFIG.get("social_bases") or {})
    if isinstance(cfg.get("social_bases"), dict):
        bases.update(cfg["social_bases"])
    cfg["social_bases"] = bases
    return cfg


@router.get("/config", response_model=SalaryConfigOut)
def get_salary_config():
    """读取薪资通用配置（缴费基数/比例/默认单位/默认收入项等）"""
    return _merge_config(load_settings().get("salary_config", {}))


@router.put("/config", response_model=SalaryConfigOut)
def update_salary_config(body: SalaryConfigUpdate):
    """更新薪资通用配置"""
    current = _merge_config(load_settings().get("salary_config", {}))
    data = {}
    if body.employer is not None:
        data["employer"] = str(body.employer)
    if body.social_bases is not None:
        if not isinstance(body.social_bases, dict):
            raise HTTPException(400, "social_bases 必须为对象")
        # 各项缴费基数分项配置（各项最低基数不同），取值须为非负数
        bases = {}
        for k in SOCIAL_RATE_KEYS:
            if k in body.social_bases:
                v = body.social_bases[k]
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    continue
                if v < 0:
                    raise HTTPException(400, f"{k} 缴费基数不能为负")
                bases[k] = round(v, 2)
        data["social_bases"] = bases
    if body.social_rates is not None:
        if not isinstance(body.social_rates, dict):
            raise HTTPException(400, "social_rates 必须为对象")
        # 只保留标准键，且取值范围合理（0~100%）
        rates = {}
        for k in SOCIAL_RATE_KEYS:
            if k in body.social_rates:
                v = body.social_rates[k]
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    continue
                if 0 <= v <= 100:
                    rates[k] = round(v, 4)
        data["social_rates"] = rates
    if body.default_pay_day is not None:
        if not (1 <= body.default_pay_day <= 31):
            raise HTTPException(400, "默认发放日必须在 1~31 之间")
        data["default_pay_day"] = int(body.default_pay_day)
    if body.default_pay_month is not None:
        if body.default_pay_month not in ("current", "next"):
            raise HTTPException(400, "default_pay_month 仅支持 current（当月）或 next（次月）")
        data["default_pay_month"] = body.default_pay_month
    if body.default_income_items is not None:
        if not isinstance(body.default_income_items, list):
            raise HTTPException(400, "default_income_items 必须为数组")
        items = []
        for it in body.default_income_items:
            if isinstance(it, dict) and it.get("name"):
                items.append({
                    "name": str(it.get("name")),
                    "amount": float(it.get("amount") or 0),
                })
        data["default_income_items"] = items
    merged = _merge_config({**current, **data})
    save_settings({"salary_config": merged})
    return merged
