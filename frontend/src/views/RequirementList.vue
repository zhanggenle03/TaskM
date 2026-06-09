<template>
  <div class="requirement-page">
    <!-- 面包屑 -->
    <el-breadcrumb separator="/" style="margin-bottom: 20px;">
      <el-breadcrumb-item :to="{ name: 'projects' }">项目列表</el-breadcrumb-item>
      <el-breadcrumb-item>{{ projectName }}</el-breadcrumb-item>
      <el-breadcrumb-item>需求列表</el-breadcrumb-item>
    </el-breadcrumb>
    <!-- 页面头部 -->
    <div class="page-header">
      <h2>需求管理</h2>
      <div class="header-actions">
        <el-button @click="$router.push(`/projects/${projectId}/requirements/settings`)" size="small">
          <el-icon><Setting /></el-icon> 设置
        </el-button>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon> 新建需求
        </el-button>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索需求标题/描述..."
        clearable
        style="width: 260px"
        @input="onSearch"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-select v-model="filterStatus" placeholder="状态筛选" clearable multiple collapse-tags style="width: 180px" @change="loadRequirements">
        <el-option
          v-for="s in statusPools"
          :key="s.id"
          :label="s.name"
          :value="statusNameToValue(s.name)"
        />
      </el-select>
      <el-select v-model="filterPriority" placeholder="优先级筛选" clearable multiple collapse-tags style="width: 160px" @change="loadRequirements">
        <el-option
          v-for="p in priorityPools"
          :key="p.id"
          :label="p.name"
          :value="priorityNameToValue(p.name)"
        />
      </el-select>
    </div>

    <!-- 统计摘要 -->
    <div class="stats-row">
      <el-tag>全部 {{ requirements.length }}</el-tag>
      <el-tag type="warning">待处理 {{ statusCount('todo') }}</el-tag>
      <el-tag type="primary">进行中 {{ statusCount('in_progress') }}</el-tag>
      <el-tag type="success">已完成 {{ statusCount('done') }}</el-tag>
    </div>

    <!-- 需求明细表 -->
    <el-table
      v-if="requirements.length"
      :data="requirements"
      stripe
      border
      style="width: 100%"
      size="small"
      @row-click="openEdit"
      @sort-change="onSortChange"
      class="req-table"
    >
      <el-table-column label="显示ID" width="160" align="center" prop="display_id">
        <template #default="{ row }">
          <span class="id-cell">{{ row.display_id || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="标题" min-width="180" sortable="custom" prop="title">
        <template #default="{ row }">
          <span class="req-title-cell">{{ row.title }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center" sortable :sort-method="sortByStatus">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small" effect="plain">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="优先级" width="80" align="center" sortable :sort-method="sortByPriority">
        <template #default="{ row }">
          <el-tag :type="priorityTagType(row.priority)" size="small">
            {{ priorityLabel(row.priority) }}
          </el-tag>
        </template>
      </el-table-column>
      <!-- 自定义字段列（动态） -->
      <el-table-column
        v-for="cf in customFields"
        :key="'cf_' + cf.id"
        :label="cf.field_name"
        :width="cf.field_type === 'text' ? 140 : 100"
        :align="cf.field_type === 'number' ? 'right' : 'center'"
      >
        <template #default="{ row }">
          <span class="cf-value">{{ getCustomValue(row.custom_values, cf.id) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="70" align="center" fixed="right">
        <template #default="{ row }">
          <el-button text size="small" type="danger" @click.stop="removeReq(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-else description="暂无需求" />

    <!-- 新建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑需求' : '新建需求'"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="80px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="需求标题" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option
              v-for="s in statusPools"
              :key="s.id"
              :label="s.name"
              :value="statusNameToValue(s.name)"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="form.priority" style="width: 100%">
            <el-option
              v-for="p in priorityPools"
              :key="p.id"
              :label="p.name"
              :value="priorityNameToValue(p.name)"
            />
          </el-select>
        </el-form-item>
        <!-- 自定义字段 -->
        <template v-for="cf in customFields" :key="cf.id">
          <el-form-item :label="cf.field_name">
            <el-input v-if="cf.field_type === 'text'" v-model="form.customValues[cf.id]" />
            <el-select v-else-if="cf.field_type === 'dropdown'" v-model="form.customValues[cf.id]" style="width: 100%">
              <el-option
                v-for="opt in parseOptions(cf.field_options)"
                :key="opt"
                :label="opt"
                :value="opt"
              />
            </el-select>
            <el-date-picker
              v-else-if="cf.field_type === 'date'"
              v-model="form.customValues[cf.id]"
              type="date"
              placeholder="选择日期"
              style="width: 100%"
              value-format="YYYY-MM-DD"
            />
            <el-input-number v-else-if="cf.field_type === 'number'" v-model="form.customValues[cf.id]" style="width: 100%" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getRequirements, createRequirement, updateRequirement, deleteRequirement,
  getReqCustomFields, getProject,
  getReqStatusPools, getReqPriorityPools,
} from '../api/index.js'

const route = useRoute()
const router = useRouter()
const projectId = route.params.projectId

// 状态
const requirements = ref([])
const customFields = ref([])
const statusPools = ref([])
const priorityPools = ref([])
const projectName = ref('')
const searchKeyword = ref('')
const filterStatus = ref([])
const filterPriority = ref([])
const sortBy = ref('')
const sortOrder = ref('')
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref(null)

// 表单
const form = ref({
  title: '',
  priority: 'normal',
  status: 'todo',
  customValues: {},
})

// 工具函数
const statusLabel = (s) => ({ todo: '待处理', in_progress: '进行中', done: '已完成', cancelled: '已取消' }[s] || s)
const statusTagType = (s) => ({ todo: 'warning', in_progress: 'primary', done: 'success', cancelled: 'info' }[s] || '')
const priorityLabel = (p) => ({ low: '低', normal: '普通', high: '高', urgent: '紧急' }[p] || p)
const priorityTagType = (p) => ({ low: 'info', normal: '', high: 'warning', urgent: 'danger' }[p] || '')
const parseOptions = (opts) => opts ? opts.split('\n').filter(Boolean) : []

const statusCount = (s) => requirements.value.filter(r => r.status === s).length

const getCustomValue = (values, fieldId) => {
  const found = values.find(v => v.field_id === fieldId)
  return found ? found.value : '—'
}

let searchTimer = null
const onSearch = () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadRequirements, 300)
}

const onSortChange = ({ prop, order }) => {
  sortBy.value = prop
  sortOrder.value = order || ''
  loadRequirements()
}

// 加载数据
async function loadRequirements() {
  const params = {}
  if (sortBy.value) params.sort_by = sortBy.value
  if (sortOrder.value) params.sort_order = sortOrder.value === 'ascending' ? 'asc' : 'desc'
  if (filterStatus.value.length) params.status = filterStatus.value.join(',')
  if (filterPriority.value.length) params.priority = filterPriority.value.join(',')
  if (searchKeyword.value) params.search = searchKeyword.value
  requirements.value = await getRequirements(projectId, params)
}

async function loadCustomFields() {
  customFields.value = await getReqCustomFields(projectId)
}

async function loadPools() {
  statusPools.value = await getReqStatusPools(projectId)
  priorityPools.value = await getReqPriorityPools(projectId)
}

async function loadProject() {
  try {
    const proj = await getProject(projectId)
    projectName.value = proj.name
  } catch {
    projectName.value = '项目'
  }
}

// CRUD
function openCreate() {
  isEditing.value = false
  editingId.value = null
  form.value = { title: '', priority: 'normal', status: 'todo', customValues: {} }
  // 预填自定义字段默认值
  const cv = {}
  customFields.value.forEach(cf => {
    if (cf.field_type === 'number') cv[cf.id] = undefined
    else cv[cf.id] = ''
  })
  form.value.customValues = cv
  dialogVisible.value = true
}

async function openEdit(req) {
  isEditing.value = true
  editingId.value = req.id
  const cv = {}
  customFields.value.forEach(cf => {
    const found = req.custom_values.find(v => v.field_id === cf.id)
    cv[cf.id] = found ? found.value : (cf.field_type === 'number' ? undefined : '')
  })
  form.value = {
    title: req.title,
    priority: req.priority,
    status: req.status,
    customValues: cv,
  }
  dialogVisible.value = true
}

async function submit() {
  if (!form.value.title.trim()) {
    ElMessage.warning('请输入需求标题')
    return
  }
  const data = {
    title: form.value.title,
    priority: form.value.priority,
    status: form.value.status,
    custom_values: form.value.customValues,
  }
  try {
    if (isEditing.value) {
      await updateRequirement(projectId, editingId.value, data)
      ElMessage.success('需求已更新')
    } else {
      await createRequirement(projectId, data)
      ElMessage.success('需求已创建')
    }
    dialogVisible.value = false
    loadRequirements()
  } catch (e) {
    // error handled by interceptor
  }
}

async function removeReq(req) {
  try {
    await ElMessageBox.confirm(`确定删除需求「${req.title}」？`, '确认删除', { type: 'warning' })
    await deleteRequirement(projectId, req.id)
    ElMessage.success('已删除')
    loadRequirements()
  } catch {}
}

// 生命周期
// 按池顺序排序
const statusNameToValue = (name) => {
  const map = { '待处理': 'todo', '进行中': 'in_progress', '已完成': 'done', '已取消': 'cancelled' }
  return map[name] || name
}

const priorityNameToValue = (name) => {
  const map = { '低': 'low', '普通': 'normal', '高': 'high', '紧急': 'urgent' }
  return map[name] || name
}

const sortByStatus = (a, b) => {
  const order = statusPools.value.map(s => /* value from name */ {
    const map = { '待处理': 'todo', '进行中': 'in_progress', '已完成': 'done', '已取消': 'cancelled' }
    return map[s.name] || ''
  })
  const ai = order.indexOf(a.status)
  const bi = order.indexOf(b.status)
  return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
}

const sortByPriority = (a, b) => {
  const order = priorityPools.value.map(p => {
    const map = { '低': 'low', '普通': 'normal', '高': 'high', '紧急': 'urgent' }
    return map[p.name] || ''
  })
  const ai = order.indexOf(a.priority)
  const bi = order.indexOf(b.priority)
  return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
}

onMounted(async () => {
  await loadProject()
  await loadCustomFields()
  await loadPools()
  await loadRequirements()
})
</script>

<style scoped>
.requirement-page { max-width: 1400px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h2 { font-size: 20px; font-weight: 600; }
.header-actions { display: flex; gap: 8px; }
.filter-bar { display: flex; gap: 10px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
.stats-row { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.req-table { cursor: pointer; }
.req-table .el-table__row:hover { background: #f5f4fe !important; }
.req-title-cell { font-weight: 500; color: #2c2c2a; }
.id-cell { font-size: 12px; color: #888; font-family: monospace; }
.cf-value { font-size: 12px; color: #555; }
.text-muted { color: #bbb; }
</style>
