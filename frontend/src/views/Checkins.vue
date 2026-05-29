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
      <!-- 日历 -->
      <div class="cal-panel" :class="{ 'batch-mode': batchMode, 'delete-batch-mode': deleteBatchMode }">
        <div class="cal-nav">
          <el-button size="small" text @click="prevMonth"><el-icon><ArrowLeft /></el-icon></el-button>
          <span class="cal-month-title">{{ calYear }}年{{ calMonth }}月</span>
          <el-button size="small" text @click="nextMonth"><el-icon><ArrowRight /></el-icon></el-button>
          <el-button size="small" text style="margin-left:8px" @click="goToday">今天</el-button>
        </div>
        <div class="cal-weekdays">
          <div v-for="w in weekDays" :key="w" class="cal-weekday">{{ w }}</div>
        </div>
        <div class="cal-grid">
          <div
            v-for="(day, i) in calendarDays"
            :key="i"
            class="cal-cell"
            :class="{
              'other-month': !day.isCurrent,
              today: day.isToday,
              active: !batchMode && !deleteBatchMode && day.date === selectedDate,
              'has-checkin': checkinsByDate[day.date],
              'batch-selected': batchMode && batchDates.includes(day.date),
              'batch-disabled': !day.isCurrent || (batchMode && checkinsByDate[day.date]),
              'delete-selected': deleteBatchMode && deleteDates.includes(day.date),
              'delete-disabled': !day.isCurrent || (deleteBatchMode && !checkinsByDate[day.date]),
            }"
            @click="onCellClick(day)"
          >
            <span class="cal-cell-num">{{ day.num }}</span>
            <span v-if="checkinsByDate[day.date] && !batchMode && !deleteBatchMode" class="cal-cell-dot"></span>
            <span v-if="batchMode && checkinsByDate[day.date]" class="cal-cell-checked">已签</span>
            <span v-if="deleteBatchMode && checkinsByDate[day.date]" class="cal-cell-has-data">已签</span>
          </div>
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
            <el-option v-for="p in projects" :key="p.id" :value="p.id" :label="p.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="相关任务">
          <el-select v-model="checkinForm.task_ids" multiple placeholder="可选，可多选" style="width:100%">
            <el-option v-for="t in tasksForSelected" :key="t.id" :value="t.id" :label="t.title" />
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
            <el-option v-for="p in projects" :key="p.id" :value="p.id" :label="p.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="相关任务">
          <el-select v-model="batchForm.task_ids" multiple placeholder="可选" style="width:100%">
            <el-option v-for="t in batchTasks" :key="t.id" :value="t.id" :label="t.title" />
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
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import utc from 'dayjs/plugin/utc'
dayjs.extend(utc)
dayjs.locale('zh-cn')
import {
  getProjects, getAllCheckins, createCheckin, updateCheckin, deleteCheckin, batchDeleteCheckins, getTasks,
} from '../api'

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
const weekDays = ['日', '一', '二', '三', '四', '五', '六']
const todayStr = dayjs().format('YYYY-MM-DD')

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

const calendarDays = computed(() => {
  const firstDay = dayjs(`${calYear.value}-${calMonth.value}-01`)
  const daysInMonth = firstDay.daysInMonth()
  const startWeekday = firstDay.day()
  const cells = []
  const prevMonth = firstDay.subtract(1, 'month')
  const prevDays = prevMonth.daysInMonth()
  for (let i = startWeekday - 1; i >= 0; i--) {
    const d = prevDays - i
    cells.push({ num: d, date: prevMonth.date(d).format('YYYY-MM-DD'), isCurrent: false, isToday: false })
  }
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = firstDay.date(d).format('YYYY-MM-DD')
    cells.push({ num: d, date: dateStr, isCurrent: true, isToday: dateStr === todayStr })
  }
  const nextMonth = firstDay.add(1, 'month')
  const remaining = 42 - cells.length
  for (let d = 1; d <= remaining; d++) {
    cells.push({ num: d, date: nextMonth.date(d).format('YYYY-MM-DD'), isCurrent: false, isToday: false })
  }
  return cells
})

const load = async () => {
  const [p, c] = await Promise.all([getProjects(), getAllCheckins()])
  projects.value = p
  allCheckins.value = c
  selectedDate.value = todayStr
}
onMounted(load)

const formatDateFull = (d) => dayjs(d).format('YYYY年M月D日 dddd')

const prevMonth = () => { if (calMonth.value === 1) { calYear.value--; calMonth.value = 12 } else calMonth.value-- }
const nextMonth = () => { if (calMonth.value === 12) { calYear.value++; calMonth.value = 1 } else calMonth.value++ }
const goToday = () => { calYear.value = dayjs().year(); calMonth.value = dayjs().month() + 1; selectedDate.value = todayStr }

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
  const all = []
  for (const pid of pids) {
    try {
      const proj = projects.value.find((p) => p.id === pid)
      if (!proj) continue
      const ts = await getTasks(proj.display_id || pid)
      all.push(...ts.map((t) => ({ ...t, _projectLabel: proj.name })))
    } catch {}
  }
  tasksForSelected.value = all
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
    allCheckins.value = await getAllCheckins()
  } finally { checkinLoading.value = false }
}
const removeCheckin = async (chk) => {
  await deleteCheckin(chk.projects?.[0]?.display_id || chk.projects?.[0]?.id || 0, chk.id)
  allCheckins.value = await getAllCheckins()
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
  allCheckins.value = await getAllCheckins()
}

// ---- 批量签到 ----
const toggleBatchMode = () => {
  batchMode.value = !batchMode.value
  if (!batchMode.value) batchDates.value = []
}
const onCellClick = (day) => {
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
  const all = []
  for (const pid of pids) {
    try {
      const proj = projects.value.find((p) => p.id === pid)
      if (!proj) continue
      const ts = await getTasks(proj.display_id || pid)
      all.push(...ts.map((t) => ({ ...t, _projectLabel: proj.name })))
    } catch {}
  }
  batchTasks.value = all
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
    allCheckins.value = await getAllCheckins()
    toggleBatchMode()
  } finally { batchLoading.value = false }
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.page-title { font-size: 20px; font-weight: 600; }
.page-sub { font-size: 13px; color: #888; margin-top: 4px; }

.calendar-layout { display: flex; gap: 24px; align-items: flex-start; }

.cal-panel { width: 420px; flex-shrink: 0; background: #fff; border-radius: 10px; border: 1px solid #e8e8e4; padding: 18px; position: relative; }
.cal-panel.batch-mode { border-color: #e6a23c; }
.cal-panel.delete-batch-mode { border-color: #f56c6c; }
.cal-nav { display: flex; align-items: center; justify-content: center; margin-bottom: 16px; }
.cal-month-title { font-size: 16px; font-weight: 600; min-width: 120px; text-align: center; }
.cal-weekdays { display: grid; grid-template-columns: repeat(7, 1fr); text-align: center; margin-bottom: 8px; }
.cal-weekday { font-size: 12px; color: #888; padding: 4px 0; }
.cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }
.cal-cell { position: relative; aspect-ratio: 1; display: flex; align-items: center; justify-content: center; border-radius: 8px; cursor: pointer; font-size: 13px; transition: background .1s; gap: 2px; }
.cal-cell:hover { background: #f5f4fe; }
.cal-cell.other-month { color: #ccc; cursor: default; }
.cal-cell.batch-disabled { opacity: 0.3; cursor: default; }
.cal-cell.delete-disabled { opacity: 0.3; cursor: default; }
.cal-cell.today .cal-cell-num { color: #534ab7; font-weight: 700; }
.cal-cell.active { background: #eeedfe; }
.cal-cell.active .cal-cell-num { font-weight: 600; }
.cal-cell.batch-selected { background: #fdf6ec; border: 1px solid #e6a23c; }
.cal-cell.delete-selected { background: #fef0f0; border: 1px solid #f56c6c; }
.cal-cell.delete-selected .cal-cell-num { font-weight: 600; color: #f56c6c; }
.cal-cell-dot { width: 5px; height: 5px; border-radius: 50%; background: #534ab7; position: absolute; bottom: 6px; }
.cal-cell-checked { font-size: 10px; color: #999; position: absolute; bottom: 4px; }
.cal-cell-has-data { font-size: 10px; color: #f56c6c; position: absolute; bottom: 4px; }
.cal-cell-num { line-height: 1; }

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
</style>
