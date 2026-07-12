<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">工作记录</h1>
        <p class="page-sub">每日签到与工作记录</p>
      </div>
      <div style="display:flex;gap:8px">
        <el-button :type="deleteBatchMode ? 'danger' : 'default'" @click="toggleDeleteBatchMode">
          <el-icon><Delete /></el-icon> {{ deleteBatchMode ? '退出删除' : '批量删除' }}
        </el-button>
        <el-button :type="batchMode ? 'warning' : 'default'" @click="toggleBatchMode">
          <el-icon><Select /></el-icon> {{ batchMode ? '退出批量' : '批量签到' }}
        </el-button>
        <el-button type="success" @click="openCheckinDialog">
          <el-icon><Select /></el-icon> 签到
        </el-button>
      </div>
    </div>

    <div class="calendar-layout">
      <div class="cal-left">
        <!-- 日历 -->
        <div class="cal-panel" :class="{ 'batch-mode': batchMode, 'delete-batch-mode': deleteBatchMode }">
          <div class="cal-nav">
            <el-button size="small" text @click="prevMonth"><el-icon><ArrowLeft /></el-icon></el-button>
            <span class="cal-month-title">{{ calYear }}年{{ calMonth }}月</span>
            <el-button size="small" text @click="nextMonth"><el-icon><ArrowRight /></el-icon></el-button>
            <el-button size="small" text style="margin-left:8px" @click="goToday">今天</el-button>
            <el-button size="small" text style="margin-left:auto" @click="showHolidaySettings = true">
              <el-icon><Setting /></el-icon>
            </el-button>
          </div>
          <div class="cal-weekdays">
            <div v-for="w in weekDays" :key="w" class="cal-weekday">{{ w }}</div>
          </div>
          <div v-if="holidayVersion" class="cal-grid">
            <div
              v-for="(day, i) in calendarDays"
              :key="i"
              class="cal-cell"
              :class="{
                'cal-cell-empty': day.empty,
                today: day.isToday,
                active: !batchMode && !deleteBatchMode && day.date === selectedDate,
                'has-checkin': checkinsByDate[day.date],
                'batch-selected': batchMode && batchDates.includes(day.date),
                'batch-disabled': (batchMode && checkinsByDate[day.date]),
                'delete-selected': deleteBatchMode && deleteDates.includes(day.date),
                'delete-disabled': (deleteBatchMode && !checkinsByDate[day.date]),
              }"
              @click="onCellClick(day)"
            >
              <template v-if="!day.empty">
                <span class="cal-cell-num">{{ day.num }}</span>
                <span v-if="day.holiday && day.holiday.badge" class="cal-cell-badge" :class="'cb-' + day.holiday.badgeType">{{ day.holiday.badge }}</span>
                <span v-if="day.status === 'attendance' && !batchMode && !deleteBatchMode" class="cal-cell-dot"></span>
                <span v-if="day.status === 'overtime' && !batchMode && !deleteBatchMode" class="cal-cell-label cal-cell-overtime">加</span>
                <span v-if="day.status === 'leave' && !batchMode && !deleteBatchMode" class="cal-cell-label cal-cell-leave">请</span>
                <span v-if="batchMode && checkinsByDate[day.date]" class="cal-cell-checked">已签</span>
                <span v-if="deleteBatchMode && checkinsByDate[day.date]" class="cal-cell-has-data">已签</span>
              </template>
            </div>
          </div>
          <!-- 数据加载中 -> 骨架占位 -->
          <div v-else class="cal-grid cal-grid-loading">
            <div v-for="i in 42" :key="i" class="cal-cell cal-cell-empty">&nbsp;</div>
          </div>

          <!-- 批量签到底部栏 -->
          <div v-if="batchMode" class="batch-bar">
            <span>已选 {{ batchDates.length }} 天</span>
            <el-button size="small" type="primary" :disabled="!batchDates.length" @click="openBatchDialog">
              确定签到
            </el-button>
          </div>

          <!-- 批量删除底部栏 -->
          <div v-if="deleteBatchMode" class="delete-batch-bar">
            <span>已选 <strong>{{ deleteDates.length }}</strong> 天</span>
            <el-button size="small" type="danger" :disabled="!deleteDates.length" @click="confirmBatchDelete">
              <el-icon><Delete /></el-icon> 删除选中
            </el-button>
          </div>
        </div>

        <!-- 月份出勤统计卡片 -->
        <div class="cal-stats-card">
          <div class="cal-stats-title">{{ calYear }}年{{ calMonth }}月出勤</div>
          <div class="cal-stats-row">
            <span class="cal-stats-item">应出勤 <strong>{{ monthStats.requiredWorkDays }}</strong> 天</span>
            <span class="cal-stats-divider"></span>
            <span class="cal-stats-item">上班 <strong>{{ monthStats.workDays }}</strong> 天</span>
            <span class="cal-stats-divider"></span>
            <span class="cal-stats-item">请假 <strong>{{ monthStats.leaveDays }}</strong> 天</span>
          </div>
          <div class="cal-stats-overtime">其中加班 <strong>{{ monthStats.overtimeDays }}</strong> 天</div>
        </div>

        <!-- 工具 -->
        <div class="cal-tools-card">
          <div class="cal-tools-title">工具</div>
          <el-button text class="cal-tools-btn" @click="showCalcDlg = true">
            <el-icon><DataAnalysis /></el-icon> 出勤计算器
          </el-button>
        </div>
      </div>

      <!-- 右侧详情 -->
      <div class="cal-detail">
        <template v-if="selectedDate && !batchMode && !deleteBatchMode">
          <div class="cal-detail-header"><h3>{{ formatDateFull(selectedDate) }}</h3></div>
          <div v-if="checkinsByDate[selectedDate]?.length" class="cal-checkins">
            <div v-for="chk in checkinsByDate[selectedDate]" :key="chk.id" class="cal-checkin-card">
              <div class="cal-cc-top">
                <template v-for="p in chk.projects" :key="p.id">
                  <span class="cal-cc-project">{{ p.name }}</span>
                </template>
                <span class="cal-cc-time">{{ dayjs.utc(chk.created_at).utcOffset(8).format('HH:mm') }}</span>
                <el-button size="small" text type="danger" @click="removeCheckin(chk)"><el-icon><Delete /></el-icon></el-button>
              </div>
              <div v-if="chk.tasks?.length" class="cal-cc-tasks">
                <span v-for="t in chk.tasks" :key="t.id" class="cal-cc-task">{{ t.title }}</span>
              </div>
              <div class="cal-cc-content">{{ chk.content || '已签到' }}</div>
            </div>
          </div>
          <el-empty v-else description="该日无签到记录" :image-size="60" />
        </template>
        <template v-else-if="deleteBatchMode">
          <div class="cal-detail-header"><h3>批量删除签到</h3></div>
          <p style="font-size:13px;color:#888;line-height:1.6">
            请在左侧日历中点击<span style="color:#f56c6c;font-weight:500">已有签到</span>的日期进行选择，
            选完后点击「删除选中」按钮批量删除。
          </p>
          <div v-if="deleteDates.length" style="margin-top:16px">
            <p style="font-size:13px;font-weight:500;color:#f56c6c;margin-bottom:8px">已选 {{ deleteDates.length }} 天：</p>
            <div v-for="d in deleteDates" :key="d" class="delete-date-item">
              <span>{{ d }}</span>
              <span style="color:#999;font-size:12px">{{ checkinsByDate[d]?.length || 0 }} 条记录</span>
            </div>
          </div>
        </template>
        <el-empty v-else-if="!batchMode" description="点击日期查看签到记录" :image-size="60" />
      </div>
    </div>

    <!-- 单次签到对话框 -->
    <el-dialog v-model="showCheckinDlg" :title="editingCheckinId ? '编辑签到' : '签到'" width="500px" @close="resetCheckinForm">
      <div style="font-size:13px;color:#534ab7;margin-bottom:12px;font-weight:500">签到日期：{{ checkinForm.date }}</div>
      <el-form :model="checkinForm" label-width="90px">
        <el-form-item label="多项目">
          <el-switch v-model="checkinForm.multi_project" @change="onMultiChange" />
          <span style="margin-left:8px;font-size:12px;color:#888">开启后可选择多个项目</span>
        </el-form-item>
        <el-form-item :label="checkinForm.multi_project ? '项目' : '项目'" required>
          <el-select v-model="projectSelectModel" :multiple="checkinForm.multi_project" placeholder="选择项目" style="width:100%" @change="onProjectChange">
            <el-option v-for="p in projects" :key="p.id" :value="p.id" :label="p.name">
              <span class="status-dot" :class="hasProjectUpdateToday(p.id) ? 'dot-green' : 'dot-gray'"></span>
              {{ p.name }}
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="相关任务">
          <el-select v-model="checkinForm.task_ids" multiple placeholder="可选，可多选" style="width:100%">
            <el-option v-for="t in tasksForSelected" :key="t.id" :value="t.id" :label="t.title">
              <span class="status-dot" :class="hasTaskUpdateToday(t.id) ? 'dot-green' : 'dot-gray'"></span>
              {{ t.title }}
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="工作记录">
          <el-input v-model="checkinForm.content" type="textarea" :rows="4" placeholder="今天做了什么？" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCheckinDlg = false">取消</el-button>
        <el-button type="primary" :loading="checkinLoading" @click="submitCheckin">{{ editingCheckinId ? '保存' : '签到' }}</el-button>
      </template>
    </el-dialog>

    <!-- 批量签到对话框 -->
    <el-dialog v-model="showBatchDlg" title="批量签到" width="500px" @close="resetBatchForm">
      <div style="font-size:13px;color:#534ab7;margin-bottom:12px;font-weight:500">签到日期：共 {{ batchDates.length }} 天（{{ batchDates[0] }} ~ {{ batchDates[batchDates.length-1] }}）</div>
      <el-form :model="batchForm" label-width="90px">
        <el-form-item label="多项目">
          <el-switch v-model="batchForm.multi_project" @change="onBatchMultiChange" />
        </el-form-item>
        <el-form-item label="项目" required>
          <el-select v-model="batchProjectModel" :multiple="batchForm.multi_project" placeholder="选择项目" style="width:100%" @change="onBatchProjectChange">
            <el-option v-for="p in projects" :key="p.id" :value="p.id" :label="p.name">
              <span class="status-dot" :class="hasProjectUpdateToday(p.id) ? 'dot-green' : 'dot-gray'"></span>
              {{ p.name }}
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="相关任务">
          <el-select v-model="batchForm.task_ids" multiple placeholder="可选" style="width:100%">
            <el-option v-for="t in batchTasks" :key="t.id" :value="t.id" :label="t.title">
              <span class="status-dot" :class="hasTaskUpdateToday(t.id) ? 'dot-green' : 'dot-gray'"></span>
              {{ t.title }}
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="工作记录">
          <el-input v-model="batchForm.content" type="textarea" :rows="4" placeholder="所有选中日期共用此记录" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBatchDlg = false">取消</el-button>
        <el-button type="primary" :loading="batchLoading" @click="submitBatch">确定（{{ batchDates.length }} 天）</el-button>
      </template>
    </el-dialog>

    <!-- 出勤计算器 -->
    <el-dialog v-model="showCalcDlg" title="出勤计算器" width="680px" top="5vh">
      <div class="calc-range">
        <span style="font-size:13px;color:#888;margin-right:8px">统计范围</span>
        <el-date-picker
          v-model="calcStart"
          type="date"
          placeholder="开始日期"
          value-format="YYYY-MM-DD"
          style="width:150px"
          :disabled-date="disabledCalcStart"
          @change="onCalcDateChange"
        />
        <span style="margin:0 8px;color:#888">至</span>
        <el-date-picker
          v-model="calcEnd"
          type="date"
          placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width:150px"
          :disabled-date="disabledCalcEnd"
          @change="onCalcDateChange"
        />
        <el-button size="small" type="primary" style="margin-left:8px" @click="runCalc">计算</el-button>
        <el-button size="small" type="success" plain style="margin-left:8px" :disabled="!calcResult" @click="exportDetailXLSX">
          <el-icon><Download /></el-icon> 导出明细
        </el-button>
      </div>

      <template v-if="calcResult">
        <!-- 总统计 -->
        <div class="calc-summary">
          <div class="calc-summary-item">
            <span class="calc-summary-num" style="color:#534ab7">{{ calcResult.total.workDays }}</span>
            <span class="calc-summary-label">上班</span>
          </div>
          <div class="calc-summary-item">
            <span class="calc-summary-num" style="color:#e67e22">{{ calcResult.total.leaveDays }}</span>
            <span class="calc-summary-label">请假</span>
          </div>
          <div class="calc-summary-item">
            <span class="calc-summary-num" style="color:#d48806">{{ calcResult.total.overtimeDays }}</span>
            <span class="calc-summary-label">加班</span>
          </div>
        </div>
        <div v-if="calcResult.total.estimatedDays > 0" class="calc-estimated-note">
          其中 <strong>{{ calcResult.total.estimatedDays }}</strong> 天为未来日期默认预估
        </div>

        <!-- 按月详情 -->
        <div v-if="calcResult.monthly.length" class="calc-section">
          <div class="calc-section-title">按月统计</div>
          <div class="calc-month-grid">
            <div v-for="m in calcResult.monthly" :key="m.month" class="calc-month-card">
              <div class="calc-month-name">
                {{ m.month }}
                <span v-if="m.estimatedDays" class="calc-estimated-tag">预估 {{ m.estimatedDays }} 天</span>
              </div>
              <div class="calc-month-row">上班 <strong style="color:#534ab7">{{ m.workDays }}</strong> 天</div>
              <div class="calc-month-row">请假 <strong style="color:#e67e22">{{ m.leaveDays }}</strong> 天</div>
              <div class="calc-month-row">加班 <strong style="color:#d48806">{{ m.overtimeDays }}</strong> 天</div>
            </div>
          </div>
        </div>

        <!-- 按项目统计 -->
        <div v-if="calcResult.byProject.length" class="calc-section">
          <div class="calc-section-title">按项目统计</div>
          <div class="calc-proj-grid">
            <div v-for="p in calcResult.byProject" :key="p.projectId" class="calc-proj-card">
              <span class="calc-proj-name">{{ p.projectName }}</span>
              <span class="calc-proj-days"><strong>{{ p.days }}</strong> 天</span>
            </div>
          </div>
        </div>

        <!-- 多项目签到提醒 -->
        <div v-if="calcResult.multiProjectDays?.length" class="calc-section">
          <div class="calc-section-title calc-section-title-warn">
            <el-icon style="margin-right:4px"><WarningFilled /></el-icon> 多项目签到提醒
          </div>
          <div class="calc-warn-grid">
            <div v-for="item in calcResult.multiProjectDays" :key="item.date" class="calc-warn-item">
              <div class="calc-warn-top">
                <span class="calc-warn-date">{{ item.dateLabel }}</span>
                <span class="calc-warn-weekday">周{{ item.weekday }}</span>
              </div>
              <div class="calc-warn-projs">
                <span v-for="(name, idx) in item.projectNames" :key="idx" class="calc-warn-proj">{{ name }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>

      <template v-else>
        <el-empty description="选择日期范围后点击「计算」" :image-size="50" style="padding:30px 0" />
      </template>
    </el-dialog>

    <!-- 日历设置 -->
    <el-dialog v-model="showHolidaySettings" title="日历设置" width="580px" top="5vh" @opened="initHolidaySettings">

      <div class="hs-tabs">
        <span class="hs-tab" :class="{ active: hsActiveTab === 'general' }" @click="hsActiveTab = 'general'">通用</span>
        <span class="hs-tab" :class="{ active: hsActiveTab === 'holiday' }" @click="hsActiveTab = 'holiday'">节假日</span>
      </div>

      <template v-if="hsActiveTab === 'general'">
        <!-- 通用设置 -->
        <div class="hs-entry">
          <span class="hs-entry-label">入职日期</span>
          <el-date-picker v-model="entryDateVal" type="date" placeholder="不设置则显示全部" value-format="YYYY-MM-DD" style="width:150px" @change="onEntryDateChange" />
          <el-button v-if="entryDateVal" size="small" text @click="clearEntryDate">清除</el-button>
        </div>
      </template>

      <template v-if="hsActiveTab === 'holiday'">
        <!-- 日历 -->
        <div class="hs-header">
          <div class="hs-nav">
            <el-button size="small" text @click="hsPrev"><el-icon><ArrowLeft /></el-icon></el-button>
            <span class="hs-month">{{ hsYear }}年{{ hsMonth }}月</span>
            <el-button size="small" text @click="hsNext"><el-icon><ArrowRight /></el-icon></el-button>
          </div>
          <div class="hs-legend">
            <span class="hs-tag hs-tag-normal">工作日</span>
            <span class="hs-tag hs-tag-holiday">法定假</span>
            <span class="hs-tag hs-tag-workday">调休班</span>
            <span class="hs-tag hs-tag-off">休息日</span>
            <span class="hs-override-hint">⬤ 已手动设置</span>
          </div>
        </div>
        <div class="hs-weekdays">
          <div v-for="w in weekDays" :key="w" class="hs-weekday">{{ w }}</div>
        </div>
        <div class="hs-grid">
          <div
            v-for="(cell, i) in hsDays"
            :key="i"
            class="hs-cell"
            :class="{
              'hs-cell-empty': cell.empty,
              'hs-cell-override': cell.overridden,
            }"
            @click="cycleHoliday(cell)"
          >
            <template v-if="!cell.empty">
              <span class="hs-num">{{ cell.day }}</span>
              <span class="hs-tag-sm" :class="'hs-ts-' + cell.effective">{{ hsTypeLabel(cell.effective) }}</span>
              <span v-if="cell.overridden" class="hs-override-dot"></span>
            </template>
          </div>
        </div>
      </template>

      <template #footer>
        <span class="hs-auto-save">自动保存 · 关闭后实时更新</span>
        <el-button v-if="hsActiveTab === 'holiday'" size="small" @click="hsResetMonth">重置本月</el-button>
        <el-button type="primary" @click="showHolidaySettings = false">完成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { DataAnalysis, WarningFilled, Setting, Download } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import utc from 'dayjs/plugin/utc'
dayjs.extend(utc)
dayjs.locale('zh-cn')
import {
  getProjects, getAllCheckins, getTodayCheckinStatus, createCheckin, updateCheckin, deleteCheckin, batchDeleteCheckins, getTasks, exportAttendanceExcel,
} from '../api'
import { loadHolidayData, getDayExtraInfo, setHolidayOverride, getHolidayOverride, getAllOverrides, getEntryDate, setEntryDate, loadUserSettingsFromServer } from '../utils/holiday'

const projects = ref([])
const allCheckins = ref([])
const showCheckinDlg = ref(false)
const checkinLoading = ref(false)
const selectedDate = ref(null)
const tasksForSelected = ref([])
const checkinForm = ref({ project_ids: [], task_ids: [], multi_project: false, date: null, content: '' })
const editingCheckinId = ref(null) // 编辑已有签到时记录 ID

// 批量签到
const batchMode = ref(false)
const batchDates = ref([])
const showBatchDlg = ref(false)
const batchLoading = ref(false)
const batchForm = ref({ project_ids: [], task_ids: [], multi_project: false, content: '' })
const batchTasks = ref([])

// 批量删除签到（日历选日期模式）
const deleteBatchMode = ref(false)
const deleteDates = ref([])

const calYear = ref(dayjs().year())
const calMonth = ref(dayjs().month() + 1)
const weekDays = ['一', '二', '三', '四', '五', '六', '日']
const todayStr = dayjs().format('YYYY-MM-DD')

// 节假日数据
// 初始即为 1：日历立即渲染（基于已缓存/周末推断数据），
// 待节假日数据（服务端/本地/接口）到达后再 ++ 刷新徽标，不再卡在骨架占位。
const holidayVersion = ref(1)
// 数据库签到数据就绪标志：网格照常秒开，但"出勤/请假/加班"状态徽标与出勤统计
// 在签到数据返回前保持中性，避免首屏把过去工作日全算成"请假"的一闪假状态。
const dataReady = ref(false)
const loadHolidayForYear = async (year) => {
  await loadHolidayData(year)
  // 也预加载前后一年，方便月份切换
  await Promise.all([loadHolidayData(year - 1), loadHolidayData(year + 1)].filter(Boolean))
}

// 出勤计算器
const showCalcDlg = ref(false)
const calcStart = ref(null)
const calcEnd = ref(null)
const calcResult = ref(null)

const onCalcDateChange = () => { calcResult.value = null }
// 入职日之前的日期不可选
const entryBefore = (date) => {
  const entryDateStr = getEntryDate()
  return entryDateStr ? dayjs(date).isBefore(dayjs(entryDateStr)) : false
}
// 开始日期：不早于入职日、不晚于结束日期
const disabledCalcStart = (date) => {
  if (entryBefore(date)) return true
  if (calcEnd.value && dayjs(date).isAfter(dayjs(calcEnd.value))) return true
  return false
}
// 结束日期：不早于入职日、不早于开始日期
const disabledCalcEnd = (date) => {
  if (entryBefore(date)) return true
  if (calcStart.value && dayjs(date).isBefore(dayjs(calcStart.value))) return true
  return false
}
const runCalc = async () => {
  if (!calcStart.value || !calcEnd.value) {
    ElMessage.warning('请选择开始和结束日期')
    return
  }
  const startStr = calcStart.value
  const endStr = calcEnd.value
  const start = dayjs(startStr)
  const end = dayjs(endStr)
  if (end.isBefore(start)) { ElMessage.warning('结束日期不能早于开始日期'); return }

  // 拉取整个日期范围的签到数据
  const rangeCheckins = await getAllCheckins({ start_date: startStr, end_date: endStr })
  // 按日期建索引
  const rangeCheckinsByDate = {}
  for (const c of rangeCheckins) {
    const d = dayjs(c.date).format('YYYY-MM-DD')
    if (!rangeCheckinsByDate[d]) rangeCheckinsByDate[d] = []
    rangeCheckinsByDate[d].push(c)
  }

  const byMonth = {}
  const byProject = {}
  const multiProjectDays = [] // 多项目签到的日期列表
  const days = [] // 逐日明细
  let totalWork = 0, totalLeave = 0, totalOvertime = 0, totalEstimated = 0
  const today = dayjs().startOf('day')

  for (let d = start; d.isBefore(end) || d.isSame(end); d = d.add(1, 'day')) {
    const dateStr = d.format('YYYY-MM-DD')
    const weekday = d.day()
    const extra = getDayExtraInfo(dateStr)
    const dayCheckins = rangeCheckinsByDate[dateStr] || []
    const hasCheckin = dayCheckins.length > 0
    const dayProjectNames = []
    for (const chk of dayCheckins) {
      for (const p of chk.projects || []) {
        if (!dayProjectNames.includes(p.name)) dayProjectNames.push(p.name)
      }
    }
    const isFuture = d.isAfter(today)
    const monthKey = d.format('YYYY年M月')
    const entryDateStr = getEntryDate()
    const beforeEntry = entryDateStr && dateStr < entryDateStr

    if (beforeEntry) continue

    if (!byMonth[monthKey]) byMonth[monthKey] = { workDays: 0, leaveDays: 0, overtimeDays: 0, estimatedDays: 0 }

    if (hasCheckin) {
      totalWork++
      byMonth[monthKey].workDays++

      // 按项目统计：每个签到记录的项目
      const dayProjects = new Set()
      for (const chk of dayCheckins) {
        for (const p of chk.projects || []) {
          if (!byProject[p.id]) byProject[p.id] = { projectName: p.name, days: 0 }
          byProject[p.id].days++
          dayProjects.add(p.id)
        }
      }
      // 检查当天是否涉及多个项目
      if (dayProjects.size >= 2) {
        const projectNames = []
        for (const chk of dayCheckins) {
          for (const p of chk.projects || []) {
            if (!projectNames.includes(p.name)) projectNames.push(p.name)
          }
        }
        multiProjectDays.push({
          date: dateStr,
          dateLabel: d.format('M月D日'),
          weekday: ['日','一','二','三','四','五','六'][weekday],
          projectCount: dayProjects.size,
          projectNames,
        })
      }
    } else if (isFuture) {
      // 未来日期：默认工作日已上班
      // 判断当日有效类型
      let effIsRest
      if (extra.override === 'off') effIsRest = true
      else if (extra.override === 'normal') effIsRest = false
      else if (extra.badgeType === 'workday') effIsRest = false
      else if (extra.badgeType === 'holiday') effIsRest = true
      else if (weekday === 0 || weekday === 6) effIsRest = true
      else effIsRest = false

      if (!effIsRest) {
        totalWork++
        totalEstimated++
        byMonth[monthKey].workDays++
        byMonth[monthKey].estimatedDays++
      }
    }

    // 请假与加班统计
    let effIsRest
    if (extra.override === 'off') effIsRest = true
    else if (extra.override === 'normal') effIsRest = false
    else if (extra.badgeType === 'workday') effIsRest = false
    else if (extra.badgeType === 'holiday') effIsRest = true
    else if (weekday === 0 || weekday === 6) effIsRest = true
    else effIsRest = false

    if (effIsRest) {
      if (hasCheckin) { totalOvertime++; byMonth[monthKey].overtimeDays++ }
    } else {
      if (!hasCheckin && !isFuture) { totalLeave++; byMonth[monthKey].leaveDays++ }
    }

    // 逐日明细
    let dayType
    if (hasCheckin) dayType = effIsRest ? '加班' : '上班'
    else if (effIsRest) dayType = '休息'
    else if (isFuture) dayType = '预估上班'
    else dayType = '请假'
    days.push({
      date: dateStr,
      weekday: ['日', '一', '二', '三', '四', '五', '六'][weekday],
      type: dayType,
      projectNames: dayProjectNames,
      estimated: dayType === '预估上班',
    })
  }

  calcResult.value = {
    total: { workDays: totalWork, leaveDays: totalLeave, overtimeDays: totalOvertime, estimatedDays: totalEstimated },
    monthly: Object.entries(byMonth).map(([month, data]) => ({ month, ...data })),
    byProject: Object.values(byProject).sort((a, b) => b.days - a.days),
    multiProjectDays,
    days,
  }
}

// 将出勤计算结果发送到后端，由 openpyxl 生成含原生图表的 Excel 并下载
const exportDetailXLSX = async () => {
  if (!calcResult.value) { ElMessage.warning('请先计算'); return }
  try {
    const res = await exportAttendanceExcel({
      start: calcStart.value,
      end: calcEnd.value,
      result: calcResult.value,
    })
    const blob = new Blob([res.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const rangeStr = (calcStart.value && calcEnd.value) ? `${calcStart.value}_${calcEnd.value}` : dayjs().format('YYYY-MM-DD')
    a.download = `出勤明细_${rangeStr}.xlsx`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('Excel 已导出')
  } catch (e) {
    console.error(e)
    ElMessage.error('导出失败：' + (e && e.message ? e.message : e))
  }
}

// 当日更新状态指示 — 基于当前签到日期
const todayUpdateStatus = ref({ project_ids: [], task_ids: [] })
const loadStatusForDate = async (date) => {
  try { todayUpdateStatus.value = await getTodayCheckinStatus(date || undefined) } catch {}
}
const hasProjectUpdateToday = (pid) => todayUpdateStatus.value.project_ids?.includes(pid)
const hasTaskUpdateToday = (tid) => todayUpdateStatus.value.task_ids?.includes(tid)

// ---- v-model 代理 ----
const projectSelectModel = computed({
  get: () => checkinForm.value.multi_project ? checkinForm.value.project_ids : (checkinForm.value.project_ids[0] || null),
  set: (val) => { checkinForm.value.project_ids = Array.isArray(val) ? val : (val != null ? [val] : []) },
})
const batchProjectModel = computed({
  get: () => batchForm.value.multi_project ? batchForm.value.project_ids : (batchForm.value.project_ids[0] || null),
  set: (val) => { batchForm.value.project_ids = Array.isArray(val) ? val : (val != null ? [val] : []) },
})

const checkinsByDate = computed(() => {
  const map = {}
  for (const c of allCheckins.value) {
    const d = dayjs(c.date).format('YYYY-MM-DD')
    if (!map[d]) map[d] = []
    map[d].push(c)
  }
  return map
})

// 农历/节日信息缓存：整个月的数据预先计算一次，calendarDays 和 monthStats 共享
const monthExtraInfo = computed(() => {
  // eslint-disable-next-line no-unused-expressions
  holidayVersion.value
  const year = calYear.value
  const month = calMonth.value
  const daysInMonth = dayjs(`${year}-${month}-01`).daysInMonth()
  const cache = {}
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = dayjs(`${year}-${month}-${d}`).format('YYYY-MM-DD')
    cache[d] = getDayExtraInfo(dateStr)
  }
  return cache
})

const calendarDays = computed(() => {
  // eslint-disable-next-line no-unused-expressions
  holidayVersion.value // 依赖版本号，数据加载后重新计算
  dataReady.value      // 签到数据未就绪时状态徽标保持中性
  const entryDateStr = getEntryDate() // 入职日期
  const firstDay = dayjs(`${calYear.value}-${calMonth.value}-01`)
  const daysInMonth = firstDay.daysInMonth()
  const startWeekday = (firstDay.day() + 6) % 7 // 周一为第一列
  const cells = []
  // 月初空白占位
  for (let i = 0; i < startWeekday; i++) {
    cells.push({ empty: true, isCurrent: false, isToday: false })
  }
  // 当月日期
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = firstDay.date(d).format('YYYY-MM-DD')
    const beforeEntry = entryDateStr && dateStr < entryDateStr
    const weekday = dayjs(dateStr).day()
    const extra = monthExtraInfo.value[d] // 从缓存获取
    const hasCheckin = !!checkinsByDate.value[dateStr]
    const isFuture = dayjs(dateStr).isAfter(dayjs().startOf('day'))

    // 判断当日有效类型（覆盖优先于默认）
    let effectiveIsRest
    if (extra.override === 'off') effectiveIsRest = true
    else if (extra.override === 'normal') effectiveIsRest = false
    else if (extra.badgeType === 'workday') effectiveIsRest = false
    else if (extra.badgeType === 'holiday') effectiveIsRest = true
    else if (weekday === 0 || weekday === 6) effectiveIsRest = true
    else effectiveIsRest = false

    let statusType = null
    if (dataReady.value && !isFuture && !beforeEntry) {
      if (effectiveIsRest) {
        if (hasCheckin) statusType = 'overtime'
      } else {
        statusType = hasCheckin ? 'attendance' : 'leave'
      }
    }

    cells.push({
      num: d,
      date: dateStr,
      isCurrent: true,
      isToday: dateStr === todayStr,
      holiday: extra,
      status: statusType,
    })
  }
  // 月末空白占位
  const remaining = 42 - cells.length
  for (let i = 0; i < remaining; i++) {
    cells.push({ empty: true, isCurrent: false, isToday: false })
  }
  return cells
})

// 月份出勤统计
const monthStats = computed(() => {
  // eslint-disable-next-line no-unused-expressions
  holidayVersion.value // 依赖版本号，自定义覆盖更新后重新计算
  dataReady.value      // 签到数据未就绪时返回中性占位，避免首屏闪现"全缺勤"
  if (!dataReady.value) {
    const daysInMonth = dayjs(`${calYear.value}-${calMonth.value}-01`).daysInMonth()
    return { workDays: 0, leaveDays: 0, overtimeDays: 0, requiredWorkDays: 0, absences: 0, total: daysInMonth, isCurrent: false, loading: true }
  }
  const year = calYear.value
  const month = calMonth.value
  const daysInMonth = dayjs(`${year}-${month}-01`).daysInMonth()
  const today = dayjs()
  const isCurrent = year === today.year() && month === today.month() + 1
  const monthStart = dayjs(`${year}-${month}-01`)
  const isFutureMonth = monthStart.isAfter(today, 'day') // 月份第一天在今天之后 → 整月未到来
  const lastDay = isCurrent ? today.date() : daysInMonth

  let workDays = 0        // 有签到记录的总天数（含加班）
  let leaveDays = 0        // 应上班但没签到
  let overtimeDays = 0
  let requiredWorkDays = 0 // 应上班天数（排除周末/节假日/手动假日）

  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = dayjs(`${year}-${month}-${d}`).format('YYYY-MM-DD')
    const weekday = dayjs(dateStr).day()
    const extra = monthExtraInfo.value[d] // 从缓存获取
    const hasCheckin = !!checkinsByDate.value[dateStr]
    const entryDateStr = getEntryDate()
    const beforeEntry = entryDateStr && dateStr < entryDateStr

    if (beforeEntry) continue // 入职前不统计

    // 判断当日有效类型（覆盖优先于默认）
    let effectiveIsRest
    if (extra.override === 'off') effectiveIsRest = true
    else if (extra.override === 'normal') effectiveIsRest = false
    else if (extra.badgeType === 'workday') effectiveIsRest = false
    else if (extra.badgeType === 'holiday') effectiveIsRest = true
    else if (weekday === 0 || weekday === 6) effectiveIsRest = true
    else effectiveIsRest = false

    if (!effectiveIsRest) requiredWorkDays++

    if (d > lastDay) continue // 今天之后的日期不统计签到/请假/加班

    if (hasCheckin) workDays++

    if (effectiveIsRest) {
      if (hasCheckin) overtimeDays++
    } else {
      if (!hasCheckin) leaveDays++
    }
  }

  // 整月未到来时清零签到相关统计，仅保留应出勤
  if (isFutureMonth) {
    workDays = 0
    leaveDays = 0
    overtimeDays = 0
  }

  const absences = requiredWorkDays - workDays // 应出勤 - 实际出勤 = 缺勤天数

  return { workDays, leaveDays, overtimeDays, requiredWorkDays, absences, total: lastDay, isCurrent }
})

const load = async () => {
  // 按当前年月过滤签到数据，避免全量加载
  const [p, c] = await Promise.all([
    getProjects(),
    getAllCheckins({ year: calYear.value, month: calMonth.value }),
    loadHolidayForYear(calYear.value),
  ])
  projects.value = p
  allCheckins.value = c
  dataReady.value = true // 签到数据已就绪，状态徽标与出勤统计可正常显示
  selectedDate.value = todayStr
  loadStatusForDate(todayStr)
}
onMounted(async () => {
  // 并行：从 settings.json/DB 加载节假日覆盖 + 主数据
  // 注：loadUserSettingsFromServer 已包含全量覆盖加载，无需再调用 loadAllOverridesFromDb（重复 DB 请求）
  await Promise.all([
    loadUserSettingsFromServer(),
    load(),
  ])
  holidayVersion.value++
})

const formatDateFull = (d) => dayjs(d).format('YYYY年M月D日 dddd')

const prevMonth = async () => {
  const newMonth = calMonth.value === 1 ? 12 : calMonth.value - 1
  const newYear  = calMonth.value === 1 ? calYear.value - 1 : calYear.value
  const [newCheckins] = await Promise.all([
    getAllCheckins({ year: newYear, month: newMonth }),
    loadHolidayForYear(newYear),
  ])
  calYear.value = newYear
  calMonth.value = newMonth
  allCheckins.value = newCheckins
  holidayVersion.value++
}
const nextMonth = async () => {
  const newMonth = calMonth.value === 12 ? 1 : calMonth.value + 1
  const newYear  = calMonth.value === 12 ? calYear.value + 1 : calYear.value
  const [newCheckins] = await Promise.all([
    getAllCheckins({ year: newYear, month: newMonth }),
    loadHolidayForYear(newYear),
  ])
  calYear.value = newYear
  calMonth.value = newMonth
  allCheckins.value = newCheckins
  holidayVersion.value++
}
const goToday = async () => {
  const targetYear  = dayjs().year()
  const targetMonth = dayjs().month() + 1
  const [newCheckins] = await Promise.all([
    getAllCheckins({ year: targetYear, month: targetMonth }),
    loadHolidayForYear(targetYear),
  ])
  calYear.value = targetYear
  calMonth.value = targetMonth
  selectedDate.value = todayStr
  allCheckins.value = newCheckins
  holidayVersion.value++
}

// 日历设置
const showHolidaySettings = ref(false)
const hsActiveTab = ref('general')
const hsYear = ref(dayjs().year())
const hsMonth = ref(dayjs().month() + 1)
const entryDateVal = ref(getEntryDate())

const initHolidaySettings = () => { hsYear.value = calYear.value; hsMonth.value = calMonth.value; entryDateVal.value = getEntryDate(); hsActiveTab.value = 'general' }
const onEntryDateChange = (val) => { setEntryDate(val || null); holidayVersion.value++ }
const clearEntryDate = () => { entryDateVal.value = null; setEntryDate(null); holidayVersion.value++ }

// 供日历和计算器使用的计算属性
const hsPrev = () => { if (hsMonth.value === 1) { hsYear.value--; hsMonth.value = 12 } else hsMonth.value-- }
const hsNext = () => { if (hsMonth.value === 12) { hsYear.value++; hsMonth.value = 1 } else hsMonth.value++ }

const hsDays = computed(() => {
  // eslint-disable-next-line no-unused-expressions
  holidayVersion.value // 依赖版本号，覆盖数据更新后重新计算
  const firstDay = dayjs(`${hsYear.value}-${hsMonth.value}-01`)
  const daysInMonth = firstDay.daysInMonth()
  const startWeekday = (firstDay.day() + 6) % 7
  const cells = []
  // 提前解析整年节假日数据，避免每单元格重复 JSON.parse
  const yearKey = `taskm_holiday_${hsYear.value}`
  const yearData = (() => {
    try {
      const stored = localStorage.getItem(yearKey)
      return stored ? JSON.parse(stored)?.data : null
    } catch { return null }
  })()
  for (let i = 0; i < startWeekday; i++) cells.push({ empty: true })
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = firstDay.date(d).format('YYYY-MM-DD')
    const mmdd = dateStr.slice(5)
    const defaultInfo = yearData?.[mmdd] || null
    const override = getHolidayOverride(dateStr)
    // 计算生效状态
    let effective
    if (override) {
      effective = override
    } else if (defaultInfo) {
      effective = defaultInfo.holiday ? 'holiday' : 'workday'
    } else {
      effective = (dayjs(dateStr).day() === 0 || dayjs(dateStr).day() === 6) ? 'off' : 'normal'
    }
    cells.push({
      day: d,
      dateStr,
      default: defaultInfo,
      override,
      effective,
      overridden: !!override,
    })
  }
  const remaining = 42 - cells.length
  for (let i = 0; i < remaining; i++) cells.push({ empty: true })
  return cells
})

const cycleHoliday = (cell) => {
  if (cell.empty) return
  const order = ['normal', 'holiday', 'workday', 'off']
  const idx = order.indexOf(cell.effective)
  const next = order[(idx + 1) % order.length]
  // 如果下个状态和默认状态相同，清除覆盖
  const isDefault = (() => {
    if (!cell.default) return false
    if (next === 'holiday') return cell.default.holiday
    if (next === 'workday') return !cell.default.holiday
    return false
  })()
  if (isDefault) {
    setHolidayOverride(cell.dateStr, null)
  } else {
    setHolidayOverride(cell.dateStr, next)
  }
  holidayVersion.value++ // 触发日历重算
}

const hsTypeLabel = (type) => {
  const map = { normal: '工作日', holiday: '法定假', workday: '调休班', off: '休息日' }
  return map[type] || ''
}

const hsResetMonth = () => {
  const prefix = `${hsYear.value}-${String(hsMonth.value).padStart(2, '0')}`
  const all = getAllOverrides()
  for (const key of Object.keys(all)) {
    if (key.startsWith(prefix)) setHolidayOverride(key, null)
  }
  holidayVersion.value++
}

// ---- 单次签到 ----
const resetCheckinForm = () => {
  editingCheckinId.value = null
  const lastPid = localStorage.getItem('taskm_last_project')
  checkinForm.value = { project_ids: lastPid ? [Number(lastPid)] : [], task_ids: [], multi_project: false, date: null, content: '' }
  tasksForSelected.value = []
  if (lastPid) loadTasksForProjects([Number(lastPid)])
}
const openCheckinDialog = () => {
  const date = selectedDate.value || todayStr
  resetCheckinForm()
  checkinForm.value.date = date
  loadStatusForDate(date)  // 加载该日期的更新状态
  // 如果该日已有签到记录，预填数据视为编辑
  const existing = checkinsByDate.value[date]?.[0]
  if (existing) {
    editingCheckinId.value = existing.id
    checkinForm.value.project_ids = existing.projects.map((p) => p.id)
    checkinForm.value.task_ids = existing.tasks.map((t) => t.id)
    checkinForm.value.multi_project = existing.multi_project
    checkinForm.value.content = existing.content
    loadTasksForProjects(checkinForm.value.project_ids)
  }
  showCheckinDlg.value = true
}
const onMultiChange = () => { checkinForm.value.project_ids = []; checkinForm.value.task_ids = []; tasksForSelected.value = [] }
const onProjectChange = () => {
  const ids = checkinForm.value.project_ids
  checkinForm.value.task_ids = []
  if (ids.length) { localStorage.setItem('taskm_last_project', ids[0]); loadTasksForProjects(ids) }
  else tasksForSelected.value = []
}
const loadTasksForProjects = async (pids) => {
  const results = await Promise.all(pids.map(async (pid) => {
    try {
      const proj = projects.value.find((p) => p.id === pid)
      if (!proj) return []
      const ts = await getTasks(proj.display_id || pid)
      return ts.map((t) => ({ ...t, _projectLabel: proj.name }))
    } catch { return [] }
  }))
  tasksForSelected.value = results.flat()
}
const submitCheckin = async () => {
  if (!checkinForm.value.project_ids.length) { ElMessage.warning('请选择项目'); return }
  checkinLoading.value = true
  try {
    if (editingCheckinId.value) {
      await updateCheckin(editingCheckinId.value, checkinForm.value)
      ElMessage.success('签到已更新')
    } else {
      await createCheckin(checkinForm.value)
      ElMessage.success('签到成功')
    }
    showCheckinDlg.value = false
    allCheckins.value = await getAllCheckins({ year: calYear.value, month: calMonth.value })
    loadStatusForDate(selectedDate.value)
  } finally { checkinLoading.value = false }
}
const removeCheckin = async (chk) => {
  await deleteCheckin(chk.projects?.[0]?.display_id || chk.projects?.[0]?.id || 0, chk.id)
  allCheckins.value = await getAllCheckins({ year: calYear.value, month: calMonth.value })
  loadStatusForDate(selectedDate.value)
}

// ---- 批量删除签到（日历选日期） ----
const toggleDeleteBatchMode = () => {
  deleteBatchMode.value = !deleteBatchMode.value
  if (!deleteBatchMode.value) deleteDates.value = []
  else if (batchMode.value) { batchMode.value = false; batchDates.value = [] }
}
const confirmBatchDelete = async () => {
  if (!deleteDates.value.length) return
  // 收集所有选中日期的签到 ID
  const ids = []
  for (const d of deleteDates.value) {
    const records = checkinsByDate.value[d] || []
    for (const r of records) ids.push(r.id)
  }
  if (!ids.length) { ElMessage.warning('未找到可删除的签到记录'); return }
  try {
    await ElMessageBox.confirm(
      `确定删除 ${deleteDates.value.length} 天的共 ${ids.length} 条签到记录？此操作不可恢复。`,
      '确认批量删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }
  await batchDeleteCheckins(ids)
  ElMessage.success(`已删除 ${ids.length} 条签到记录（${deleteDates.value.length} 天）`)
  deleteDates.value = []
  allCheckins.value = await getAllCheckins({ year: calYear.value, month: calMonth.value })
  loadStatusForDate(selectedDate.value)
}

// ---- 批量签到 ----
const toggleBatchMode = () => {
  batchMode.value = !batchMode.value
  if (!batchMode.value) batchDates.value = []
}
const onCellClick = (day) => {
  if (day.empty) return
  if (batchMode.value) {
    // 批量签到模式：已有签到的日期不可选
    if (!day.isCurrent || checkinsByDate[day.date]) return
    const idx = batchDates.value.indexOf(day.date)
    if (idx >= 0) batchDates.value.splice(idx, 1)
    else batchDates.value.push(day.date)
    batchDates.value.sort()
  } else if (deleteBatchMode.value) {
    // 批量删除模式：仅已有签到的日期可选
    if (!day.isCurrent || !checkinsByDate.value[day.date]) return
    const idx = deleteDates.value.indexOf(day.date)
    if (idx >= 0) deleteDates.value.splice(idx, 1)
    else deleteDates.value.push(day.date)
    deleteDates.value.sort()
  } else {
    selectedDate.value = day.date
  }
}
const openBatchDialog = () => {
  if (!batchDates.value.length) return
  const lastPid = localStorage.getItem('taskm_last_project')
  batchForm.value = { project_ids: lastPid ? [Number(lastPid)] : [], task_ids: [], multi_project: false, content: '' }
  batchTasks.value = []
  if (lastPid) loadBatchTasks([Number(lastPid)])
  showBatchDlg.value = true
}
const onBatchMultiChange = () => { batchForm.value.project_ids = []; batchForm.value.task_ids = []; batchTasks.value = [] }
const onBatchProjectChange = () => {
  const ids = batchForm.value.project_ids
  batchForm.value.task_ids = []
  if (ids.length) { localStorage.setItem('taskm_last_project', ids[0]); loadBatchTasks(ids) }
  else batchTasks.value = []
}
const loadBatchTasks = async (pids) => {
  const results = await Promise.all(pids.map(async (pid) => {
    try {
      const proj = projects.value.find((p) => p.id === pid)
      if (!proj) return []
      const ts = await getTasks(proj.display_id || pid)
      return ts.map((t) => ({ ...t, _projectLabel: proj.name }))
    } catch { return [] }
  }))
  batchTasks.value = results.flat()
}
const resetBatchForm = () => { batchForm.value = { project_ids: [], task_ids: [], multi_project: false, content: '' }; batchTasks.value = [] }
const submitBatch = async () => {
  if (!batchForm.value.project_ids.length) { ElMessage.warning('请选择项目'); return }
  batchLoading.value = true
  try {
    let count = 0
    for (const d of batchDates.value) {
      await createCheckin({ ...batchForm.value, date: d })
      count++
    }
    ElMessage.success(`批量签到完成（${count} 天）`)
    showBatchDlg.value = false
    allCheckins.value = await getAllCheckins({ year: calYear.value, month: calMonth.value })
    loadStatusForDate(selectedDate.value)
    toggleBatchMode()
  } finally { batchLoading.value = false }
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.page-title { font-size: 20px; font-weight: 600; }
.page-sub { font-size: 13px; color: #888; margin-top: 4px; }

.calendar-layout { display: flex; gap: 24px; align-items: flex-start; }

.cal-left { width: 420px; flex-shrink: 0; display: flex; flex-direction: column; gap: 16px; }
.cal-panel { background: #fff; border-radius: 10px; border: 1px solid #e8e8e4; padding: 18px; position: relative; }
.cal-panel.batch-mode { border-color: #e6a23c; }
.cal-panel.delete-batch-mode { border-color: #f56c6c; }
.cal-nav { display: flex; align-items: center; justify-content: center; margin-bottom: 16px; }
.cal-month-title { font-size: 16px; font-weight: 600; min-width: 120px; text-align: center; }
.cal-weekdays { display: grid; grid-template-columns: repeat(7, 1fr); text-align: center; margin-bottom: 8px; }
.cal-weekday { font-size: 12px; color: #888; padding: 4px 0; }
.cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }
.cal-grid-loading .cal-cell { background: #f6f6f6; border-radius: 8px; }
.cal-cell { position: relative; aspect-ratio: 1; display: flex; align-items: center; justify-content: center; border-radius: 8px; cursor: pointer; font-size: 13px; transition: background .1s; gap: 2px; }
.cal-cell:hover { background: #f5f4fe; }
.cal-cell-empty { visibility: hidden; pointer-events: none; }
.cal-cell.batch-disabled { opacity: 0.3; cursor: default; }
.cal-cell.delete-disabled { opacity: 0.3; cursor: default; }
.cal-cell.today .cal-cell-num { color: #534ab7; font-weight: 700; }
.cal-cell.active { background: #eeedfe; }
.cal-cell.active .cal-cell-num { font-weight: 600; }
.cal-cell.batch-selected { background: #fdf6ec; border: 1px solid #e6a23c; }
.cal-cell.delete-selected { background: #fef0f0; border: 1px solid #f56c6c; }
.cal-cell.delete-selected .cal-cell-num { font-weight: 600; color: #f56c6c; }
.cal-cell-dot { width: 5px; height: 5px; border-radius: 50%; background: #534ab7; position: absolute; bottom: 6px; }
.cal-cell-label { position: absolute; bottom: 3px; font-size: 9px; font-weight: 600; line-height: 1; }
.cal-cell-overtime { color: #d48806; }
.cal-cell-leave { color: #e67e22; }
.cal-cell-badge { position: absolute; top: 1px; right: 2px; font-size: 9px; font-weight: 600; line-height: 1.2; border-radius: 3px; padding: 0 3px; max-width: 52px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cal-cell-badge.cb-holiday { color: #e74c3c; background: #fde8e8; }
.cal-cell-badge.cb-workday { color: #d48806; background: #fff7e6; }
.cal-cell-badge.cb-festival { color: #8b5cf6; background: #f3eefe; }
.cal-cell-badge.cb-off { color: #999; background: #f0f0f0; }
.cal-cell-checked { font-size: 10px; color: #999; position: absolute; bottom: 4px; }
.cal-cell-has-data { font-size: 10px; color: #f56c6c; position: absolute; bottom: 4px; }
.cal-cell-num { line-height: 1; }

.cal-stats-card { background: #fff; border-radius: 10px; border: 1px solid #e8e8e4; padding: 16px 18px; }
.cal-stats-title { font-size: 12px; color: #888; margin-bottom: 6px; }
.cal-stats-row { display: flex; align-items: center; gap: 12px; }
.cal-stats-item { font-size: 13px; color: #333; }
.cal-stats-item strong { font-size: 18px; color: #534ab7; }
.cal-stats-divider { width: 1px; height: 20px; background: #e0e0e0; }
.cal-stats-overtime { font-size: 12px; color: #d48806; margin-top: 4px; }
.cal-stats-overtime strong { font-size: 14px; }

.batch-bar { display: flex; align-items: center; justify-content: space-between; padding: 10px 4px 0; margin-top: 10px; border-top: 1px solid #eee; font-size: 13px; color: #e6a23c; }

.delete-batch-bar { display: flex; align-items: center; justify-content: space-between; padding: 10px 4px 0; margin-top: 10px; border-top: 1px solid #f56c6c; font-size: 13px; color: #f56c6c; }

.cal-detail { flex: 1; min-width: 0; }
.cal-detail-header { margin-bottom: 16px; }
.cal-detail-header h3 { font-size: 16px; font-weight: 600; margin: 0; }
.cal-checkins { display: flex; flex-direction: column; gap: 10px; }
.cal-checkin-card { background: #fff; border-radius: 8px; border: 1px solid #e8e8e4; padding: 14px 18px; }
.cal-cc-top { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }
.cal-cc-project { font-size: 11px; padding: 2px 8px; border-radius: 4px; background: #eeedfe; color: #534ab7; font-weight: 500; }
.cal-cc-time { font-size: 12px; color: #aaa; margin-left: auto; }
.cal-cc-tasks { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.cal-cc-task { font-size: 11px; padding: 2px 8px; border-radius: 4px; background: #e1f5ee; color: #0f6e56; font-weight: 500; }
.cal-cc-content { font-size: 14px; line-height: 1.5; color: #333; white-space: pre-wrap; }

.delete-date-item { display: flex; justify-content: space-between; align-items: center; padding: 6px 10px; background: #fef0f0; border-radius: 6px; font-size: 13px; margin-bottom: 4px; }

.status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 8px; flex-shrink: 0; vertical-align: middle; }
.dot-green { background: #52c41a; }
.dot-gray { background: #d9d9d9; }

/* 工具卡片 */
.cal-tools-card { background: #fff; border-radius: 10px; border: 1px solid #e8e8e4; padding: 14px 18px; }
.cal-tools-title { font-size: 12px; color: #888; margin-bottom: 10px; }
.cal-tools-btn { padding: 6px 12px; font-size: 13px; border-radius: 6px; background: #f5f4fe; color: #534ab7; }
.cal-tools-btn:hover { background: #eeedfe; }

/* 出勤计算器 */
.calc-range { display: flex; align-items: center; margin-bottom: 20px; }
.calc-summary { display: flex; justify-content: space-around; padding: 16px 0; background: #f9f9fb; border-radius: 10px; margin-bottom: 20px; }
.calc-summary-item { text-align: center; }
.calc-summary-num { display: block; font-size: 28px; font-weight: 700; line-height: 1.2; }
.calc-summary-label { font-size: 13px; color: #888; margin-top: 2px; display: block; }
.calc-section { margin-top: 16px; }
.calc-section-title { font-size: 14px; font-weight: 600; margin-bottom: 10px; color: #333; }
.calc-month-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.calc-month-card { background: #f9f9fb; border-radius: 8px; padding: 12px; }
.calc-month-name { font-size: 13px; font-weight: 600; color: #534ab7; margin-bottom: 8px; }
.calc-month-row { font-size: 12px; color: #666; line-height: 1.8; }
.calc-proj-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.calc-proj-card { display: flex; align-items: center; gap: 8px; background: #f0f0f5; border-radius: 8px; padding: 8px 14px; }
.calc-proj-name { font-size: 13px; color: #333; }
.calc-proj-days { font-size: 13px; color: #534ab7; }
.calc-proj-days strong { font-size: 16px; }
.calc-estimated-note { text-align: center; font-size: 12px; color: #999; margin-top: -12px; margin-bottom: 8px; }
.calc-estimated-note strong { color: #534ab7; }
.calc-estimated-tag { display: inline-block; font-size: 10px; font-weight: 400; color: #fff; background: #534ab7; border-radius: 3px; padding: 0 5px; margin-left: 4px; vertical-align: middle; }
.calc-section-title-warn { display: flex; align-items: center; color: #e67e22; }
.calc-warn-grid { display: flex; flex-wrap: wrap; gap: 6px; }
.calc-warn-item { background: #fff7e6; border: 1px solid #ffe0a3; border-radius: 6px; padding: 8px 10px; font-size: 12px; min-width: 140px; }
.calc-warn-top { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.calc-warn-date { font-weight: 600; color: #d48806; }
.calc-warn-weekday { color: #999; font-size: 11px; }
.calc-warn-projs { display: flex; flex-wrap: wrap; gap: 4px; }
.calc-warn-proj { font-size: 11px; padding: 1px 6px; border-radius: 3px; background: #eeedfe; color: #534ab7; }

/* 日历设置 */
.hs-tabs { display: flex; gap: 0; margin-bottom: 16px; border-bottom: 1px solid #e8e8e4; }
.hs-tab { padding: 6px 20px; font-size: 13px; cursor: pointer; color: #888; border-bottom: 2px solid transparent; margin-bottom: -1px; transition: all .15s; }
.hs-tab:hover { color: #534ab7; }
.hs-tab.active { color: #534ab7; border-bottom-color: #534ab7; font-weight: 600; }
.hs-entry { display: flex; align-items: center; gap: 10px; padding: 10px 0; }
.hs-entry-label { font-size: 13px; color: #888; white-space: nowrap; }
.hs-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.hs-nav { display: flex; align-items: center; }
.hs-month { font-size: 15px; font-weight: 600; min-width: 120px; text-align: center; }
.hs-legend { display: flex; align-items: center; gap: 6px; }
.hs-tag { display: inline-block; font-size: 11px; padding: 1px 6px; border-radius: 3px; }
.hs-tag-normal { background: #e8f5e9; color: #2e7d32; }
.hs-tag-holiday { background: #fde8e8; color: #e74c3c; }
.hs-tag-workday { background: #fff7e6; color: #d48806; }
.hs-tag-off { background: #f0f0f0; color: #999; }
.hs-override-hint { font-size: 11px; color: #bbb; margin-left: 2px; }
.hs-weekdays { display: grid; grid-template-columns: repeat(7, 1fr); text-align: center; margin-bottom: 6px; }
.hs-weekday { font-size: 11px; color: #888; padding: 2px 0; }
.hs-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; }
.hs-cell { position: relative; aspect-ratio: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; border-radius: 6px; cursor: pointer; font-size: 13px; background: #fafafa; transition: background .1s; gap: 1px; }
.hs-cell:hover { background: #f0f0f5; }
.hs-cell-empty { visibility: hidden; }
.hs-num { line-height: 1; font-weight: 500; }
.hs-tag-sm { font-size: 9px; line-height: 1.2; border-radius: 2px; padding: 0 3px; }
.hs-ts-normal { color: #2e7d32; background: #e8f5e9; }
.hs-ts-holiday { color: #e74c3c; background: #fde8e8; }
.hs-ts-workday { color: #d48806; background: #fff7e6; }
.hs-ts-off { color: #999; background: #f0f0f0; }
.hs-override-dot { width: 4px; height: 4px; border-radius: 50%; background: #534ab7; position: absolute; top: 2px; right: 2px; }
.hs-auto-save { font-size: 12px; color: #bbb; }

</style>
