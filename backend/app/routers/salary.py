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
from datetime import datetime, date
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db, SalaryRecord, SalaryItem
from ..schemas import (
    SalaryRecordCreate,
    SalaryRecordOut,
    SalaryItemOut,
    SalarySummaryOut,
    SalaryTaxSummaryOut,
    SalaryCalcTaxIn,
    SalaryConfigOut,
    SalaryConfigUpdate,
)
from ..schemas import VALID_SALARY_CATEGORIES
from ..settings_manager import load_settings, save_settings

router = APIRouter(prefix="/salary")

# 五险一金比例的标准键（与前端 SOCIAL_TEMPLATE 名称保持一致）
SOCIAL_RATE_KEYS = [
    "养老保险(个人)", "医疗保险(个人)", "失业保险(个人)", "住房公积金(个人)",
    "养老保险(公司)", "医疗保险(公司)", "失业保险(公司)",
    "工伤保险(公司)", "生育保险(公司)", "住房公积金(公司)",
]
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


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _compute_totals(record):
    """返回 (gross, personal_deduction, net, company_cost)"""
    gross = sum(i.amount for i in record.items if i.category == "income")
    personal_deduction = sum(i.amount for i in record.items if i.category in ("deduction", "tax"))
    company_cost = sum(i.amount for i in record.items if i.category == "company_cost")
    net = gross - personal_deduction
    return gross, personal_deduction, net, company_cost


def _to_out(record: SalaryRecord) -> SalaryRecordOut:
    gross, pd, net, cc = _compute_totals(record)
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
                sort_order=i.sort_order,
            )
            for i in sorted(record.items, key=lambda x: x.sort_order)
        ],
        gross=round(gross, 2),
        personal_deduction=round(pd, 2),
        net=round(net, 2),
        company_cost=round(cc, 2),
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


def _make_salary_item(it, idx, salary_record_id=None):
    """构造一条 SalaryItem（自动换算 amount 并保留 base/rate）"""
    return SalaryItem(
        salary_record_id=salary_record_id,
        category=it.category,
        name=it.name,
        amount=_item_amount(it),
        base=it.base,
        rate=it.rate,
        funded_by=it.funded_by or "",
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
    db.delete(rec)
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
        g, pd, net, cc = _compute_totals(r)
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


@router.get("/tax-summary", response_model=SalaryTaxSummaryOut)
def salary_tax_summary(
    year: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """按年计算个税汇算汇总：累计应纳税所得额、适用税率、距下一级距剩余额度"""
    if year is None:
        year = datetime.now().year

    records = (
        db.query(SalaryRecord)
        .filter(SalaryRecord.period.like(f"{year}%"))
        .order_by(SalaryRecord.period.asc())
        .all()
    )

    if not records:
        return SalaryTaxSummaryOut(
            year=year,
            month_count=0,
            total_gross=0.0,
            total_social_insurance=0.0,
            taxable_income=0.0,
            tax_rate=0.0,
            tax_rate_label="0%",
            bracket_min=0.0,
            bracket_max=0.0,
            quick_deduction=0.0,
            remaining_to_next=36_000.0,
            next_bracket_threshold=36_000.0,
            next_tax_rate=3.0,
        )

    total_gross = 0.0
    total_social_insurance = 0.0
    month_count = len(records)

    for r in records:
        for i in r.items:
            if i.category == "income":
                total_gross += i.amount
            elif i.category == "deduction":
                total_social_insurance += i.amount

    # 应纳税所得额 = 年度累计应发 - 累计减除费用(5000×月份数) - 累计专项扣除(社保公积金个人)
    taxable_income = round(total_gross - MONTHLY_DEDUCTION * month_count - total_social_insurance, 2)

    # 查找对应的个税级距
    bracket_index = -1
    tax_rate = 0.0
    quick_deduction = 0.0

    if taxable_income <= 0:
        # 未达起征点（甚至亏损），适用 0%
        bracket_min, bracket_max = 0.0, 36_000.0
        remaining_to_next = round(36_000.0 + abs(taxable_income), 2)
        next_threshold = 36_000.0
        next_rate = 3.0
    else:
        prev_upper = 0
        for i, (upper, rate, qd) in enumerate(TAX_BRACKETS):
            if upper == 0 or taxable_income <= upper:
                bracket_index = i
                bracket_min = prev_upper
                bracket_max = upper if upper != 0 else float('inf')
                tax_rate = rate
                quick_deduction = qd
                break
            prev_upper = upper

        # 计算距下一级距额度
        if bracket_max != float('inf') and taxable_income < bracket_max:
            # 还在这一级距内，有下一级
            remaining_to_next = round(bracket_max - taxable_income, 2)
            # 下一级的信息
            if bracket_index + 1 < len(TAX_BRACKETS):
                nu, nr, _ = TAX_BRACKETS[bracket_index + 1]
                next_threshold = nu if nu != 0 else float('inf')
                next_rate = nr
            else:
                next_threshold = 0.0
                next_rate = 0.0
        else:
            # 已在本级上限或已是最高级
            remaining_to_next = 0.0
            next_threshold = 0.0
            next_rate = 0.0

    tax_rate_label = f"{tax_rate:.0f}%" if tax_rate == int(tax_rate) else f"{tax_rate:.1f}%"

    return SalaryTaxSummaryOut(
        year=year,
        month_count=month_count,
        total_gross=round(total_gross, 2),
        total_social_insurance=round(total_social_insurance, 2),
        taxable_income=taxable_income,
        tax_rate=tax_rate,
        tax_rate_label=tax_rate_label,
        bracket_min=round(bracket_min, 2),
        bracket_max=round(bracket_max, 2) if bracket_max != float('inf') else 0.0,
        quick_deduction=round(quick_deduction, 2),
        remaining_to_next=remaining_to_next,
        next_bracket_threshold=round(next_threshold, 2) if next_threshold != float('inf') else 0.0,
        next_tax_rate=next_rate,
    )


def _cumulate_for_tax(items):
    """从明细列表计算收入总额与专项扣除"""
    income = 0.0
    social = 0.0
    for it in items:
        amt = it.amount or 0.0
        if it.category == "income":
            income += amt
        elif it.category == "deduction":
            social += amt
    return income, social


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
            elif i.category == "deduction":
                prev_social += i.amount
        prev_actual_tax += r.actual_tax or 0.0
        prev_month_count += 1

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
