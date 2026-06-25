<template>
  <div class="dashboard-page">
    <!-- 面包屑 -->
    <el-breadcrumb separator="/" style="flex-shrink: 0;">
      <el-breadcrumb-item :to="{ name: 'projects' }">项目列表</el-breadcrumb-item>
      <el-breadcrumb-item>{{ projectName }}</el-breadcrumb-item>
      <el-breadcrumb-item>总览大屏</el-breadcrumb-item>
    </el-breadcrumb>

    <!-- 页面头部 -->
    <div class="page-header">
      <h2>总览看板</h2>
      <div class="header-actions">
        <span class="update-time">上次更新: {{ lastUpdateTime }}</span>
        <el-button type="primary" :icon="Refresh" :loading="refreshing" @click="refreshData" circle />
        <el-select v-model="autoRefresh" size="small" style="width: 120px" @change="toggleAutoRefresh">
          <el-option label="自动刷新" :value="0" />
          <el-option label="30秒" :value="30000" />
          <el-option label="60秒" :value="60000" />
          <el-option label="5分钟" :value="300000" />
        </el-select>
      </div>
    </div>

    <!-- ===== 任务看板 + 需求状态分布（并排） ===== -->
    <div class="kanban-row">
      <div class="kanban-section">
        <div class="kanban-card">
          <div class="kanban-card-header">任务看板</div>
          <div class="kanban-board">
          <div
          v-for="col in columnDefs"
          :key="col.key"
          class="kanban-column"
          :class="'col-' + col.key"
        >
          <!-- 栏头 -->
          <div class="column-header">
            <span class="column-title">{{ col.label }}</span>
            <span class="column-badge">{{ getColumnTasks(col).length }}</span>
            <el-popover
              placement="bottom"
              trigger="click"
              :width="220"
              popper-class="kanban-popover"
            >
              <template #reference>
                <el-button :icon="Setting" size="small" text class="col-setting-btn" @click.stop />
              </template>
              <div class="popover-body">
                <div class="popover-title">选择显示的状态</div>
                <el-checkbox-group
                  v-model="col.selectedIds"
                  @change="saveColumnConfig"
                >
                  <el-checkbox
                    v-for="s in allStatuses"
                    :key="s.status_id"
                    :label="s.status_id"
                    :value="s.status_id"
                  >
                    <span class="status-dot" :style="{ background: s.color }"></span>
                    {{ s.status_name }}
                  </el-checkbox>
                </el-checkbox-group>
              </div>
            </el-popover>
          </div>
          <!-- 卡片列表 -->
          <div class="column-body" v-if="getColumnTasks(col).length">
            <div
              v-for="task in getColumnTasks(col)"
              :key="task.id"
              class="task-card"
              @click="goToTask(task.display_id)"
            >
              <div class="task-title" :title="task.title">{{ task.title }}</div>
              <div class="task-meta">
                <span v-if="task.contact_names" class="meta-item">
                  <el-icon :size="12"><User /></el-icon>
                  {{ task.contact_names }}
                </span>
                <span v-if="task.due_date" class="meta-item meta-due" :class="{ overdue: isOverdue(task.due_date) }">
                  <el-icon :size="12"><Calendar /></el-icon>
                  {{ task.due_date }}
                </span>
              </div>
              <div v-if="task.status_duration_text && col.key !== 'done'" class="task-duration">
                <el-icon :size="11"><Timer /></el-icon>
                已{{ col.key === 'todo' ? '等待' : '停留' }} {{ task.status_duration_text }}
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无" :image-size="36" />
        </div>
      </div><!-- /kanban-board -->
      </div><!-- /kanban-card -->
    </div><!-- /kanban-section -->

      <!-- 右侧：需求状态分布 + 需求优先级分布 -->
      <div class="sidebar-charts">
        <div class="sidebar-chart-item">
          <div class="sidebar-chart-title">需求状态分布</div>
          <v-chart v-if="statusChartData.length" :option="statusPieOption" autoresize class="sidebar-chart-box" @click="handleStatusClick" />
          <el-empty v-else description="暂无数据" :image-size="36" />
        </div>
        <div class="sidebar-chart-item">
          <div class="sidebar-chart-title">需求优先级分布</div>
          <v-chart v-if="priorityChartData.length" :option="priorityBarOption" autoresize class="sidebar-chart-box" @click="handlePriorityClick" />
          <el-empty v-else description="暂无数据" :image-size="36" />
        </div>
      </div>
    </div><!-- /kanban-row -->
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh, Setting, User, Calendar, Timer } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import VChart from 'vue-echarts'
import * as echarts from 'echarts'
import { getDashboardStats, getProject, getKanbanTasks, getKanbanConfig, putKanbanConfig } from '../api/index.js'

const route = useRoute()
const router = useRouter()
const projectId = route.params.projectId

const projectName = ref('')
const kanbanData = ref({ columns: [] })
const dashboardData = ref({})
const refreshing = ref(false)
const lastUpdateTime = ref(dayjs().format('HH:mm:ss'))
const autoRefresh = ref(0)
let refreshTimer = null

// ---- 看板栏位定义 ----
const defaultColumnDefs = [
  { key: 'todo',   label: '待开始' },
  { key: 'doing',  label: '进行中' },
  { key: 'blocked', label: '有卡点' },
  { key: 'done',   label: '已完成' },
]

// 每个栏选中的状态 ID 列表
const columnDefs = ref([])

// 从后端获取所有状态
const allStatuses = computed(() => {
  return (kanbanData.value.columns || []).map(c => ({
    status_id: c.status_id,
    status_name: c.status_name,
    color: c.color,
  }))
})

async function loadColumnConfig() {
  try {
    return await getKanbanConfig(projectId)
  } catch { return null }
}

let configSaveTimer = null
function saveColumnConfig() {
  clearTimeout(configSaveTimer)
  configSaveTimer = setTimeout(async () => {
    const config = {}
    for (const col of columnDefs.value) {
      config[col.key] = col.selectedIds
    }
    try {
      await putKanbanConfig(projectId, config)
    } catch {}
  }, 300)
}

function initColumnDefs() {
  const cols = kanbanData.value.columns || []
  if (!cols.length) return
  columnDefs.value = defaultColumnDefs.map(d => ({
    ...d,
    selectedIds: [],
  }))
  // 异步加载已保存的配置
  loadColumnConfig().then(saved => {
    if (saved) {
      columnDefs.value = defaultColumnDefs.map(d => ({
        ...d,
        selectedIds: saved[d.key] || [],
      }))
    }
  })
}

// 根据栏配置获取该栏的任务
function getColumnTasks(col) {
  const colMap = {}
  for (const c of kanbanData.value.columns || []) {
    colMap[c.status_id] = c.tasks || []
  }
  const result = []
  for (const sid of col.selectedIds) {
    const tasks = colMap[sid]
    if (tasks) result.push(...tasks)
  }
  return result
}

function isOverdue(dateStr) {
  if (!dateStr) return false
  return dayjs(dateStr).isBefore(dayjs(), 'day')
}

function goToTask(taskDisplayId) {
  router.push(`/projects/${projectId}/tasks/${taskDisplayId}`)
}

function handleStatusClick(params) {
  router.push({ name: 'requirements', params: { projectId }, query: { status: params.name } })
}

function handlePriorityClick(params) {
  router.push({ name: 'requirements', params: { projectId }, query: { priority: params.name } })
}

// ---- 右侧图表 ----
const statusChartData = computed(() => dashboardData.value.status_distribution || [])
const priorityChartData = computed(() => dashboardData.value.priority_distribution || [])

const statusPieOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  color: ['#e6a23c', '#409eff', '#67c23a', '#909399'],
  series: [{
    type: 'pie', radius: ['35%', '60%'], center: ['50%', '50%'],
    avoidLabelOverlap: true,
    itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
    label: { show: true, formatter: '{b}\n{c}', fontSize: 11 },
    emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
    data: statusChartData.value.map(d => ({ name: d.name, value: d.value })),
  }]
}))

const priorityBarOption = computed(() => {
  const order = ['低', '普通', '高', '紧急']
  const sorted = [...priorityChartData.value].sort(
    (a, b) => order.indexOf(a.name) - order.indexOf(b.name)
  )
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: sorted.map(d => d.name), axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{ type: 'bar', data: sorted.map(d => d.value), itemStyle: { borderRadius: [4, 4, 0, 0], color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#534ab7' }, { offset: 1, color: '#7c73e6' }]) }, barWidth: '50%' }],
  }
})

// ---- 数据加载 ----
async function loadData() {
  try {
    const [kanban, stats] = await Promise.all([
      getKanbanTasks(projectId),
      getDashboardStats(projectId),
    ])
    kanbanData.value = kanban || { columns: [] }
    dashboardData.value = stats || {}
    lastUpdateTime.value = dayjs().format('HH:mm:ss')

    // 首次加载时初始化栏配置
    if (!columnDefs.value.length && kanban?.columns?.length) {
      initColumnDefs()
    }
  } catch {}
}

async function refreshData() {
  refreshing.value = true
  await loadData()
  refreshing.value = false
}

async function loadProject() {
  try {
    const proj = await getProject(projectId)
    projectName.value = proj.name
  } catch {
    projectName.value = '项目'
  }
}

function toggleAutoRefresh(val) {
  clearInterval(refreshTimer)
  refreshTimer = null
  if (val > 0) {
    refreshTimer = setInterval(loadData, val)
  }
}

onMounted(async () => {
  await loadProject()
  await loadData()
})

onBeforeUnmount(() => {
  clearInterval(refreshTimer)
})
</script>

<style scoped>
.dashboard-page { width: 100%; flex: 1; min-height: 0; display: flex; flex-direction: column; gap: 16px; overflow: hidden; }

/* ---- 头部 ---- */
.page-header { display: flex; justify-content: space-between; align-items: flex-start; flex-shrink: 0; }
.page-header h2 { font-size: 20px; font-weight: 600; margin: 0; }
.header-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.update-time { font-size: 12px; color: #999; }

/* ---- 看板行（看板 66% + 右侧图表） ---- */
.kanban-row { display: flex; gap: 16px; flex: 1; min-height: 0; align-items: stretch; }
.kanban-section { width: 66.666%; flex-shrink: 0; display: flex; flex-direction: column; min-height: 0; }
.kanban-card {
  background: #fff;
  border: 1px solid #e8e8e4;
  border-radius: 10px;
  padding: 0 16px 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.kanban-card-header {
  font-size: 15px;
  font-weight: 600;
  color: #444;
  padding: 14px 0 10px;
  flex-shrink: 0;
}
.kanban-board {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.kanban-column {
  background: #fff;
  border: 1px solid #e8e8e4;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

/* ---- 右侧图表 ---- */
.sidebar-charts {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}
.sidebar-chart-item {
  flex: 1;
  min-height: 0;
  background: #fff;
  border: 1px solid #e8e8e4;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
}
.sidebar-chart-title {
  font-size: 14px;
  font-weight: 600;
  color: #555;
  margin-bottom: 12px;
  flex-shrink: 0;
}
.sidebar-chart-box {
  width: 100%;
  flex: 1;
  min-height: 0;
}

.column-header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 10px 6px;
  border-bottom: 1px solid #f0f0ee;
  flex-shrink: 0;
}
.column-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}
.column-badge {
  font-size: 11px;
  background: #f0f0ee;
  color: #888;
  padding: 0 7px;
  border-radius: 8px;
  line-height: 18px;
  min-width: 18px;
  text-align: center;
}
.col-setting-btn {
  margin-left: auto;
  font-size: 14px;
  color: #bbb;
  transition: color 0.15s;
}
.col-setting-btn:hover { color: #409eff; }

.column-body {
  flex: 1;
  overflow-y: auto;
  padding: 6px 8px 8px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.column-body::-webkit-scrollbar {
  width: 4px;
}
.column-body::-webkit-scrollbar-track {
  background: transparent;
}
.column-body::-webkit-scrollbar-thumb {
  background: #ddd;
  border-radius: 2px;
}
.column-body::-webkit-scrollbar-thumb:hover {
  background: #bbb;
}

/* ---- 任务卡片 ---- */
.task-card {
  background: #fafafa;
  border: 1px solid #eee;
  border-radius: 6px;
  padding: 6px 10px;
  cursor: pointer;
  transition: box-shadow 0.15s, border-color 0.15s;
}
.task-card:hover {
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
  border-color: #d0d0cc;
}
.task-title {
  font-size: 12px;
  font-weight: 500;
  color: #333;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 3px;
}
.task-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  font-size: 10px;
  color: #888;
}
.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.meta-due.overdue {
  color: #e53e3e;
  font-weight: 500;
}
.task-duration {
  font-size: 10px;
  color: #999;
  margin-top: 2px;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

/* ---- 各栏颜色风格 ---- */
.col-todo    .column-title { color: #e6a23c; }
.col-doing   .column-title { color: #409eff; }
.col-blocked .column-title { color: #e53e3e; }
.col-done    .column-title { color: #67c23a; }

/* ---- popover ---- */
.popover-body { padding: 4px 0; }
.popover-title { font-size: 13px; font-weight: 500; color: #555; margin-bottom: 10px; }
.popover-body .el-checkbox { display: flex; margin-bottom: 6px; height: auto; }
.popover-body .el-checkbox__label { font-size: 12px; display: inline-flex; align-items: center; gap: 4px; }
.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  vertical-align: middle;
}
</style>
