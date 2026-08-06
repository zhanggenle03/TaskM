<template>
  <div>
    <!-- 面包屑 -->
    <el-breadcrumb separator="/" style="margin-bottom:20px">
      <el-breadcrumb-item :to="{ path: '/projects' }">项目列表</el-breadcrumb-item>
      <el-breadcrumb-item>{{ project?.name }}</el-breadcrumb-item>
      <el-breadcrumb-item>任务列表</el-breadcrumb-item>
    </el-breadcrumb>

    <div class="page-header">
      <div>
        <h1 class="page-title">任务管理</h1>
        <p class="page-sub">{{ project?.description }}</p>
      </div>
      <div class="header-actions">
        <div class="search-group">
          <el-select
            v-model="searchScope"
            class="scope-select"
            placeholder="全部范围"
            multiple
            collapse-tags
            collapse-tags-tooltip
            @change="onScopeChange"
          >
            <el-option label="任务信息" value="task" />
            <el-option label="沟通记录" value="comm" />
            <el-option label="对接人" value="contact" />
          </el-select>
          <el-input
            v-model="searchKeyword"
            placeholder="输入关键词…"
            clearable
            class="search-input"
            @input="onSearchInput"
            @clear="onSearchClear"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </div>
        <span v-if="isSearching" class="search-count">命中 {{ tasks.length }} 个任务</span>
        <div class="sort-group">
          <el-select v-model="sortBy" @change="onSortChange" placeholder="排序方式">
            <el-option v-for="opt in sortOptions" :key="opt.key" :label="opt.label" :value="opt.key" />
          </el-select>
          <el-tooltip :content="sortOrder === 'asc' ? '升序' : '降序'" placement="top">
            <el-button class="sort-order-btn" @click="toggleSortOrder">
              <el-icon><SortUp v-if="sortOrder === 'asc'" /><SortDown v-else /></el-icon>
            </el-button>
          </el-tooltip>
        </div>
        <el-button @click="$router.push(`/projects/${projectId}/settings`)">
          <el-icon><Setting /></el-icon> 设置
        </el-button>
        <el-button type="primary" @click="resetForm(); showCreate = true">
          <el-icon><Plus /></el-icon> 新建任务
        </el-button>
      </div>
    </div>

    <!-- 状态筛选 -->
    <div class="filter-bar">
      <span class="filter-label">状态筛选：</span>
      <el-button
        v-for="s in [{ id: null, name: '全部', color: '#888' }, ...statuses.filter(s => s.is_active || usedStatusIds.has(s.id))]"
        :key="s.id"
        size="small"
        :type="activeStatus === s.id ? 'primary' : ''"
        :style="activeStatus !== s.id ? { borderColor: s.color, color: s.color } : {}"
        @click="setFilter(s.id)"
        round
      >{{ s.name }}<span style="font-size:11px;opacity:0.7;margin-left:3px">({{ s.id === null ? allTaskCount : (statusCount[s.id] || 0) }})</span></el-button>
    </div>

    <!-- 标签筛选 -->
    <div class="filter-bar" style="margin-top:8px" v-if="tags.length">
      <span class="filter-label">标签筛选：</span>
      <el-button
        v-for="t in tags"
        :key="t.id"
        size="small"
        round
        :type="activeTagIds.includes(t.id) ? 'primary' : ''"
        :style="activeTagIds.includes(t.id) ? { background: t.color, borderColor: t.color } : { borderColor: t.color, color: t.color }"
        @click="toggleTagFilter(t.id)"
      >{{ t.name }}<span style="font-size:11px;opacity:0.7;margin-left:3px">({{ tagCount[t.id] || 0 }})</span></el-button>
    </div>

    <!-- 任务列表 -->
    <div class="task-list" v-if="tasks.length" ref="taskListRef">
      <div
        v-for="t in tasks" :key="t.id"
        class="task-row"
        @click="goTask(t.display_id)"
      >
        <div class="task-status-dot" :style="{ background: statusColor(t.status_id) }"></div>
          <div class="task-info">
          <div class="task-title">
            {{ t.title }}
            <span class="task-tags-inline" v-if="t.tags?.length">
              <span v-for="tag in t.tags" :key="tag.id" class="tag-chip" :style="{ background: tag.color + '22', color: tag.color, borderColor: tag.color }">{{ tag.name }}</span>
            </span>
          </div>
          <div class="task-meta">
            <el-tag v-if="t.priority" :type="priorityType(t.priority) || undefined" size="small">{{ priorityLabel(t.priority) }}</el-tag>
            <span v-if="t.last_comm_at" class="task-comm-info">
              <span class="task-contact-col">当前对接人：{{ t.last_comm_contact_name || '无' }}</span>
              <span class="task-comm-col">变更于 {{ formatTime(t.last_comm_at) }}</span>
            </span>
          </div>
          <!-- 综合搜索命中详情 -->
          <div v-if="t.search_hits" class="search-hits">
            <div v-if="t.search_hits.task_fields?.length" class="search-hit-fields">
              <span v-for="f in t.search_hits.task_fields" :key="f" class="hit-field-chip">{{ fieldLabel[f] || f }}</span>
            </div>
            <div v-for="c in t.search_hits.comms" :key="c.id" class="search-hit-comm">
              <span class="hit-time">{{ c.comm_at ? formatTime(c.comm_at) : '' }}</span>
              <span v-if="c.subject" class="hit-subject" v-html="highlightText(c.subject)"></span>
              <span class="hit-snippet" v-html="highlightText(c.snippet)"></span>
            </div>
          </div>
        </div>
        <div class="task-status-tag">
          <el-tag :color="statusColor(t.status_id)" effect="plain" size="small" style="border:none;background:transparent">
            {{ statusName(t.status_id) }}
          </el-tag>
        </div>
        <span v-if="t.due_date" class="task-date-col">截止 {{ t.due_date }}</span>
        <div class="task-actions" @click.stop>
          <el-button size="small" text @click="openEdit(t)"><el-icon><Edit /></el-icon></el-button>
          <el-button size="small" text type="danger" @click="removeTask(t)"><el-icon><Delete /></el-icon></el-button>
        </div>
      </div>
    </div>
    <el-empty v-else :description="isSearching ? '未找到匹配的任务' : '暂无任务'" />

    <!-- 新建/编辑任务 -->
    <el-dialog v-model="showCreate" :title="editTarget ? '编辑任务' : '新建任务'" width="480px" @close="resetForm">
      <el-form :model="form" label-width="80px">
        <el-form-item label="任务标题" required>
          <el-input v-model="form.title" placeholder="输入任务标题" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status_id" placeholder="选择状态" clearable>
            <el-option v-for="s in statuses.filter(s => s.is_active || s.id === form.status_id)" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="form.priority">
            <el-option label="低" value="low" />
            <el-option label="普通" value="normal" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="urgent" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker v-model="form.due_date" type="date" value-format="YYYY-MM-DD" placeholder="可选" />
        </el-form-item>
        <el-form-item label="标签">
          <el-select v-model="form.tag_ids" multiple placeholder="选择标签" style="width:100%">
            <el-option v-for="t in tags.filter(t => t.is_active || form.tag_ids?.includes(t.id))" :key="t.id" :value="t.id" :label="t.name">
              <span :style="{ color: t.color, marginRight: '6px' }">●</span>{{ t.name }}
            </el-option>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="submit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter, onBeforeRouteUpdate } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import {
  getTasks, createTask, updateTask, deleteTask, getStatuses, getProjects,
  getTags, getTaskSortConfig, putTaskSortConfig,
} from '../api'

const route = useRoute()
const router = useRouter()
const projectId = route.params.projectId
const project = ref(null)
const tasks = ref([])
const statuses = ref([])
const tags = ref([])
const activeStatus = ref(route.query.status_id ? Number(route.query.status_id) : null)
const activeTagIds = ref(route.query.tag_ids ? route.query.tag_ids.split(',').map(Number) : [])
const sortBy = ref(route.query.sort_by || 'updated_at')
const sortOrder = ref(route.query.sort_order || 'desc')
const sortOptions = [
  { key: 'updated_at', label: '更新时间' },
  { key: 'due_date', label: '截止时间' },
  { key: 'status', label: '状态' },
  { key: 'title', label: '名称' },
]
const showCreate = ref(false)
const loading = ref(false)
const editTarget = ref(null)
const form = ref({ title: '', description: '', status_id: null, priority: 'normal', due_date: null, tag_ids: [] })
const taskListRef = ref(null)

// ---- 综合搜索 ----
// searchScope 为数组：空数组=全部范围；全选 3 项=全部范围；部分选中按逗号传后端
const searchKeyword = ref(route.query.search || '')
const searchScope = ref(route.query.scope ? String(route.query.scope).split(',').filter(Boolean) : [])
const isSearching = computed(() => !!searchKeyword.value.trim())
const fieldLabel = { title: '标题', description: '描述', display_id: '编号', tag: '标签', contact: '对接人' }
let searchTimer = null

const onSearchInput = () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    const kw = searchKeyword.value.trim()
    router.replace({ query: { ...route.query, search: kw || undefined } })
    loadTasks()
  }, 300)
}

const onScopeChange = () => {
  clearTimeout(searchTimer)
  // 空选或全选 3 项都等价于"全部范围"，不传 scope 参数
  const sel = searchScope.value
  const scopeParam = sel.length && sel.length < 3 ? sel.join(',') : undefined
  router.replace({ query: { ...route.query, scope: scopeParam } })
  loadTasks()
}

const onSearchClear = () => {
  clearTimeout(searchTimer)
  // 此时 v-model 已被清空（clear 事件晚于值更新触发），无条件恢复全量列表
  router.replace({ query: { ...route.query, search: undefined } })
  loadTasks()
}

const escapeHtml = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

// 关键词高亮（先转义再替换，防 XSS）
const highlightText = (text) => {
  const kw = searchKeyword.value.trim()
  if (!kw) return escapeHtml(text)
  const escaped = escapeHtml(text)
  const kwEsc = escapeHtml(kw).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return escaped.replace(new RegExp(`(${kwEsc})`, 'gi'), '<mark class="hit-mark">$1</mark>')
}

// 自动对齐所有任务卡的「当前负责人」列宽
const alignContactCols = () => {
  nextTick(() => {
    if (!taskListRef.value) return
    const cols = taskListRef.value.querySelectorAll('.task-contact-col')
    if (!cols.length) return
    // 临时放开 overflow 限制，确保 scrollWidth 返回完整内容宽度
    cols.forEach(el => { el.style.overflow = 'visible' })
    let maxW = 0
    cols.forEach(el => { maxW = Math.max(maxW, el.scrollWidth) })
    cols.forEach(el => {
      el.style.width = maxW + 'px'
      el.style.overflow = ''  // 恢复 CSS scoped 的 overflow: hidden
    })
  })
}

// 状态池有加载完成时更新 form 的默认状态
const defaultStatusId = ref(null)
// 项目内所有任务的当前状态和标签（用于决定是否显示已停用筛选项）
const usedStatusIds = ref(new Set())
// 标签对应任务计数
const tagCount = ref({})
// 状态对应任务计数
const statusCount = ref({})
const allTaskCount = ref(0)
const load = async () => {
  const [all, s, tg] = await Promise.all([
    getProjects(),
    getStatuses(projectId, { show_inactive: true }),
    getTags(projectId, { show_inactive: true }),
  ])
  project.value = all.find(p => p.display_id === projectId)
  statuses.value = s
  tags.value = tg
  defaultStatusId.value = s.find(st => st.is_default)?.id ?? null
  usedStatusIds.value = new Set()

  // 从配置文件恢复排序（仅在路由没有显式指定时）
  if (!route.query.sort_by && !route.query.sort_order) {
    const saved = await getTaskSortConfig(projectId)
    if (saved?.sort_by) sortBy.value = saved.sort_by
    if (saved?.sort_order) sortOrder.value = saved.sort_order
  }

  await loadTasks()
}
const loadTasks = async () => {
  const params = { sort_by: sortBy.value, sort_order: sortOrder.value }
  if (activeStatus.value !== null) params.status_id = activeStatus.value
  if (activeTagIds.value.length) params.tag_ids = activeTagIds.value.join(',')
  const kw = searchKeyword.value.trim()
  if (kw) params.search = kw
  // 部分选中范围时传逗号组合；空/全选=全部范围不传
  if (searchScope.value.length && searchScope.value.length < 3) {
    params.search_scope = searchScope.value.join(',')
  }
  tasks.value = await getTasks(projectId, params)
  // 刷新后重新计算当前使用的状态/标签ID（覆盖筛选后可见的已停用项）
  const allTasks = await getTasks(projectId, {})
  usedStatusIds.value = new Set(allTasks.map(t => t.status_id).filter(Boolean))
  allTaskCount.value = allTasks.length
  // 计算每个标签的任务计数
  const tagCounts = {}
  const statusCounts = {}
  allTasks.forEach(t => {
    (t.tags || []).forEach(tag => {
      tagCounts[tag.id] = (tagCounts[tag.id] || 0) + 1
    })
    if (t.status_id) {
      statusCounts[t.status_id] = (statusCounts[t.status_id] || 0) + 1
    }
  })
  tagCount.value = tagCounts
  statusCount.value = statusCounts
  alignContactCols()
}

const setFilter = (statusId) => {
  activeStatus.value = statusId
  router.replace({ query: { ...route.query, status_id: statusId || undefined } })
  loadTasks()
}

const toggleTagFilter = (tagId) => {
  const idx = activeTagIds.value.indexOf(tagId)
  if (idx === -1) {
    activeTagIds.value.push(tagId)
  } else {
    activeTagIds.value.splice(idx, 1)
  }
  router.replace({ query: { ...route.query, tag_ids: activeTagIds.value.length ? activeTagIds.value.join(',') : undefined } })
  loadTasks()
}

const onSortChange = (val) => {
  router.replace({ query: { ...route.query, sort_by: val || undefined, sort_order: sortOrder.value || undefined } })
  loadTasks()
  saveSortConfig()
}

const toggleSortOrder = () => {
  sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  router.replace({ query: { ...route.query, sort_order: sortOrder.value || undefined } })
  loadTasks()
  saveSortConfig()
}

const saveSortConfig = async () => {
  try {
    await putTaskSortConfig(projectId, { sort_by: sortBy.value, sort_order: sortOrder.value })
  } catch { /* 静默写入，不影响用户体验 */ }
}

const formatTime = (dt) => dayjs(dt).format('YYYY-MM-DD HH:mm')

const goTask = (taskId) => {
  router.push({
    path: `/projects/${projectId}/tasks/${taskId}`,
    query: route.query
  })
}

// 监听路由 query 变化（如浏览器前进/后退时恢复筛选和排序状态）
watch(() => route.query.status_id, (newVal) => {
  const sid = newVal ? Number(newVal) : null
  if (sid !== activeStatus.value) {
    activeStatus.value = sid
    loadTasks()
  }
})
watch(() => route.query.sort_by, (newVal) => {
  if (newVal && newVal !== sortBy.value) {
    sortBy.value = newVal
    loadTasks()
  }
})

watch(() => route.query.sort_order, (newVal) => {
  if (newVal && newVal !== sortOrder.value) {
    sortOrder.value = newVal
    loadTasks()
  }
})

watch(() => route.query.search, (newVal) => {
  const v = newVal || ''
  if (v !== searchKeyword.value) {
    searchKeyword.value = v
    loadTasks()
  }
})

watch(() => route.query.scope, (newVal) => {
  const arr = newVal ? String(newVal).split(',').filter(Boolean) : []
  if (arr.join(',') !== searchScope.value.join(',')) {
    searchScope.value = arr
    loadTasks()
  }
})

onMounted(load)
onBeforeRouteUpdate(() => { load() })

const statusColor = (id) => statuses.value.find(s => s.id === id)?.color || '#aaa'
const statusName = (id) => statuses.value.find(s => s.id === id)?.name || '无状态'
const priorityLabel = (p) => ({ low: '低', normal: '普通', high: '高', urgent: '紧急' }[p] || p)
const priorityType = (p) => ({ low: 'info', normal: undefined, high: 'warning', urgent: 'danger' }[p] || undefined)

const resetForm = () => {
  form.value = {
    title: '',
    description: '',
    status_id: defaultStatusId.value,
    priority: 'normal',
    due_date: null,
    tag_ids: []
  }
  editTarget.value = null
}

const openEdit = (t) => {
  editTarget.value = t
  form.value = {
    title: t.title,
    description: t.description,
    status_id: t.status_id,
    priority: t.priority,
    due_date: t.due_date,
    tag_ids: (t.tags || []).map(tag => tag.id)
  }
  showCreate.value = true
}

const submit = async () => {
  if (!form.value.title.trim()) { ElMessage.warning('标题不能为空'); return }
  loading.value = true
  try {
    const payload = { ...form.value }
    if (payload.status_id != null) payload.status_id = Number(payload.status_id)
    if (editTarget.value) {
      await updateTask(projectId, editTarget.value.display_id, payload)
      ElMessage.success('已更新')
    } else {
      await createTask(projectId, payload)
      ElMessage.success('创建成功')
    }
    showCreate.value = false
    await loadTasks()
  } finally { loading.value = false }
}

const removeTask = async (t) => {
  await ElMessageBox.confirm(`确定删除任务「${t.title}」吗？`, '警告', { type: 'warning' })
  await deleteTask(projectId, t.display_id)
  ElMessage.success('已删除')
  await loadTasks()
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-title { font-size: 20px; font-weight: 600; }
.page-sub { font-size: 13px; color: #888; margin-top: 4px; }
.header-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
.search-group { display: inline-flex; align-items: stretch; }
.scope-select { width: 150px; }
/* 下拉：左圆角，只保留左/上/下边框（右缘与输入框融合） */
.scope-select :deep(.el-select__wrapper) {
  border-radius: 4px 0 0 4px;
  box-shadow: inset 1px 0 0 0 var(--el-border-color), inset 0 1px 0 0 var(--el-border-color), inset 0 -1px 0 0 var(--el-border-color) !important;
}
/* 输入框：右圆角，只保留右/上/下边框（左缘与下拉融合，中间无分割线） */
.search-group .search-input { width: 300px; }
.search-group .search-input :deep(.el-input__wrapper) {
  border-radius: 0 4px 4px 0;
  box-shadow: inset -1px 0 0 0 var(--el-border-color), inset 0 1px 0 0 var(--el-border-color), inset 0 -1px 0 0 var(--el-border-color) !important;
}
/* 聚焦/展开时整组同步高亮为主题紫 */
.search-group:focus-within .scope-select :deep(.el-select__wrapper) {
  box-shadow: inset 1px 0 0 0 #534ab7, inset 0 1px 0 0 #534ab7, inset 0 -1px 0 0 #534ab7 !important;
}
.search-group:focus-within .search-input :deep(.el-input__wrapper) {
  box-shadow: inset -1px 0 0 0 #534ab7, inset 0 1px 0 0 #534ab7, inset 0 -1px 0 0 #534ab7 !important;
}
.filter-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.filter-label { font-size: 13px; color: #888; }
.task-list { display: flex; flex-direction: column; gap: 8px; }
.task-row { background: #fff; border-radius: 8px; border: 1px solid #e8e8e4; padding: 14px 18px; display: flex; align-items: center; gap: 14px; cursor: pointer; transition: border-color .15s; }
.task-row:hover { border-color: #534ab7; }
.task-status-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.task-info { flex: 1; min-width: 0; }
.task-title { font-size: 14px; font-weight: 500; display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.task-tags-inline { display: inline-flex; align-items: center; gap: 3px; flex-wrap: wrap; }
.tag-chip { font-size: 11px; padding: 1px 7px; border-radius: 10px; border: 1px solid; line-height: 1.5; }
.task-meta { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #888; }
.task-contacts { display: flex; align-items: center; gap: 3px; }
.task-comm-time { color: #aaa; font-size: 12px; }
.task-comm-info { display: inline-flex; gap: 24px; color: #aaa; font-size: 12px; }
.task-contact-col { flex-shrink: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.task-comm-col { white-space: nowrap; }
.search-count { font-size: 12px; color: #888; }
.search-hits { margin-top: 8px; padding: 6px 10px; background: #f6f5ff; border-radius: 6px; display: flex; flex-direction: column; gap: 4px; }
.search-hit-fields { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.hit-field-chip { font-size: 11px; background: #534ab7; color: #fff; border-radius: 4px; padding: 0 6px; line-height: 1.7; }
.search-hit-comm { font-size: 12px; color: #666; display: flex; gap: 8px; align-items: baseline; }
.hit-time { color: #999; flex-shrink: 0; font-size: 11px; white-space: nowrap; }
.hit-subject { font-weight: 600; color: #534ab7; flex-shrink: 0; }
.hit-snippet { line-height: 1.5; word-break: break-all; }
.hit-mark { background: #ffe58f; color: inherit; padding: 0 1px; border-radius: 2px; }
.sort-group { display: inline-flex; align-items: center; }
.sort-group .el-select { width: 120px; }
.sort-group .el-select .el-input__wrapper { border-radius: 4px 0 0 4px; border-right: none; }
.sort-group .el-select .el-input__inner { padding-right: 4px; }
.sort-order-btn { border-radius: 0 4px 4px 0; border-left: none; margin-left: -1px; }
.task-status-tag { flex-shrink: 0; }
.task-date-col { font-size: 12px; color: #e24b4a; flex-shrink: 0; white-space: nowrap; }
.task-actions { display: flex; gap: 4px; flex-shrink: 0; }

.checkin-section { background: #fff; border-radius: 8px; border: 1px solid #e8e8e4; padding: 14px 18px; margin-bottom: 16px; }
.checkin-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.checkin-title { font-size: 14px; font-weight: 500; display: flex; align-items: center; gap: 6px; color: #444; }
.checkin-input-row { display: flex; gap: 8px; margin-bottom: 10px; }
.checkin-list { display: flex; flex-direction: column; gap: 6px; }
.checkin-item { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #555; }
.checkin-date { font-weight: 500; color: #534ab7; min-width: 36px; }
.checkin-dot { width: 6px; height: 6px; border-radius: 50%; background: #534ab7; flex-shrink: 0; }
.checkin-content { flex: 1; color: #333; }
</style>
