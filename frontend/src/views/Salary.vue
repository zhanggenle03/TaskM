<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">薪资记录</h1>
        <p class="page-sub">按月记录薪资发放、明细与五险一金</p>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <el-date-picker
          v-model="periodRange"
          type="monthrange"
          range-separator="至"
          start-placeholder="开始月份"
          end-placeholder="结束月份"
          value-format="YYYY-MM"
          @change="loadData"
          style="width:260px"
        />
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon> 新增薪资
        </el-button>
        <el-button @click="openConfig">
          <el-icon><Setting /></el-icon> 薪资配置
        </el-button>
      </div>
    </div>

    <!-- 统计汇总卡片 -->
    <div class="summary-grid" v-if="summary">
      <div class="sum-card sum-gross">
        <div class="sum-label">区间应发合计</div>
        <div class="sum-value">{{ fmt(summary.total_gross) }}</div>
      </div>
      <div class="sum-card sum-deduct">
        <div class="sum-label">个人扣除合计</div>
        <div class="sum-value">{{ fmt(summary.total_personal_deduction) }}</div>
      </div>
      <div class="sum-card sum-net">
        <div class="sum-label">区间实发合计</div>
        <div class="sum-value">{{ fmt(summary.total_net) }}</div>
      </div>
      <div class="sum-card sum-credited">
        <div class="sum-label">到账合计</div>
        <div class="sum-value">{{ fmt(summary.total_credited) }}</div>
      </div>
      <div class="sum-card sum-company">
        <div class="sum-label">公司承担合计</div>
        <div class="sum-value">{{ fmt(summary.total_company_cost) }}</div>
      </div>
    </div>

    <!-- 个税年度汇算卡片 -->
    <div class="tax-summary-card" v-if="taxSummary">
      <div class="tax-summary-title">📊 {{ taxSummary.year }} 年个税汇算</div>
      <div class="tax-summary-body">
        <div class="tax-item">
          <div class="tax-item-label">本年应纳税所得额</div>
          <div class="tax-item-value" :class="taxableClass">{{ fmt(taxSummary.taxable_income) }}</div>
        </div>
        <div class="tax-divider"></div>
        <div class="tax-item">
          <div class="tax-item-label">当前税率</div>
          <div class="tax-item-value tax-rate">{{ taxSummary.tax_rate_label }}</div>
        </div>
        <div class="tax-divider"></div>
        <div class="tax-item">
          <div class="tax-item-label">距下一级距</div>
          <div class="tax-item-value" v-if="taxSummary.remaining_to_next > 0">{{ fmt(taxSummary.remaining_to_next) }}</div>
          <div class="tax-item-value tax-remaining" v-else>已达最高级</div>
        </div>
        <div class="tax-divider"></div>
        <div class="tax-item tax-sub">
          <div class="tax-item-label-sub">年度累计应发</div>
          <div class="tax-item-value-sub">{{ fmt(taxSummary.total_gross) }}</div>
        </div>
        <div class="tax-item tax-sub">
          <div class="tax-item-label-sub">累计减除费用</div>
          <div class="tax-item-value-sub">¥{{ (5000 * (taxSummary.month_count || 0)).toLocaleString() }}</div>
        </div>
        <div class="tax-item tax-sub">
          <div class="tax-item-label-sub">累计专项扣除</div>
          <div class="tax-item-value-sub">{{ fmt(taxSummary.total_social_insurance) }}</div>
        </div>
      </div>
    </div>

    <!-- 记录表格 -->
    <div class="table-wrap">
      <el-table :data="records" v-loading="loading" class="salary-table" empty-text="暂无薪资记录，点击右上角「新增薪资」开始记录">
        <el-table-column type="expand" label="" width="44" fixed="left">
          <template #default="{ row }">
            <div class="detail-list">
              <div v-for="it in row.items" :key="it.id" class="detail-row">
                <span class="detail-cat" :class="'cat-' + it.category">{{ catLabel(it.category) }}</span>
                <span class="detail-name">{{ it.name }}<template v-if="it.base != null && it.rate != null"> <span class="detail-formula">基数{{ fmt(it.base) }}×{{ it.rate }}%</span></template></span>
                <span class="detail-amt">{{ fmt(it.amount) }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="period" label="月份" width="80" />
        <el-table-column label="发放日期" width="100">
          <template #default="{ row }">{{ row.pay_date || '—' }}</template>
        </el-table-column>
        <el-table-column label="单位" min-width="125" show-overflow-tooltip>
          <template #default="{ row }">{{ row.employer || '—' }}</template>
        </el-table-column>
        <el-table-column label="应发" width="100" align="center">
          <template #default="{ row }"><span class="amt amt-gross">{{ fmt(row.gross) }}</span></template>
        </el-table-column>
        <el-table-column label="个人扣" width="190" align="center">
          <template #default="{ row }">
            <span class="amt amt-deduct">{{ fmt(row.personal_deduction) }}</span>
            <span class="tax-hint">（含税：{{ taxOf(row) }}）</span>
          </template>
        </el-table-column>
        <el-table-column label="实发" width="115" align="center">
          <template #default="{ row }"><span class="amt amt-net">{{ fmt(row.net) }}</span></template>
        </el-table-column>
        <el-table-column label="到账" width="115" align="center">
          <template #default="{ row }"><span class="amt amt-credited" :class="{ 'amt-muted': row.credited_amount == null }">{{ row.credited_amount != null ? fmt(row.credited_amount) : '—' }}</span></template>
        </el-table-column>
        <el-table-column label="实际个税" width="115" align="center">
          <template #default="{ row }"><span class="amt amt-tax" :class="{ 'amt-muted': row.actual_tax == null }">{{ row.actual_tax != null ? fmt(row.actual_tax) : '—' }}</span></template>
        </el-table-column>
        <el-table-column label="公司承担" width="115" align="center">
          <template #default="{ row }"><span class="amt amt-company">{{ fmt(row.company_cost) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="105" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 新增 / 编辑 弹窗 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑薪资记录' : '新增薪资记录'" width="1040px" top="2vh"
      class="record-dialog" @closed="resetForm"
      :style="{ height: '620px', maxHeight: '620px', display: 'flex', flexDirection: 'column' }">
      <div class="record-split">
        <div class="record-main">
          <el-form :model="form" label-width="88px">
            <div class="form-row">
              <el-form-item label="薪资月份" required>
                <el-date-picker v-model="form.period" type="month" value-format="YYYY-MM" placeholder="选择月份" style="width:100%" />
              </el-form-item>
              <el-form-item label="发放日期">
                <el-date-picker v-model="form.pay_date" type="date" value-format="YYYY-MM-DD" placeholder="发放日" style="width:100%" />
              </el-form-item>
            </div>
            <el-form-item label="单位">
              <el-input v-model="form.employer" placeholder="公司名（可选）" />
            </el-form-item>
          </el-form>

          <div class="sec-head">薪资明细</div>
          <div class="items-grid">
            <div class="items-head">
              <span>类别</span><span>项目名称</span><span>基数</span><span>比例%</span><span>金额（元）</span><span></span>
            </div>
            <div v-for="(item, idx) in form.items" :key="idx" class="item-row">
              <el-select v-model="item.category" size="small" class="item-cat" @change="onCatChange(item)">
                <el-option v-for="c in CATEGORY_OPTIONS" :key="c.value" :label="c.label" :value="c.value" />
              </el-select>
              <el-input v-model="item.name" size="small" placeholder="项目名称" class="item-name" />
              <el-input-number v-model="item.base" :min="0" :precision="2" :step="100" size="small" class="item-base" controls-position="right" />
              <el-input-number v-model="item.rate" :min="0" :precision="2" :step="0.1" size="small" class="item-rate" controls-position="right" />
              <el-input-number v-model="item.amount" :min="0" :precision="2" :step="100" size="small" class="item-amt" controls-position="right" :disabled="isRateMode(item)" />
              <el-button size="small" text type="danger" @click="removeItem(idx)"><el-icon><Delete /></el-icon></el-button>
            </div>
          </div>
          <div class="items-actions">
            <el-button size="small" @click="addItem"><el-icon><Plus /></el-icon> 加一行</el-button>
            <el-button size="small" @click="applySocialTemplate"><el-icon><MagicStick /></el-icon> 套用五险一金模板</el-button>
            <el-button size="small" @click="applyIncomeTemplate"><el-icon><DocumentCopy /></el-icon> 套用默认收入</el-button>
            <el-button size="small" @click="calcTax"><el-icon><DataAnalysis /></el-icon> 计算个税(实际已交个税计算)</el-button>
          </div>
        </div>

        <div class="record-side">
          <div class="summary-card">
            <div class="side-head">实时汇总</div>
            <div class="si"><span class="si-label">应发</span><span class="si-val c-gross">{{ fmt(formTotals.gross) }}</span></div>
            <div class="si"><span class="si-label">个人扣</span><span class="si-val c-deduct">{{ fmt(formTotals.personal_deduction) }}</span></div>
            <div class="si-divider"></div>
            <div class="si"><span class="si-label">实发</span><span class="si-val c-net">{{ fmt(formTotals.net) }}</span></div>
            <div class="si-divider"></div>
            <div class="si"><span class="si-label">公司承担</span><span class="si-val c-company">{{ fmt(formTotals.company_cost) }}</span></div>
          </div>

          <div class="actual-card">
            <div class="inline-field">
              <span class="inline-label">实际到账</span>
              <el-input-number v-model="form.credited_amount" :min="0" controls-position="right" size="small" class="inline-input" placeholder="入卡" />
            </div>
            <div class="inline-field">
              <span class="inline-label">实际个税</span>
              <el-input-number v-model="form.actual_tax" :min="0" controls-position="right" size="small" class="inline-input" placeholder="个税" />
            </div>
          </div>

          <div class="side-head remark-head">备注</div>
          <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="可选备注" class="remark-input"></el-input>
        </div>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 薪资默认配置 弹窗 -->
    <el-dialog v-model="configVisible" title="薪资默认配置" width="900px" top="2vh"
      class="config-dialog" @closed="resetConfigForm"
      :style="{ height: '640px', maxHeight: '640px', display: 'flex', flexDirection: 'column' }">
      <el-alert type="info" :closable="false" show-icon
        title="通用稳定配置，配置一次后新增薪资时自动带入，无需每月重复填写。" style="margin-bottom:16px" />
      <el-tabs v-model="configTab" class="config-tabs">
        <!-- 基础设置 -->
        <el-tab-pane label="基础设置" name="basic">
          <div class="cfg-section">
            <el-form :model="configForm" label-width="92px" class="cfg-form">
              <el-form-item label="默认单位">
                <el-input v-model="configForm.employer" placeholder="如：某某科技有限公司（可选）" />
              </el-form-item>
              <el-form-item label="默认发放日">
                <div class="pay-day">
                  <el-select v-model="configForm.default_pay_month" size="small" style="width:100px">
                    <el-option label="当月" value="current" />
                    <el-option label="次月" value="next" />
                  </el-select>
                  <el-input-number v-model="configForm.default_pay_day" :min="1" :max="31" size="small" controls-position="right" style="width:120px" />
                  <span class="unit">号</span>
                </div>
                <div class="hint">新增时按所选月份自动预填发放日，如「次月 5 号」表示次月 5 日发放</div>
              </el-form-item>
            </el-form>
          </div>
          <div class="cfg-divider">默认收入项</div>
          <div class="income-tpl">
            <div v-for="(it, idx) in configForm.default_income_items" :key="idx" class="income-tpl-row">
              <el-input v-model="it.name" size="small" placeholder="项目名称" style="flex:1" />
              <span class="unit">¥</span>
              <el-input-number v-model="it.amount" :min="0" :precision="2" :step="100" size="small" controls-position="right" style="width:150px" />
              <el-button size="small" text type="danger" @click="configForm.default_income_items.splice(idx, 1)"><el-icon><Delete /></el-icon></el-button>
            </div>
            <el-button size="small" class="add-income" @click="configForm.default_income_items.push({ name: '', amount: 0 })"><el-icon><Plus /></el-icon> 加一项</el-button>
          </div>
          <div class="hint" style="margin-top:8px">新增薪资时会自动带出以上收入项。</div>
        </el-tab-pane>

        <!-- 五险一金 -->
        <el-tab-pane label="五险一金" name="social">
          <div class="social-wrap">
            <div class="social-col personal">
              <div class="social-col-title personal">个人缴纳</div>
              <div class="social-line head"><span>项目</span><span>基数</span><span>比例%</span><span class="amt-cell">月金额</span></div>
              <div v-for="k in SOCIAL_PERSONAL" :key="k" class="social-line">
                <span class="sname" :title="k">{{ k.replace('(个人)', '') }}</span>
                <el-input-number v-model="configForm.social_bases[k]" :min="0" :precision="2" :step="100" size="small" controls-position="right" />
                <el-input-number v-model="configForm.social_rates[k]" :min="0" :max="100" :precision="2" :step="0.1" size="small" controls-position="right" />
                <span class="amt-cell">{{ fmt(round2((configForm.social_bases[k]||0) * (configForm.social_rates[k]||0) / 100)) }}</span>
              </div>
            </div>
            <div class="social-col company">
              <div class="social-col-title company">公司承担</div>
              <div class="social-line head"><span>项目</span><span>基数</span><span>比例%</span><span class="amt-cell">月金额</span></div>
              <div v-for="k in SOCIAL_COMPANY" :key="k" class="social-line">
                <span class="sname" :title="k">{{ k.replace('(公司)', '') }}</span>
                <el-input-number v-model="configForm.social_bases[k]" :min="0" :precision="2" :step="100" size="small" controls-position="right" />
                <el-input-number v-model="configForm.social_rates[k]" :min="0" :max="100" :precision="2" :step="0.1" size="small" controls-position="right" />
                <span class="amt-cell">{{ fmt(round2((configForm.social_bases[k]||0) * (configForm.social_rates[k]||0) / 100)) }}</span>
              </div>
            </div>
          </div>
          <div class="hint" style="margin-top:10px">各项最低缴费基数通常不同，可分别填写；留空则该项套用时需手动填基数。</div>
        </el-tab-pane>

      </el-tabs>
      <template #footer>
        <el-button @click="configVisible = false">取消</el-button>
        <el-button type="primary" :loading="configSaving" @click="saveConfig">保存配置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getSalaryRecords, getSalaryRecord,
  createSalaryRecord, updateSalaryRecord, deleteSalaryRecord, getSalarySummary,
  getSalaryConfig, updateSalaryConfig, getSalaryTaxSummary, calcSalaryTax,
} from '../api'

// ── 常量 ──
const CATEGORY_OPTIONS = [
  { value: 'income', label: '收入', cls: 'cat-income' },
  { value: 'deduction', label: '个人扣款', cls: 'cat-deduction' },
  { value: 'tax', label: '个税', cls: 'cat-tax' },
  { value: 'company_cost', label: '公司承担', cls: 'cat-company_cost' },
]
// 五险一金模板（个人部分进「个人扣款」，公司部分进「公司承担」）
const SOCIAL_TEMPLATE = [
  { category: 'deduction', name: '养老保险(个人)', funded_by: 'personal' },
  { category: 'deduction', name: '医疗保险(个人)', funded_by: 'personal' },
  { category: 'deduction', name: '失业保险(个人)', funded_by: 'personal' },
  { category: 'deduction', name: '住房公积金(个人)', funded_by: 'personal' },
  { category: 'company_cost', name: '养老保险(公司)', funded_by: 'company' },
  { category: 'company_cost', name: '医疗保险(公司)', funded_by: 'company' },
  { category: 'company_cost', name: '失业保险(公司)', funded_by: 'company' },
  { category: 'company_cost', name: '工伤保险(公司)', funded_by: 'company' },
  { category: 'company_cost', name: '生育保险(公司)', funded_by: 'company' },
  { category: 'company_cost', name: '住房公积金(公司)', funded_by: 'company' },
]
// 五险一金各险种默认比例（百分比，如 8 表示 8%）；套用模板时按对话框缴费基数自动计算金额
const SOCIAL_RATES = {
  '养老保险(个人)': 0,
  '医疗保险(个人)': 0,
  '失业保险(个人)': 0,
  '住房公积金(个人)': 0,
  '养老保险(公司)': 0,
  '医疗保险(公司)': 0,
  '失业保险(公司)': 0,
  '工伤保险(公司)': 0,
  '生育保险(公司)': 0,
  '住房公积金(公司)': 0,
}

// 比例配置的键顺序（与模板名称一致）
const RATE_KEYS = [
  '养老保险(个人)', '医疗保险(个人)', '失业保险(个人)', '住房公积金(个人)',
  '养老保险(公司)', '医疗保险(公司)', '失业保险(公司)', '工伤保险(公司)', '生育保险(公司)', '住房公积金(公司)',
]
// 按个人 / 公司拆分，便于两栏展示
const SOCIAL_PERSONAL = RATE_KEYS.filter(k => k.includes('个人'))
const SOCIAL_COMPANY = RATE_KEYS.filter(k => k.includes('公司'))

// 各项默认比例（百分比，如 8 表示 8%），套用模板时按对话框缴费基数自动计算金额
function defaultRates() {
  return {
    '养老保险(个人)': 0, '医疗保险(个人)': 0, '失业保险(个人)': 0, '住房公积金(个人)': 0,
    '养老保险(公司)': 0, '医疗保险(公司)': 0, '失业保险(公司)': 0, '工伤保险(公司)': 0, '生育保险(公司)': 0, '住房公积金(公司)': 0,
  }
}

// ── 状态 ──
const loading = ref(false)
const saving = ref(false)
const records = ref([])
const summary = ref(null)
const taxSummary = ref(null)

// 月份范围过滤，默认当前年
const now = new Date()
const periodRange = ref([`${now.getFullYear()}-01`, `${now.getFullYear()}-12`])

const dialogVisible = ref(false)

// ── 薪资通用配置（用于新增时自动带入）──
const configVisible = ref(false)
const configTab = ref('basic')
const configSaving = ref(false)
const salaryConfig = ref(null)
const emptyConfig = () => ({
  employer: '',
  social_bases: {},
  social_rates: defaultRates(),
  default_pay_month: 'current',
  default_pay_day: 10,
  default_income_items: [],
})
const configForm = reactive(emptyConfig())
function resetConfigForm() { Object.assign(configForm, emptyConfig()) }

const emptyForm = () => ({ id: null, period: '', pay_date: '', employer: '', credited_amount: null, actual_tax: null, remark: '', items: [] })
const form = reactive(emptyForm())

// ── 工具 ──
const fmt = (n) => '¥' + Number(n || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const catLabel = (c) => (CATEGORY_OPTIONS.find(o => o.value === c) || {}).label || c
// 从明细行中计算个税合计
const taxOf = (row) => fmt((row.items || []).filter(i => i.category === 'tax').reduce((s, i) => s + (i.amount || 0), 0))
// 应纳税所得额的颜色样式
const taxableClass = computed(() => {
  if (!taxSummary.value) return ''
  const ti = taxSummary.value.taxable_income
  if (ti <= 0) return 'tax-zero'
  if (ti <= 36000) return 'tax-low'
  if (ti <= 144000) return 'tax-mid'
  return 'tax-high'
})

function loadData() {
  loading.value = true
  const [pf, pt] = periodRange.value || []
  return Promise.all([
    getSalaryRecords({ period_from: pf || null, period_to: pt || null }),
    getSalarySummary({ period_from: pf || null, period_to: pt || null }),
    loadTaxSummary(),
  ]).then(([recs, sum]) => {
    records.value = recs || []
    summary.value = sum
  }).catch(() => {
    records.value = []
    summary.value = null
  }).finally(() => { loading.value = false })
}

function loadTaxSummary() {
  const year = new Date().getFullYear()
  return getSalaryTaxSummary({ year }).then(ts => {
    taxSummary.value = ts
  }).catch(() => {
    taxSummary.value = null
  })
}

onMounted(async () => { await loadData(); await loadConfig() })

// ── 薪资通用配置 ──
function loadConfig() {
  return getSalaryConfig().then(c => { salaryConfig.value = c }).catch(() => { salaryConfig.value = emptyConfig() })
}
async function openConfig() {
  try {
    const c = await getSalaryConfig()
    configForm.employer = c.employer || ''
    configForm.social_bases = { ...(c.social_bases || {}) }
    configForm.default_pay_month = c.default_pay_month || 'current'
    configForm.default_pay_day = c.default_pay_day || 10
    const rates = defaultRates()
    Object.assign(rates, c.social_rates || {})
    configForm.social_rates = rates
    configForm.default_income_items = (c.default_income_items || []).map(i => ({ name: i.name, amount: i.amount }))
    configVisible.value = true
  } catch { /* 拦截器已提示 */ }
}
async function saveConfig() {
  configSaving.value = true
  // 各项缴费基数分项收集（仅保留已填数字项）
  const bases = {}
  for (const k of RATE_KEYS) {
    const v = configForm.social_bases[k]
    if (v !== '' && v != null && !isNaN(Number(v))) bases[k] = Number(v)
  }
  const payload = {
    employer: configForm.employer,
    social_bases: bases,
    social_rates: { ...configForm.social_rates },
    default_pay_month: configForm.default_pay_month || 'current',
    default_pay_day: Number(configForm.default_pay_day) || 10,
    default_income_items: configForm.default_income_items
      .filter(i => i.name).map(i => ({ name: i.name, amount: Number(i.amount) || 0 })),
  }
  try {
    const saved = await updateSalaryConfig(payload)
    salaryConfig.value = saved
    ElMessage.success('配置已保存')
    configVisible.value = false
  } catch { /* 拦截器已提示 */ }
  finally { configSaving.value = false }
}

// ── 表单内明细 ──
function addItem() {
  form.items.push({ category: 'income', name: '', amount: 0, base: null, rate: null, funded_by: '', sort_order: form.items.length })
}
function removeItem(idx) { form.items.splice(idx, 1) }
function onCatChange(item) {
  // 根据类别自动带出 funded_by，便于后续统计
  item.funded_by = (item.category === 'company_cost') ? 'company' : (item.category === 'deduction' || item.category === 'tax' ? 'personal' : '')
}
// 基数与比例同时填写 → 金额自动算（基数×比例/100），金额输入禁用
function isRateMode(item) {
  return item.base !== '' && item.base != null && item.rate !== '' && item.rate != null
}
const numOrNull = (v) => (v === '' || v == null ? null : Number(v))
function applySocialTemplate(silent = false) {
  // 套用模板：按配置中「各项缴费基数」+ 比例自动生成明细；已存在同名项不重复添加
  const cfg = salaryConfig.value
  const rates = (cfg && cfg.social_rates) ? cfg.social_rates : SOCIAL_RATES
  const bases = (cfg && cfg.social_bases) ? cfg.social_bases : {}
  const exist = new Set(form.items.map(i => i.name))
  let anyBase = false
  SOCIAL_TEMPLATE.forEach(t => {
    if (!exist.has(t.name)) {
      const rate = rates[t.name] ?? 0
      const rawBase = bases[t.name]
      const base = (rawBase !== '' && rawBase != null && !isNaN(Number(rawBase))) ? Number(rawBase) : null
      if (base != null) anyBase = true
      const amount = base != null ? round2(base * rate / 100) : 0
      form.items.push({
        category: t.category, name: t.name, funded_by: t.funded_by,
        base: base, rate: rate, amount: amount,
        sort_order: form.items.length,
      })
    }
  })
  if (!silent) {
    ElMessage.success(anyBase ? '已套用五险一金模板（按各项缴费基数自动计算）' : '已套用五险一金模板（各项基数请在套用后分别填写）')
  }
}
function applyIncomeTemplate() {
  const cfg = salaryConfig.value
  if (!cfg || !cfg.default_income_items || !cfg.default_income_items.length) {
    ElMessage.warning('请先在「薪资配置」中设置默认收入项')
    openConfig()
    return
  }
  const exist = new Set(form.items.map(i => i.name))
  cfg.default_income_items.forEach(it => {
    if (!exist.has(it.name)) {
      form.items.push({
        category: 'income', name: it.name, amount: it.amount || 0,
        base: null, rate: null, funded_by: '', sort_order: form.items.length,
      })
    }
  })
  ElMessage.success('已套用默认收入项')
}

async function calcTax() {
  if (!form.period) {
    ElMessage.warning('请先选择薪资月份')
    return
  }
  try {
    const payload = {
      period: form.period,
      edit_id: form.id,
      items: form.items.map((it, i) => {
        const base = numOrNull(it.base)
        const rate = numOrNull(it.rate)
        const amount = (base != null && rate != null) ? round2(base * rate / 100) : (Number(it.amount) || 0)
        return {
          category: it.category,
          name: it.name,
          amount: amount,
          base: base,
          rate: rate,
          funded_by: it.funded_by || '',
          sort_order: i,
        }
      }),
    }
    const res = await calcSalaryTax(payload)
    const taxVal = res.tax_amount
    // 查找明细中是否已有"个税"项，有则更新，无则添加
    const existing = form.items.find(i => i.category === 'tax')
    if (existing) {
      existing.amount = taxVal
      existing.base = null
      existing.rate = null
    } else {
      form.items.push({
        category: 'tax',
        name: '个税',
        amount: taxVal,
        base: null,
        rate: null,
        funded_by: 'personal',
        sort_order: form.items.length,
      })
    }
    ElMessage.success(`计算个税完成：本月应扣 ¥${taxVal.toFixed(2)}`)
  } catch { /* 拦截器已提示 */ }
}

const round2 = (n) => Math.round((n + Number.EPSILON) * 100) / 100

// 基数+比例同时填写时，按 基数×比例/100 计算金额，用于实时汇总
const formTotals = computed(() => {
  let gross = 0, pd = 0, cc = 0
  for (const it of form.items) {
    const b = numOrNull(it.base)
    const r = numOrNull(it.rate)
    const a = (b != null && r != null) ? round2(b * r / 100) : (Number(it.amount) || 0)
    if (it.category === 'income') gross += a
    else if (it.category === 'deduction' || it.category === 'tax') pd += a
    else if (it.category === 'company_cost') cc += a
  }
  return { gross: round2(gross), personal_deduction: round2(pd), net: round2(gross - pd), company_cost: round2(cc) }
})

// 基数/比例变动时，自动回填金额（仅对「基数×比例」模式的行），让禁用的金额输入框显示正确值
watch(
  () => form.items.map(i => [i.base, i.rate]),
  () => {
    form.items.forEach(it => {
      const b = numOrNull(it.base)
      const r = numOrNull(it.rate)
      if (b != null && r != null) it.amount = round2(b * r / 100)
    })
  },
  { deep: true }
)

// ── 打开 / 保存 / 删除 ──
function resetForm() {
  Object.assign(form, emptyForm())
}
function openCreate() {
  resetForm()
  // 仅带出默认单位名称，薪资明细由用户手动添加
  const cfg = salaryConfig.value
  if (cfg) form.employer = cfg.employer || ''
  dialogVisible.value = true
}

// 新增时，选择月份后按「默认发放月份 + 默认发放日」自动预填发放日
function computeDefaultPayDate(period, monthOffset, day) {
  if (!period) return ''
  const [y, m] = period.split('-').map(Number)
  let yy = y
  let mm = m + (monthOffset || 0)
  if (mm > 12) { mm -= 12; yy += 1 }
  return `${yy}-${String(mm).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}
watch(
  () => form.period,
  (p) => {
    if (!form.id && p) {
      const cfg = salaryConfig.value || {}
      const monthOffset = cfg.default_pay_month === 'next' ? 1 : 0
      const day = cfg.default_pay_day || 10
      form.pay_date = computeDefaultPayDate(p, monthOffset, day)
    }
  }
)
async function openEdit(row) {
  try {
    const detail = await getSalaryRecord(row.id)
    Object.assign(form, {
      id: detail.id,
      period: detail.period,
      pay_date: detail.pay_date || '',
      employer: detail.employer || '',
      credited_amount: detail.credited_amount ?? null,
      actual_tax: detail.actual_tax ?? null,
      remark: detail.remark || '',
      items: (detail.items || []).map((it, i) => ({
        category: it.category, name: it.name, amount: it.amount,
        base: (it.base == null ? null : it.base),
        rate: (it.rate == null ? null : it.rate),
        funded_by: it.funded_by || '', sort_order: i,
      })),
    })
    dialogVisible.value = true
  } catch { /* 错误提示由拦截器处理 */ }
}

async function save() {
  if (!form.period) { ElMessage.warning('请选择薪资月份'); return }
  const payload = {
    period: form.period,
    pay_date: form.pay_date || null,
    employer: form.employer || '',
    credited_amount: form.credited_amount ?? null,
    actual_tax: form.actual_tax ?? null,
    remark: form.remark || '',
    items: form.items.map((it, i) => {
      const base = numOrNull(it.base)
      const rate = numOrNull(it.rate)
      const amount = (base != null && rate != null) ? round2(base * rate / 100) : (Number(it.amount) || 0)
      return {
        category: it.category,
        name: it.name,
        amount: amount,
        base: base,
        rate: rate,
        funded_by: it.funded_by || '',
        sort_order: i,
      }
    }),
  }
  saving.value = true
  try {
    if (form.id) await updateSalaryRecord(form.id, payload)
    else await createSalaryRecord(payload)
    ElMessage.success('已保存')
    dialogVisible.value = false
    await loadData()
  } catch { /* 拦截器已提示（如月份重复 409） */ }
  finally { saving.value = false }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除 ${row.period} 的薪资记录吗？`, '删除确认', { type: 'warning' })
  } catch { return }
  try {
    await deleteSalaryRecord(row.id)
    ElMessage.success('已删除')
    await loadData()
  } catch { /* 拦截器提示 */ }
}
</script>

<style scoped>
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
.page-title { font-size: 22px; font-weight: 600; color: #2c2c2a; margin: 0; }
.page-sub { margin: 4px 0 0; font-size: 13px; color: #999; }

.summary-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 18px; }
.sum-card { background: #fff; border: 1px solid #e8e8e4; border-radius: 10px; padding: 14px 16px; }
.sum-label { font-size: 12px; color: #999; margin-bottom: 8px; }
.sum-value { font-size: 18px; font-weight: 600; color: #2c2c2a; }
.sum-gross .sum-value { color: #67C23A; }
.sum-deduct .sum-value { color: #E6A23C; }
.sum-net .sum-value { color: #534AB7; }
.sum-credited .sum-value { color: #1d953f; }
.sum-company .sum-value { color: #909399; }
.sum-avg .sum-value { color: #2c2c2a; }

/* 个税年度汇算卡片 */
.tax-summary-card {
  background: linear-gradient(135deg, #f0f5ff 0%, #e8f0fe 100%);
  border: 1px solid #c8d8f0;
  border-radius: 10px;
  padding: 14px 20px;
  margin-bottom: 18px;
  display: flex;
  align-items: stretch;
  gap: 18px;
}
.tax-summary-title {
  font-size: 14px;
  font-weight: 600;
  color: #3a5fa8;
  white-space: nowrap;
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.tax-summary-body {
  display: flex;
  align-items: stretch;
  gap: 0;
  flex: 1;
}
.tax-item {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 0 18px;
  min-width: 0;
  flex: 1;
}
.tax-item.tax-sub {
  flex: 0.7;
  padding: 0 12px;
}
.tax-item-label {
  font-size: 11px;
  color: #6b7fa8;
  margin-bottom: 4px;
  text-align: center;
  white-space: nowrap;
}
.tax-item-value {
  font-size: 16px;
  font-weight: 600;
  color: #2c3e6b;
  font-variant-numeric: tabular-nums;
}
.tax-item-value.tax-rate {
  color: #d9534f;
  font-size: 20px;
}
.tax-item-value.tax-remaining {
  color: #67C23A;
  font-size: 13px;
}
.tax-item-value.tax-zero { color: #909399; }
.tax-item-value.tax-low { color: #67C23A; }
.tax-item-value.tax-mid { color: #E6A23C; }
.tax-item-value.tax-high { color: #d9534f; }
.tax-divider {
  width: 1px;
  background: #c8d8f0;
  flex-shrink: 0;
  align-self: stretch;
}
.tax-item-label-sub {
  font-size: 10px;
  color: #8a9fc8;
  margin-bottom: 2px;
  text-align: center;
  white-space: nowrap;
}
.tax-item-value-sub {
  font-size: 12px;
  font-weight: 500;
  color: #5a7ab8;
  font-variant-numeric: tabular-nums;
}

.salary-table { background: #fff; border-radius: 10px; border: 1px solid #e8e8e4; }
.salary-table :deep(.cell) { white-space: nowrap; }
.table-wrap { width: 100%; }
.amt { font-variant-numeric: tabular-nums; }
.amt-gross { color: #67C23A; }
.amt-deduct { color: #E6A23C; }
.tax-hint { color: #aaa; font-size: 12px; white-space: nowrap; }
.amt-net { color: #534AB7; font-weight: 600; }
.amt-credited { color: #1d953f; }
.amt-tax { color: #d9534f; }
.amt-muted { color: #bbb; }
.amt-company { color: #909399; }

.detail-list { padding: 4px 12px; }
.detail-row { display: flex; align-items: center; gap: 12px; padding: 4px 0; font-size: 13px; }
.detail-cat { flex: 0 0 76px; text-align: center; border-radius: 4px; padding: 1px 0; font-size: 12px; color: #fff; }
.detail-name { flex: 1; color: #2c2c2a; }
.detail-amt { font-variant-numeric: tabular-nums; color: #555; }
.detail-formula { color: #aaa; font-size: 11px; margin-left: 4px; }
.cat-income { background: #67C23A; }
.cat-deduction { background: #E6A23C; }
.cat-tax { background: #F56C6C; }
.cat-company_cost { background: #909399; }

/* 弹窗内表单 */
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.form-row .el-form-item { min-width: 0; }

/* 分栏布局：左侧明细可滚动，右侧汇总固定 */
.record-split { display: flex; gap: 20px; height: 100%; }
.record-main { flex: 1; overflow-y: auto; overflow-x: hidden; min-width: 0; padding-right: 4px; }
.record-side { flex: 0 0 280px; display: flex; flex-direction: column; min-height: 0; }
.record-side .side-head { flex-shrink: 0; }
.record-side .side-head.credited-head { margin-top: 16px; }
.record-side .side-head.tax-head { margin-top: 12px; }
.record-side .side-head.remark-head { margin-top: 20px; }
.record-side .side-head.remark-head { margin-top: 20px; }
.record-side .remark-input { flex: 1; overflow-y: auto; min-height: 0; }

/* 实际到账 / 实际个税 卡片 */
.actual-card {
  background: #f8f9fb;
  border: 1px solid #eef0f2;
  border-radius: 10px;
  padding: 10px 14px;
  margin-top: 12px;
  flex-shrink: 0;
}
.inline-field { display: flex; align-items: center; gap: 8px; }
.inline-field + .inline-field { margin-top: 8px; }
.inline-label { font-size: 12px; color: #666; white-space: nowrap; flex-shrink: 0; }
.inline-input { flex: 0 0 120px; }
.inline-input .el-input-number { width: 100%; }

.sec-head {
  font-size: 13px; font-weight: 600; color: #2c2c2a;
  padding: 0 0 10px; margin: 16px 0 12px;
  border-bottom: 1px solid #eef0f2;
}

.items-grid {
  border: 1px solid #edf0f4;
  border-radius: 8px;
  padding: 10px 12px;
  background: #fafbfc;
}
.items-head, .item-row { display: flex; align-items: center; gap: 6px; }
.items-head { font-size: 12px; color: #aaa; padding: 0 2px 8px; margin-bottom: 4px; border-bottom: 1px dashed #e6e6e6; }
.items-head span:nth-child(1), .item-cat { flex: 0 0 100px; }
.items-head span:nth-child(2), .item-name { flex: 1; min-width: 100px; }
.items-head span:nth-child(3), .item-base { flex: 0 0 100px; }
.items-head span:nth-child(4), .item-rate { flex: 0 0 86px; }
.items-head span:nth-child(5), .item-amt { flex: 0 0 118px; }
.items-head span:nth-child(6) { flex: 0 0 32px; }
.item-row { padding: 6px 2px; }
.item-row + .item-row { border-top: 1px solid rgba(0,0,0,.045); }
.item-row:hover { background: rgba(83,74,183,.045); border-radius: 6px; margin: 0 -4px; padding: 6px; }
.items-actions { margin-top: 10px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }

/* 侧边摘要卡片 */
.summary-card {
  background: #f8f9fb;
  border: 1px solid #eef0f2;
  border-radius: 12px;
  padding: 16px 18px;
  margin-bottom: 16px;
}
.side-head {
  font-size: 13px; font-weight: 600; color: #2c2c2a;
  margin-bottom: 12px; padding-bottom: 8px;
  border-bottom: 1px solid #eef0f2;
}
.si { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; }
.si-label { font-size: 13px; color: #666; }
.si-val { font-size: 17px; font-weight: 600; font-variant-numeric: tabular-nums; }
.c-gross { color: #67C23A; }
.c-deduct { color: #E6A23C; }
.c-net { color: #534AB7; }
.c-company { color: #909399; }
.si-divider { height: 1px; background: #eef0f2; margin: 0; }

/* 配置弹窗固定高度 - 见文件底部非 scoped 样式块（el-dialog Teleport 到 body，scoped 属性不传递） */

.config-tabs { margin-top: -4px; }
.config-tabs :deep(.el-tabs__header) { margin-bottom: 16px; }
.config-tabs :deep(.el-tabs__item) { font-size: 14px; }
.cfg-section { padding: 2px; }
.cfg-divider {
  font-size: 12px; color: #999; font-weight: 500;
  padding: 0 0 8px; margin: 16px 0 10px;
  border-bottom: 1px solid #eef0f2;
}
.hint { color: #999; font-size: 12px; line-height: 1.6; }
.pay-day { display: flex; align-items: center; gap: 8px; }
.unit { color: #999; font-size: 13px; }

/* 五险一金 两栏卡片 */
.social-wrap { display: flex; gap: 16px; }
.social-col { flex: 1; min-width: 0; border-radius: 12px; padding: 14px 16px; }
.social-col.personal { background: #fffaf3; border: 1px solid #f6e6cf; }
.social-col.company { background: #f8f9fb; border: 1px solid #e7eaef; }
.social-col-title {
  font-size: 13px; font-weight: 600;
  display: inline-flex; align-items: center; gap: 7px;
  padding: 4px 11px; border-radius: 20px; margin-bottom: 12px;
}
.social-col-title::before { content: ''; width: 7px; height: 7px; border-radius: 50%; }
.social-col-title.personal { color: #C8841A; background: #fbecd6; }
.social-col-title.personal::before { background: #E6A23C; }
.social-col-title.company { color: #6b7280; background: #eceef1; }
.social-col-title.company::before { background: #909399; }

.social-line {
  display: grid; grid-template-columns: 1fr 90px 76px 80px;
  align-items: center; gap: 6px; padding: 7px 6px; border-radius: 6px;
}
.social-line > * { min-width: 0; }
.social-line.head {
  font-size: 12px; color: #aaa;
  padding: 0 6px 8px; margin-bottom: 2px;
  border-bottom: 1px dashed #e0e0e0;
}
.social-line:not(.head) + .social-line:not(.head) { border-top: 1px solid rgba(0,0,0,.045); }
.social-line:not(.head):hover { background: rgba(83,74,183,.05); }
.sname { font-size: 13px; color: #2c2c2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.amt-cell { font-size: 13px; color: #555; text-align: right; font-variant-numeric: tabular-nums; }
.social-line.head .amt-cell { color: #aaa; }
.social-line :deep(.el-input-number) { width: 100%; }
.social-line :deep(.el-input-number .el-input__inner) { text-align: right; }

/* 默认收入 */
.income-tpl { display: flex; flex-direction: column; gap: 10px; padding: 2px; }
.income-tpl-row {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; background: #fafbfc;
  border: 1px solid #eef0f2; border-radius: 8px;
}
.add-income { align-self: flex-start; }
</style>

<!-- el-dialog Teleport 到 body，固定高度须用非 scoped 样式 -->
<style>
.config-dialog .el-dialog__header { flex-shrink: 0; }
.config-dialog .el-dialog__body {
  flex: 1 1 0;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0;
}
.config-dialog .el-dialog__footer { flex-shrink: 0; }

.record-dialog .el-dialog__header { flex-shrink: 0; }
.record-dialog .el-dialog__body {
  flex: 1 1 0;
  overflow: hidden;
  min-height: 0;
}
.record-dialog .el-dialog__footer { flex-shrink: 0; }
</style>
