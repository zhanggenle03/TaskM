<template>
  <div class="dashboard-page">
    <!-- 面包屑 -->
    <el-breadcrumb separator="/" style="margin-bottom: 20px;">
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

    <!-- 第一行：需求状态分布 + 优先级分布 + 项目进度 -->
    <div class="chart-row">
      <div class="chart-card" @click="goToRequirements('status', 'todo,in_progress')">
        <div class="chart-title">需求状态分布</div>
        <v-chart v-if="statusChartData.length" :option="statusPieOption" autoresize class="chart-box" />
        <el-empty v-else description="暂无数据" :image-size="60" />
      </div>
      <div class="chart-card" @click="goToRequirements('all')">
        <div class="chart-title">优先级分布</div>
        <v-chart v-if="priorityChartData.length" :option="priorityBarOption" autoresize class="chart-box" />
        <el-empty v-else description="暂无数据" :image-size="60" />
      </div>
      <div class="chart-card" @click="goToTasks()">
        <div class="chart-title">项目进度</div>
        <v-chart v-if="progressChartData.length" :option="progressOption" autoresize class="chart-box" />
        <el-empty v-else description="暂无任务数据" :image-size="60" />
      </div>
    </div>

    <!-- 第二行：近期截止 + 需求趋势 -->
    <div class="chart-row">
      <div class="chart-card chart-card-half" @click="goToRequirements('all')">
        <div class="chart-title">近期截止需求</div>
        <div v-if="dashboardData.upcoming_deadlines?.length" class="deadline-list">
          <div
            v-for="item in dashboardData.upcoming_deadlines"
            :key="item.id"
            class="deadline-item"
            @click.stop="goToRequirements('status', item.status)"
          >
            <div class="deadline-left">
              <span class="deadline-title">{{ item.title }}</span>
              <span class="deadline-priority" :class="'pri-' + item.priority">
                {{ priorityLabel(item.priority) }}
              </span>
            </div>
            <div class="deadline-right">
              <el-tag :type="deadlineTag(item.due_date)" size="small">
                {{ item.due_date }}
              </el-tag>
            </div>
          </div>
        </div>
        <el-empty v-else description="近期无截止需求" :image-size="50" />
      </div>
      <div class="chart-card chart-card-half">
        <div class="chart-title">需求趋势（近10周）</div>
        <v-chart v-if="trendData.length" :option="trendLineOption" autoresize class="chart-box" />
        <el-empty v-else description="暂无数据" :image-size="60" />
      </div>
    </div>

    <!-- 统计数字 -->
    <div class="stat-cards">
      <div class="stat-item" @click="goToRequirements('status', 'todo')">
        <div class="stat-value" style="color: #e6a23c">{{ todoCount }}</div>
        <div class="stat-label">待处理需求</div>
      </div>
      <div class="stat-item" @click="goToRequirements('status', 'in_progress')">
        <div class="stat-value" style="color: #409eff">{{ progressCount }}</div>
        <div class="stat-label">进行中需求</div>
      </div>
      <div class="stat-item" @click="goToRequirements('status', 'done')">
        <div class="stat-value" style="color: #67c23a">{{ doneCount }}</div>
        <div class="stat-label">已完成需求</div>
      </div>
      <div class="stat-item" @click="goToRequirements('status', 'todo,in_progress')">
        <div class="stat-value" style="color: #f56c6c">{{ overdueCount }}</div>
        <div class="stat-label">已逾期需求</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import VChart from 'vue-echarts'
import 'echarts'
import { getDashboardStats, getProject } from '../api/index.js'

const route = useRoute()
const router = useRouter()
const projectId = route.params.projectId

const projectName = ref('')
const dashboardData = ref({})
const refreshing = ref(false)
const lastUpdateTime = ref(dayjs().format('HH:mm:ss'))
const autoRefresh = ref(0)
let refreshTimer = null

// 统计计数
const todoCount = computed(() => {
  const item = dashboardData.value.status_distribution?.find(d => d.name === '待处理')
  return item?.value || 0
})
const progressCount = computed(() => {
  const item = dashboardData.value.status_distribution?.find(d => d.name === '进行中')
  return item?.value || 0
})
const doneCount = computed(() => {
  const item = dashboardData.value.status_distribution?.find(d => d.name === '已完成')
  return item?.value || 0
})
const overdueCount = computed(() => {
  return dashboardData.value.upcoming_deadlines?.filter(d => dayjs(d.due_date).isBefore(dayjs(), 'day')).length || 0
})

// 图表数据
const statusChartData = computed(() => dashboardData.value.status_distribution || [])
const priorityChartData = computed(() => dashboardData.value.priority_distribution || [])
const progressChartData = computed(() => dashboardData.value.project_progress || [])
const trendData = computed(() => dashboardData.value.trend || [])

// 状态饼图
const statusPieOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  color: ['#e6a23c', '#409eff', '#67c23a', '#909399'],
  series: [{
    type: 'pie',
    radius: ['35%', '60%'],
    center: ['50%', '50%'],
    avoidLabelOverlap: true,
    itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
    label: { show: true, formatter: '{b}\n{c}', fontSize: 11 },
    emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
    data: statusChartData.value.map(d => ({ name: d.name, value: d.value })),
  }]
}))

// 优先级柱状图
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
    series: [{
      type: 'bar',
      data: sorted.map(d => d.value),
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#534ab7' },
          { offset: 1, color: '#7c73e6' },
        ]),
      },
      barWidth: '50%',
    }],
  }
})

// 项目进度环形图
const progressOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c}' },
  series: [{
    type: 'pie',
    radius: ['40%', '65%'],
    center: ['50%', '50%'],
    avoidLabelOverlap: true,
    label: { show: true, formatter: '{b}\n{c}', fontSize: 11 },
    emphasis: { label: { show: true, fontSize: 14 } },
    data: progressChartData.value.map(d => ({
      name: d.name, value: d.value,
      itemStyle: { color: d.color },
    })),
  }]
}))

// 趋势折线图
const trendLineOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 40, right: 20, top: 20, bottom: 30 },
  xAxis: { type: 'category', data: trendData.value.map(d => d.date), axisLabel: { fontSize: 10 } },
  yAxis: { type: 'value', minInterval: 1 },
  series: [{
    type: 'line',
    data: trendData.value.map(d => d.count),
    smooth: true,
    lineStyle: { color: '#534ab7', width: 2 },
    itemStyle: { color: '#534ab7' },
    areaStyle: {
      color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: 'rgba(83,74,183,0.3)' },
        { offset: 1, color: 'rgba(83,74,183,0.02)' },
      ]),
    },
    symbol: 'circle',
    symbolSize: 6,
  }]
}))

// 辅助函数
const priorityLabel = (p) => ({ low: '低', normal: '普通', high: '高', urgent: '紧急' }[p] || p)
const deadlineTag = (d) => {
  if (!d) return 'info'
  return dayjs(d).isBefore(dayjs(), 'day') ? 'danger' : (dayjs(d).diff(dayjs(), 'day') <= 3 ? 'warning' : '')
}

// 导航
function goToRequirements(filter, value) {
  const query = {}
  if (filter === 'status' && value) query.status = value
  router.push({ name: 'requirements', params: { projectId }, query })
}

function goToTasks() {
  router.push(`/projects/${projectId}`)
}

// 数据加载
async function loadData() {
  try {
    dashboardData.value = await getDashboardStats(projectId)
    lastUpdateTime.value = dayjs().format('HH:mm:ss')
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
.dashboard-page { max-width: 1400px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h2 { font-size: 20px; font-weight: 600; }
.header-actions { display: flex; align-items: center; gap: 8px; }
.update-time { font-size: 12px; color: #999; }
.chart-row { display: flex; gap: 16px; margin-bottom: 16px; }
.chart-card {
  flex: 1; background: #fff; border: 1px solid #e8e8e4;
  border-radius: 10px; padding: 16px; cursor: pointer;
  transition: box-shadow 0.2s; min-height: 280px;
}
.chart-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.06); }
.chart-card-half { flex: 1; }
.chart-title { font-size: 14px; font-weight: 600; color: #555; margin-bottom: 12px; }
.chart-box { width: 100%; height: 220px; }
.deadline-list { display: flex; flex-direction: column; gap: 8px; }
.deadline-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 10px; border-radius: 6px; background: #fafafa;
  transition: background 0.15s;
}
.deadline-item:hover { background: #f0f0ee; }
.deadline-left { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
.deadline-title { font-size: 13px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.deadline-priority { font-size: 11px; padding: 1px 6px; border-radius: 3px; background: #f0f0ee; color: #888; white-space: nowrap; }
.deadline-priority.pri-urgent { background: #fef0f0; color: #e53e3e; }
.deadline-priority.pri-high { background: #fdf6ec; color: #e6a23c; }
.deadline-priority.pri-normal { background: #f0f5ff; color: #409eff; }
.deadline-right { flex-shrink: 0; }
.stat-cards { display: flex; gap: 16px; margin-top: 8px; }
.stat-item {
  flex: 1; background: #fff; border: 1px solid #e8e8e4;
  border-radius: 10px; padding: 20px; text-align: center;
  cursor: pointer; transition: box-shadow 0.2s;
}
.stat-item:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.06); }
.stat-value { font-size: 32px; font-weight: 700; margin-bottom: 4px; }
.stat-label { font-size: 13px; color: #888; }
</style>
