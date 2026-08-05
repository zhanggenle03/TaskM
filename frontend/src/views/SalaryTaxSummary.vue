<template>
  <div>
    <div class="page-header">
      <div style="display:flex;align-items:center;gap:12px">
        <el-button text @click="$router.push('/salary')">
          <el-icon><ArrowLeft /></el-icon>
        </el-button>
        <div>
          <h1 class="page-title">个税汇算</h1>
          <p class="page-sub">综合所得年度汇算清缴</p>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:12px">
        <el-tooltip content="勾选后，非计税收入（转账等）也并入综合所得收入额参与计税计算" placement="bottom">
          <el-checkbox v-model="includeNontax" size="small">含非计税</el-checkbox>
        </el-tooltip>
        <el-select v-model="taxYear" size="small" style="width:100px">
          <el-option v-for="y in taxYears" :key="y" :label="`${y} 年`" :value="y" />
        </el-select>
      </div>
    </div>

    <div v-if="!loaded && loading" style="text-align:center;padding:80px 0">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p style="color:#999;margin-top:12px">加载中…</p>
    </div>
    <div v-else-if="!loaded" style="text-align:center;padding:80px 0">
      <el-empty description="暂无该年份薪资数据" :image-size="100" />
    </div>

    <template v-if="loaded">
      <!-- KPI 卡片 -->
      <div class="kpi-grid">
        <div class="kpi-card kpi-gross">
          <div class="kpi-label">综合所得收入额</div>
          <div class="kpi-value">{{ fmt(ps.total_income) }}</div>
          <div class="kpi-sub">
            <span>薪资 {{ fmt(base.total_gross) }}</span>
            <span v-if="ps.other_income_included > 0"> + 其他 {{ fmt(ps.other_income_included) }}</span>
            <span v-if="includeNontax && ps.non_taxable_income > 0"> + 非计税 {{ fmt(ps.non_taxable_income) }}</span>
          </div>
        </div>
        <div class="kpi-card kpi-nontax">
          <div class="kpi-label">非计税收入</div>
          <div class="kpi-value">{{ fmt(ps.non_taxable_income) }}</div>
          <div class="kpi-sub">
            <span>合计收入 {{ fmt(ps.total_income_all) }}</span>
          </div>
        </div>
        <div class="kpi-card kpi-deduct">
          <div class="kpi-label">累计减除费用</div>
          <div class="kpi-value">{{ fmt(ps.deduction_fee) }}</div>
        </div>
        <div class="kpi-card kpi-insurance">
          <div class="kpi-label">各项扣除合计</div>
          <div class="kpi-value">{{ fmt(ps.total_deductions - ps.deduction_fee) }}</div>
          <div class="kpi-sub">
            <span>社保专项 {{ fmt(base.total_social_insurance) }}</span>
            <span v-if="ps.special_deduction_total > 0"> + 附加 {{ fmt(ps.special_deduction_total) }}</span>
            <span v-if="ps.other_deduction_total > 0"> + 其他 {{ fmt(ps.other_deduction_total) }}</span>
          </div>
        </div>
      </div>

      <div class="detail-grid">
        <div class="detail-card">
          <div class="detail-title">应纳税额计算</div>
          <div class="detail-body">
            <div class="detail-row">
              <span class="detail-label">应纳税所得额</span>
              <span class="detail-value" :class="taxableClass">{{ fmt(ps.taxable_income) }}</span>
            </div>
            <div class="detail-divider"></div>
            <div class="detail-row">
              <span class="detail-label">当前税率</span>
              <span class="detail-value detail-tax-rate">{{ ps.tax_rate_label }}</span>
            </div>
            <div class="detail-divider"></div>
            <div class="detail-row">
              <span class="detail-label">距下一级距</span>
              <span class="detail-value" v-if="ps.remaining_to_next > 0" style="color:#67C23A">{{ fmt(ps.remaining_to_next) }}</span>
              <span class="detail-value" v-else style="color:#909399">已达最高级</span>
            </div>
          </div>
        </div>
        <div class="detail-card">
          <div class="detail-title">税额对比</div>
          <div class="detail-body">
            <div class="detail-row">
              <span class="detail-label">应交税额</span>
              <span class="detail-value" :class="taxPayableClass">{{ fmt(ps.tax_payable) }}</span>
            </div>
            <div class="detail-divider"></div>
            <div class="detail-row">
              <span class="detail-label">实缴税额</span>
              <span class="detail-value">{{ fmt(ps.actual_tax_paid) }}</span>
            </div>
            <div class="detail-divider"></div>
            <div class="detail-row">
              <span class="detail-label">差值（应缴−实缴）</span>
              <span class="detail-value" :class="diffClass">{{ fmt(ps.tax_difference) }}</span>
            </div>
            <div class="diff-hint" v-if="ps.tax_difference !== 0">
              {{ ps.tax_difference > 0 ? '⚠️ 欠缴，需补税' : '✅ 多缴，可退税' }}
            </div>
          </div>
        </div>
      </div>

      <!-- ── 调整项管理（统一添加 + 展示列表） ── -->
      <div class="adj-section">
        <div class="adj-header">
          <span class="adj-title">收入与扣除调整项</span>
          <div class="adj-actions">
            <el-button size="small" type="primary" @click="openAdd">+ 添加</el-button>
            <el-button size="small" :loading="savingAll" @click="saveAllRows">保存全部</el-button>
          </div>
        </div>

        <div v-if="currentRows.length === 0" class="adj-empty">
          暂无调整项，点击「+ 添加」新增
        </div>

        <!-- 按分类展示 -->
        <template v-for="cat in categories" :key="cat.key">
          <div v-if="grouped[cat.key].length > 0" class="adj-group">
            <div class="adj-group-title">{{ cat.label }} <span class="adj-group-total">小计 {{ fmt(sectionTotal(cat.key)) }}</span></div>
            <div
              v-for="item in grouped[cat.key]"
              :key="item._key"
              class="adj-item"
            >
              <div class="adj-item-main">
                <span class="adj-item-type">{{ typeLabel(item) }}</span>
                <span v-if="item.label" class="adj-item-label">{{ item.label }}</span>
                <span class="adj-item-period" v-if="item.period_from">{{ item.period_from }} ~ {{ item.period_to }}</span>
                <span class="adj-item-detail-inline" v-if="item.category === 'other_income' && item.original_amount">
                  · 原始 {{ fmt(item.original_amount) }} × {{ typeRate(item) * 100 }}%
                </span>
                <span class="adj-item-detail-inline" v-if="item.tax_paid > 0">
                  · 已缴税 {{ fmt(item.tax_paid) }}
                </span>
                <span class="adj-item-detail-inline" v-else-if="item.category !== 'other_income' && item.monthly_amount > 0">
                  · 月 {{ fmt(item.monthly_amount) }} × {{ periodMonths(item) }} 月
                </span>
                <span v-if="showProrate(item)" class="adj-item-prorate">按已录入 {{ dataMonth }} 月折算 {{ fmt(prorateAmt(item)) }}</span>
                <span class="adj-item-amt">{{ fmt(item.amount || 0) }}</span>
                <div class="adj-item-actions">
                  <el-button text size="small" @click="editItem(item)">编辑</el-button>
                  <el-button text size="small" type="danger" @click="deleteItem(item)">删除</el-button>
                </div>
              </div>
            </div>
          </div>
        </template>

        <div v-if="currentRows.length > 0" class="adj-footer">
          <span>其他收入：<b>{{ fmt(sectionTotal('other_income')) }}</b></span>
          <span>专项附加扣除：<b>{{ fmt(sectionTotal('special_deduction')) }}</b></span>
          <span>其他扣除：<b>{{ fmt(sectionTotal('other_deduction')) }}</b></span>
        </div>
      </div>
    </template>

    <!-- ── 统一添加/编辑对话框 ── -->
    <el-dialog v-model="dlg.visible" :title="dlg.title" width="680px" :close-on-click-modal="false">
      <el-form :model="form" label-position="top" size="small">
        <div class="dlg-row2">
          <el-form-item label="分类" required>
            <el-select v-model="form.category" style="width:100%" @change="onCatChange">
              <el-option label="其他综合所得收入" value="other_income" />
              <el-option label="专项附加扣除" value="special_deduction" />
              <el-option label="其他扣除" value="other_deduction" />
            </el-select>
          </el-form-item>
          <el-form-item label="类型" required>
            <el-select v-model="form.item_type" style="width:100%">
              <el-option v-for="(lb, k) in typeOpts[form.category] || {}" :key="k" :label="lb" :value="k" />
            </el-select>
          </el-form-item>
        </div>

        <el-form-item label="标签（可选）">
          <el-input v-model="form.label" placeholder="如 上半年租金、某次劳务报酬" clearable />
        </el-form-item>

        <div class="dlg-row2">
          <el-form-item label="起始月份" required>
            <el-date-picker v-model="form.period_from" type="month" format="YYYY-MM" value-format="YYYY-MM" placeholder="选择起始月" style="width:100%" @change="recalc" />
          </el-form-item>
          <el-form-item label="结束月份" required>
            <el-date-picker v-model="form.period_to" type="month" format="YYYY-MM" value-format="YYYY-MM" placeholder="选择结束月" style="width:100%" @change="recalc" />
          </el-form-item>
        </div>

        <!-- 跨年提示 -->
        <div v-if="crossYearNotice" class="cross-year-notice">
          <el-icon><WarningFilled /></el-icon> {{ crossYearNotice }}
        </div>

        <!-- 收入项 -->
        <template v-if="form.category === 'other_income'">
          <div class="dlg-row3">
            <el-form-item label="原始收入金额">
              <el-input-number v-model="form.original_amount" :min="0" :precision="2" :step="1000" style="width:100%" controls-position="right" @change="recalc" />
              <div class="form-hint">未扣税前金额</div>
            </el-form-item>
            <el-form-item label="计入综合所得">
              <el-input-number :model-value="computedIncome" disabled :precision="2" style="width:100%" />
              <div class="form-hint">已 × {{ typeRateByKey(form.item_type) * 100 }}%</div>
            </el-form-item>
            <el-form-item label="已预缴个税">
              <el-input-number v-model="form.tax_paid" :min="0" :precision="2" :step="100" style="width:100%" controls-position="right" />
              <div class="form-hint">发放时已扣缴</div>
            </el-form-item>
          </div>
        </template>

        <!-- 扣除项 -->
        <template v-else>
          <div class="dlg-row2">
            <el-form-item label="月金额（可选）">
              <el-input-number v-model="form.monthly_amount" :min="0" :precision="2" :step="500" style="width:100%" controls-position="right" @change="recalc" />
              <div class="form-hint">填月金额后自动按时间段算总额</div>
            </el-form-item>
            <el-form-item label="总金额（汇算时计入）" required>
              <el-input-number v-model="form.amount" :min="0" :precision="2" :step="1000" style="width:100%" controls-position="right" />
            </el-form-item>
          </div>
        </template>
      </el-form>

      <template #footer>
        <el-button size="small" @click="dlg.visible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="dlg.saving" @click="confirmDlg">{{ dlg.mode === 'add' ? '添加' : '保存修改' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { WarningFilled } from '@element-plus/icons-vue'
import {
  getSalaryTaxSummary, getSalaryYears,
  createTaxAdjustment, updateTaxAdjustment, deleteTaxAdjustment,
} from '../api'

const fmt = (n) => '¥' + Number(n || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

// ── 类型常量 ──
const categories = [
  { key: 'other_income', label: '其他综合所得收入' },
  { key: 'special_deduction', label: '专项附加扣除' },
  { key: 'other_deduction', label: '其他扣除' },
]

const typeOpts = {
  other_income: {
    labor_service: '劳务报酬',
    remuneration: '稿酬',
    royalty: '特许权使用费',
  },
  special_deduction: {
    children_education: '子女教育',
    continuing_education: '继续教育',
    medical_treatment: '大病医疗',
    housing_loan_interest: '住房贷款利息',
    housing_rent: '住房租金',
    elderly_care: '赡养老人',
    infant_care: '3岁以下婴幼儿照护',
  },
  other_deduction: {
    enterprise_annuity: '企业年金/职业年金',
    commercial_health: '商业健康保险',
    deferred_pension: '税收递延型商业养老保险',
    other_deduction_other: '其他',
  },
}

const incomeRates = { labor_service: 0.80, remuneration: 0.56, royalty: 0.80 }

const TAX_BRACKETS = [
  { upper: 36000, rate: 3, qd: 0 },
  { upper: 144000, rate: 10, qd: 2520 },
  { upper: 300000, rate: 20, qd: 16920 },
  { upper: 420000, rate: 25, qd: 31920 },
  { upper: 660000, rate: 30, qd: 52920 },
  { upper: 960000, rate: 35, qd: 85920 },
  { upper: Infinity, rate: 45, qd: 181920 },
]

// ── 状态 ──
const taxSummary = ref(null)
const loading = ref(false)
const loaded = ref(false)
const taxYear = ref(new Date().getFullYear())
const taxYears = ref([])
const includeNontax = ref(false)
const savingAll = ref(false)
const rows = ref([])
let _keySeq = 0

// 当前年份（用于当年折算判断）；折算截止月优先用薪资数据最新月份（后端 data_month）
const nowDate = new Date()
const currentYear = nowDate.getFullYear()
const dataMonth = computed(() => taxSummary.value?.data_month || (nowDate.getMonth() + 1))

function showProrate(item) {
  if (taxYear.value !== currentYear) return false
  if (!item.period_from || !item.period_to) return false
  const tm = parseInt(item.period_to.split('-')[1])
  return !isNaN(tm) && tm > dataMonth.value
}

function prorateAmt(item) {
  if (!showProrate(item) || !item.amount) return 0
  const fm = parseInt(item.period_from.split('-')[1])
  const tm = parseInt(item.period_to.split('-')[1])
  const total = tm - fm + 1
  const eff = Math.max(0, dataMonth.value - fm + 1)
  if (item.monthly_amount) return Math.round(item.monthly_amount * eff * 100) / 100
  return Math.round(item.amount * eff / total * 100) / 100
}

const dlg = reactive({ visible: false, mode: 'add', saving: false, editTarget: null })
const defaultForm = () => ({
  category: 'other_income',
  item_type: 'labor_service',
  label: '',
  period_from: null,
  period_to: null,
  monthly_amount: 0,
  tax_paid: 0,
  original_amount: null,
  amount: 0,
})
const form = reactive(defaultForm())

// ── 基础值 ──
const base = computed(() => taxSummary.value || { total_gross: 0, non_taxable_income: 0, total_social_insurance: 0, actual_tax_paid: 0, deduction_fee: 0, month_count: 0 })

// 按当前年份过滤
const currentRows = computed(() => rows.value.filter(r => r.year === taxYear.value))

// ── 预览汇算（仅当前年份，超出当前月的部分折算） ──
const ps = computed(() => {
  const b = base.value
  const isCurYear = (taxYear.value === currentYear)

  // 当年月份比例折算（截止到薪资数据最新月份）
  function effAmt(r) {
    if (!isCurYear || !r.period_from || !r.period_to || !r.amount) return r.amount || 0
    const fm = parseInt(r.period_from.split('-')[1])
    const tm = parseInt(r.period_to.split('-')[1])
    if (isNaN(fm) || isNaN(tm)) return r.amount || 0
    if (tm <= dataMonth.value) return r.amount
    if (fm > dataMonth.value) return 0
    const total = tm - fm + 1
    const eff = dataMonth.value - fm + 1
    if (r.monthly_amount) return Math.round(r.monthly_amount * eff * 100) / 100
    return Math.round(r.amount * eff / total * 100) / 100
  }

  let oi = 0, sd = 0, od = 0
  for (const r of currentRows.value) {
    const a = effAmt(r)
    if (r.category === 'other_income') oi += a
    else if (r.category === 'special_deduction') sd += a
    else if (r.category === 'other_deduction') od += a
  }
  const nonTax = b.non_taxable_income || 0
  const totalIncome = b.total_gross + oi + (includeNontax.value ? nonTax : 0)
  const totalD = b.deduction_fee + b.total_social_insurance + sd + od
  const taxable = Math.max(0, totalIncome - totalD)
  let tr = 0, qd = 0, remain = 36000
  if (taxable > 0) {
    for (const bk of TAX_BRACKETS) {
      if (taxable <= bk.upper) { tr = bk.rate; qd = bk.qd; if (bk.upper !== Infinity && taxable < bk.upper) remain = bk.upper - taxable; else remain = 0; break }
    }
  } else { remain = 36000 + Math.abs(taxable) }
  const tp = Math.max(0, Math.round((taxable * tr / 100 - qd) * 100) / 100)
  // 实际已缴税额 = 薪资个税（来自后端）+ 各调整项已预缴税额
  let actualTax = b.actual_tax_paid || 0
  for (const r of currentRows.value) {
    if (r.tax_paid) actualTax += r.tax_paid
  }
  const at = Math.round(actualTax * 100) / 100
  return {
    total_income: Math.round(totalIncome * 100) / 100,
    non_taxable_income: Math.round(nonTax * 100) / 100,
    total_income_all: Math.round((b.total_gross + oi + nonTax) * 100) / 100,
    total_deductions: Math.round(totalD * 100) / 100,
    deduction_fee: b.deduction_fee,
    other_income_included: Math.round(oi * 100) / 100,
    special_deduction_total: Math.round(sd * 100) / 100,
    other_deduction_total: Math.round(od * 100) / 100,
    taxable_income: Math.round(taxable * 100) / 100,
    tax_rate_label: Number.isInteger(tr) ? `${tr}%` : `${tr.toFixed(1)}%`,
    tax_payable: tp,
    actual_tax_paid: at,
    tax_difference: Math.round((tp - at) * 100) / 100,
    remaining_to_next: Math.round(remain * 100) / 100,
  }
})

const taxableClass = computed(() => {
  const t = ps.value.taxable_income; if (t <= 0) return 'tax-zero'; if (t <= 36000) return 'tax-low'; if (t <= 144000) return 'tax-mid'; return 'tax-high'
})
const taxPayableClass = computed(() => ps.value.tax_payable <= 0 ? 'tax-zero' : '')
const diffClass = computed(() => { const d = ps.value.tax_difference; if (d > 0) return 'tax-high'; if (d < 0) return 'tax-low'; return 'tax-zero' })

// 按分类分组展示（仅当前年份）
const grouped = computed(() => {
  const g = { other_income: [], special_deduction: [], other_deduction: [] }
  for (const r of currentRows.value) { if (g[r.category]) g[r.category].push(r) }
  return g
})

// 对话框跨年检测
const crossYearNotice = computed(() => {
  if (!form.period_from || !form.period_to) return ''
  const fy = parseInt(form.period_from.slice(0, 4))
  const ty = parseInt(form.period_to.slice(0, 4))
  if (ty > fy) {
    if (form.category === 'other_income') {
      return `时间段跨越 ${ty - fy} 年，收入项将归入起始年份 ${fy} 年`
    }
    return `时间段跨越 ${ty - fy} 年，将按月份自动拆分为 ${ty - fy + 1} 条记录，分别归入对应年份`
  }
  return ''
})

// 对话框内收入项自动计算
const computedIncome = computed(() => {
  const r = incomeRates[form.item_type] || 1
  return form.original_amount ? Math.round(form.original_amount * r * 100) / 100 : 0
})

// ── 工具函数 ──
function typeLabel(item) {
  const opts = typeOpts[item.category]
  return (opts && opts[item.item_type]) || item.item_type
}
function typeRate(item) { return incomeRates[item.item_type] || 0 }
function typeRateByKey(k) { return incomeRates[k] || 1 }
function periodMonths(item) {
  if (!item.period_from || !item.period_to) return 0
  const f = item.period_from.split('-').map(Number), t = item.period_to.split('-').map(Number)
  return (t[0] - f[0]) * 12 + (t[1] - f[1]) + 1
}
function sectionTotal(cat) { return currentRows.value.filter(r => r.category === cat).reduce((s, r) => s + (r.amount || 0), 0) }

function makeRow(data) {
  _keySeq++; return { _key: 'r' + _keySeq, _saving: false, id: null, year: taxYear.value, category: 'special_deduction', item_type: 'children_education', label: '', period_from: taxYear.value + '-01', period_to: taxYear.value + '-12', monthly_amount: 0, tax_paid: 0, original_amount: null, amount: 0, ...data }
}

// ── 对话框 ──
function openAdd() {
  dlg.mode = 'add'; dlg.title = '添加调整项'; dlg.editTarget = null; dlg.visible = true
  Object.assign(form, defaultForm())
}

function editItem(item) {
  dlg.mode = 'edit'; dlg.title = '编辑调整项'; dlg.editTarget = item; dlg.visible = true
  Object.assign(form, { category: item.category, item_type: item.item_type, label: item.label || '', period_from: item.period_from || (taxYear.value + '-01'), period_to: item.period_to || (taxYear.value + '-12'), monthly_amount: item.monthly_amount || 0, tax_paid: item.tax_paid || 0, original_amount: item.original_amount, amount: item.amount || 0 })
}

function onCatChange() {
  const opts = typeOpts[form.category]
  form.item_type = Object.keys(opts)[0] || ''
  recalc()
}

function recalc() {
  if (form.category === 'other_income') {
    const r = incomeRates[form.item_type] || 1
    form.amount = form.original_amount ? Math.round(form.original_amount * r * 100) / 100 : 0
  } else {
    const months = periodMonths(form)
    if (months > 0 && form.monthly_amount > 0) {
      form.amount = Math.round(form.monthly_amount * months * 100) / 100
    }
  }
}

function confirmDlg() {
  if (!form.category || !form.item_type) { ElMessage.warning('请选择分类和类型'); return }
  if (!form.period_from || !form.period_to) { ElMessage.warning('请选择起始和结束月份'); return }

  dlg.saving = true

  const fromYear = parseInt(form.period_from.slice(0, 4))
  const toYear = parseInt(form.period_to.slice(0, 4))

  // 构建待创建的 payload 列表（同一年=1条，跨年=拆分为多条）
  const payloads = buildPayloads()

  const promises = payloads.map(p => {
    if (dlg.mode === 'edit' && dlg.editTarget?.id) {
      return updateTaxAdjustment(dlg.editTarget.id, p)
    }
    return createTaxAdjustment(p)
  })

  Promise.all(promises).then(results => {
    const otherYears = []
    if (dlg.mode === 'add') {
      for (const res of results) {
        if (res.year === taxYear.value) {
          rows.value.push(makeRow(res))
        } else {
          otherYears.push(res.year)
        }
      }
    } else if (dlg.editTarget) {
      Object.assign(dlg.editTarget, results[0])
    }
    dlg.visible = false; dlg.saving = false
    let msg = dlg.mode === 'add' ? '已添加' : '已更新'
    if (results.length > 1) msg += `（拆分为 ${results.length} 条）`
    if (otherYears.length > 0) msg += `，${otherYears.join('/')} 年记录请切换年份查看`
    ElMessage.success(msg)
  }).catch(e => {
    dlg.saving = false
    ElMessage.error('操作失败：' + (e.message || e))
  })

  function buildPayloads() {
    if (fromYear === toYear) {
      return [makePayload(fromYear, form.period_from, form.period_to, form.amount)]
    }

    const fromP = form.period_from.split('-').map(Number)
    const toP = form.period_to.split('-').map(Number)
    const monthly = form.monthly_amount || 0
    const totalAmount = form.amount || 0

    // 收入项：归入起始年份
    if (form.category === 'other_income') {
      return [makePayload(fromYear, form.period_from, form.period_to, totalAmount)]
    }

    // 扣除项：按月份拆分
    const list = []

    if (monthly > 0) {
      // 首年
      const firstMonths = 12 - fromP[1] + 1
      list.push(makePayload(fromYear, form.period_from, `${fromYear}-12`, Math.round(monthly * firstMonths * 100) / 100))

      // 中间整年
      for (let y = fromYear + 1; y < toYear; y++) {
        list.push(makePayload(y, `${y}-01`, `${y}-12`, Math.round(monthly * 12 * 100) / 100))
      }

      // 末年
      const lastMonths = toP[1]
      list.push(makePayload(toYear, `${toYear}-01`, form.period_to, Math.round(monthly * lastMonths * 100) / 100))
    } else {
      // 无月金额，按月份比例分摊总金额
      const totalMonths = (toYear - fromYear) * 12 + (toP[1] - fromP[1]) + 1
      let remaining = totalAmount

      for (let y = fromYear; y <= toYear; y++) {
        const yM = y === fromYear ? 12 - fromP[1] + 1 : (y === toYear ? toP[1] : 12)
        const amt = y === toYear
          ? Math.round(remaining * 100) / 100
          : Math.round((totalAmount * yM / totalMonths) * 100) / 100
        remaining -= amt

        const pf = y === fromYear ? form.period_from : `${y}-01`
        const pt = y === toYear ? form.period_to : `${y}-12`
        list.push(makePayload(y, pf, pt, amt))
      }
    }

    return list
  }

  function makePayload(year, pf, pt, amt) {
    return {
      year, category: form.category, item_type: form.item_type,
      label: form.label || '', period_from: pf, period_to: pt,
      monthly_amount: form.monthly_amount || 0,
      tax_paid: form.tax_paid || 0,
      original_amount: form.category === 'other_income' ? (form.original_amount || 0) : null,
      amount: amt,
    }
  }
}

// ── 删除 ──
function deleteItem(item) {
  if (!item.id) { rows.value = rows.value.filter(r => r._key !== item._key); return }
  ElMessageBox.confirm('确定删除该调整项？', '确认删除', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
    .then(() => deleteTaxAdjustment(item.id).then(() => { rows.value = rows.value.filter(r => r._key !== item._key); ElMessage.success('已删除') }).catch(e => ElMessage.error('删除失败：' + (e.message || e))))
    .catch(() => {})
}

// ── 保存全部 ──
async function saveAllRows() {
  savingAll.value = true; let ok = 0, fail = 0
  for (const row of rows.value) {
    try {
      const rowYear = row.year || taxYear.value
      const payload = { year: rowYear, category: row.category, item_type: row.item_type, label: row.label || '', period_from: row.period_from || (rowYear + '-01'), period_to: row.period_to || (rowYear + '-12'), monthly_amount: row.monthly_amount || 0, tax_paid: row.tax_paid || 0, original_amount: row.category === 'other_income' ? (row.original_amount || 0) : null, amount: row.amount || 0 }
      if (row.id) { await updateTaxAdjustment(row.id, payload) }
      else { const res = await createTaxAdjustment(payload); Object.assign(row, res, { id: res.id }) }
      ok++
    } catch { fail++ }
  }
  savingAll.value = false
  if (fail === 0) ElMessage.success(`全部保存成功（${ok} 条）`)
  else ElMessage.warning(`${ok} 成功，${fail} 失败`)
}

// ── 加载 ──
function loadSummary() {
  if (!taxYear.value) { loaded.value = false; return }
  loading.value = true; loaded.value = false
  return getSalaryTaxSummary({ year: taxYear.value }).then(ts => {
    taxSummary.value = ts; rows.value = (ts.adjustments || []).map(a => makeRow(a)); loaded.value = true
  }).catch(() => { loaded.value = false; taxSummary.value = null }).finally(() => { loading.value = false })
}
function loadYears() { return getSalaryYears().then(years => { taxYears.value = years || [] }).catch(() => { taxYears.value = [] }) }
function loadAll() { return Promise.all([loadSummary(), loadYears()]) }
watch(taxYear, () => { loadSummary() })
onMounted(() => { loadAll() })
</script>

<style scoped>
.page-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:24px; }
.page-title { font-size:22px; font-weight:600; color:#2c2c2a; margin:0; }
.page-sub { margin:4px 0 0; font-size:13px; color:#999; }

.kpi-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:20px; }
.kpi-card { background:#fff; border:1px solid #e8e8e4; border-radius:12px; padding:20px 20px; }
.kpi-label { font-size:13px; color:#999; margin-bottom:10px; }
.kpi-value { font-size:24px; font-weight:700; color:#2c2c2a; font-variant-numeric:tabular-nums; }
.kpi-sub { margin-top:6px; font-size:12px; color:#aaa; line-height:1.5; }
.kpi-gross .kpi-value { color:#534ab7; }
.kpi-nontax .kpi-value { color:#909399; }
.kpi-deduct .kpi-value { color:#67C23A; }
.kpi-insurance .kpi-value { color:#E6A23C; }

.detail-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:20px; }
.detail-card { background:#fff; border:1px solid #e8e8e4; border-radius:12px; padding:20px 24px; }
.detail-title { font-size:14px; font-weight:600; color:#2c2c2a; margin-bottom:8px; }
.detail-body { display:flex; align-items:stretch; flex-wrap:wrap; }
.detail-row { flex:1; display:flex; flex-direction:column; align-items:center; padding:16px 8px; text-align:center; min-width:120px; }
.detail-label { font-size:12px; color:#888; margin-bottom:6px; white-space:nowrap; }
.detail-value { font-size:20px; font-weight:700; font-variant-numeric:tabular-nums; }
.detail-value.detail-tax-rate { color:#d9534f; font-size:24px; }
.detail-value.tax-zero { color:#909399; }
.detail-value.tax-low { color:#67C23A; }
.detail-value.tax-mid { color:#E6A23C; }
.detail-value.tax-high { color:#d9534f; }
.detail-divider { width:1px; background:#eef0f2; flex-shrink:0; }
.diff-hint { width:100%; text-align:center; font-size:13px; padding:8px 0 0; color:#666; }

.adj-section { background:#fff; border:1px solid #e8e8e4; border-radius:12px; padding:20px 24px; margin-bottom:16px; }
.adj-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.adj-title { font-size:14px; font-weight:600; color:#2c2c2a; }
.adj-actions { display:flex; gap:8px; }
.adj-empty { text-align:center; color:#ccc; padding:32px 0; font-size:13px; }

.adj-group { margin-bottom:16px; }
.adj-group-title { font-size:13px; font-weight:600; color:#666; margin-bottom:8px; }
.adj-group-total { font-weight:400; color:#999; margin-left:8px; font-size:12px; }

.adj-item { background:#f8f9fa; border:1px solid #eef0f2; border-radius:8px; padding:12px 16px; margin-bottom:6px; }
.adj-item-main { display:flex; align-items:center; gap:10px; }
.adj-item-type { font-size:13px; font-weight:600; color:#2c2c2a; flex-shrink:0; }
.adj-item-label { font-size:12px; color:#909399; background:#eef0f2; padding:1px 8px; border-radius:4px; flex-shrink:0; }
.adj-item-period { font-size:12px; color:#909399; flex-shrink:0; }
.adj-item-amt { font-size:15px; font-weight:700; color:#534ab7; margin-left:auto; flex-shrink:0; }
.adj-item-actions { display:flex; gap:4px; flex-shrink:0; }
.adj-item-detail-inline { font-size:12px; color:#999; flex-shrink:0; white-space:nowrap; }
.adj-item-prorate { font-size:12px; color:#E6A23C; flex-shrink:0; white-space:nowrap; }

.adj-footer { display:flex; gap:24px; padding-top:14px; margin-top:8px; border-top:1px solid #eef0f2; font-size:13px; color:#666; }
.adj-footer b { color:#534ab7; }

/* 对话框布局 */
.dlg-row2 { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
.dlg-row3 { display:grid; grid-template-columns:1fr 1fr 1fr; gap:14px; }
.form-hint { font-size:12px; color:#909399; margin-top:4px; }
.cross-year-notice { display:flex; align-items:center; gap:6px; font-size:12px; color:#E6A23C; background:#fdf6ec; padding:8px 12px; border-radius:6px; margin-bottom:8px; }
</style>
