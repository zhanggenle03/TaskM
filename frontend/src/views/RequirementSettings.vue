<template>
  <div>
    <el-breadcrumb separator="/" style="margin-bottom:20px">
      <el-breadcrumb-item :to="{ path: '/projects' }">项目列表</el-breadcrumb-item>
      <el-breadcrumb-item :to="{ path: `/projects/${projectId}/requirements` }">返回需求列表</el-breadcrumb-item>
      <el-breadcrumb-item>需求设置</el-breadcrumb-item>
    </el-breadcrumb>

    <el-tabs v-model="activeTab" tab-position="left" style="min-height:400px">
      <!-- ===== 字段管理 ===== -->
      <el-tab-pane label="字段管理" name="fields">
        <div class="tab-header">
          <span>管理需求字段。支持拖拽排序；停用字段后，已停用的字段数据不受影响，重新启用后可恢复数据；删除字段则不保留数据。</span>
          <span style="display:flex;align-items:center;gap:8px">
            <span style="font-size:12px;color:#999">显示已停用</span>
            <el-switch v-model="showInactive" size="small" @change="load" />
            <el-button type="primary" @click="openAddField">
              <el-icon><Plus /></el-icon> 新增字段
            </el-button>
          </span>
        </div>

        <div class="list">
          <div
            v-for="(f, i) in displayFields"
            :key="f.id"
            class="list-item"
            :class="{
              'drag-over': dragOver === i,
              inactive: !f.is_active,
              'builtin-item': f.builtin,
            }"
            :draggable="(!f.builtin && f.is_active) ? 'true' : 'false'"
            @dragstart="!f.builtin && f.is_active && (dragIdx = i)"
            @dragover.prevent="!f.builtin && f.is_active && (dragOver = i)"
            @dragleave="dragOver = -1"
            @drop="!f.builtin && f.is_active && onDrop(i)"
            @dragend="dragIdx = -1; dragOver = -1"
          >
            <span v-if="!f.builtin" class="drag-handle" :style="{ opacity: f.is_active ? 1 : 0.3 }"><el-icon><Rank /></el-icon></span>
            <span v-else style="width:20px"></span>
            <div class="dot" :style="{ background: f.builtin ? '#bbb' : '#534ab7' }"></div>
            <div style="flex:1;min-width:0">
              <div class="item-name" :class="{ 'inactive-text': !f.is_active }">{{ f.field_name }}</div>
              <div style="font-size:12px;color:#888">
                {{ f.builtin ? '内置字段' : fieldTypeLabel(f.field_type) }}{{ !f.builtin && f.field_type === 'dropdown' && f.field_options ? ' · ' + f.field_options.replace(/\n/g, ' / ') : '' }}
              </div>
            </div>
            <el-tag v-if="f.builtin" size="small" type="info" effect="plain">内置</el-tag>
            <el-tag v-if="!f.is_active && !f.builtin" type="warning" size="small">已停用</el-tag>
            <template v-if="!f.builtin">
              <el-button v-if="f.is_active" size="small" text @click="editField(f)"><el-icon><Edit /></el-icon></el-button>
              <el-button v-if="f.is_active" size="small" text type="warning" @click="removeField(f)"><el-icon><Remove /></el-icon> 停用</el-button>
              <el-button v-if="f.is_active" size="small" text type="danger" @click="permanentDelete(f)"><el-icon><Delete /></el-icon> 彻底删除</el-button>
              <template v-else>
                <el-button size="small" text type="primary" @click="restoreField(f)"><el-icon><Refresh /></el-icon> 还原</el-button>
                <el-button size="small" text type="danger" @click="permanentDelete(f)"><el-icon><Delete /></el-icon> 彻底删除</el-button>
              </template>
            </template>
          </div>
          <el-empty v-if="!displayFields.length" description="暂无字段" :image-size="60" />
        </div>
      </el-tab-pane>

      <!-- ===== 状态池 ===== -->
      <el-tab-pane label="状态池" name="statusPool">
        <div class="tab-header">
          <span>管理需求的状态选项，可拖拽排序，颜色可自定义。</span>
          <span style="display:flex;align-items:center;gap:8px">
            <span style="font-size:12px;color:#999">显示已停用</span>
            <el-switch v-model="showInactiveStatus" size="small" @change="loadStatusPools" />
            <el-button type="primary" @click="openAddDialog('status')">
              <el-icon><Plus /></el-icon> 新增状态
            </el-button>
          </span>
        </div>
        <div class="list">
          <div
            v-for="(s, i) in statusPools"
            :key="s.id"
            class="list-item"
            :class="{'drag-over': statusDragOver === i, inactive: !s.is_active}"
            :draggable="s.is_active ? 'true' : 'false'"
            @dragstart="s.is_active && (statusDragIdx = i)"
            @dragover.prevent="s.is_active && (statusDragOver = i)"
            @dragleave="statusDragOver = -1"
            @drop="s.is_active && onStatusDrop(i)"
            @dragend="statusDragIdx = -1; statusDragOver = -1"
          >
            <span class="drag-handle" :style="{opacity: s.is_active ? 1 : 0.3}"><el-icon><Rank /></el-icon></span>
            <div class="dot" :style="{background: s.color}"></div>
            <div class="item-name" :class="{'inactive-text': !s.is_active}">{{ s.name }}</div>
            <el-color-picker v-if="s.is_active" v-model="s.color" size="small" @change="onStatusColorChange(s)" />
            <el-tag v-if="s.is_default" type="info" size="small">默认</el-tag>
            <el-tag v-if="!s.is_active" type="warning" size="small">已停用</el-tag>
            <div style="flex:1"></div>
            <el-button v-if="s.is_active" size="small" text @click="openEditDialog('status', s)"><el-icon><Edit /></el-icon></el-button>
            <template v-if="!s.is_active">
              <el-button size="small" text type="primary" @click="restorePool('status', s)"><el-icon><Refresh /></el-icon> 还原</el-button>
              <el-button size="small" text type="danger" @click="permanentDeletePool('status', s)"><el-icon><Delete /></el-icon> 彻底删除</el-button>
            </template>
            <template v-else-if="!s.is_default">
              <el-button size="small" text type="warning" @click="removePool('status', s)"><el-icon><Remove /></el-icon> 停用</el-button>
              <el-button size="small" text type="danger" @click="permanentDeletePool('status', s)"><el-icon><Delete /></el-icon> 彻底删除</el-button>
            </template>
          </div>
          <el-empty v-if="!statusPools.length" description="暂无状态" :image-size="60" />
        </div>
      </el-tab-pane>

      <!-- ===== 优先级池 ===== -->
      <el-tab-pane label="优先级池" name="priorityPool">
        <div class="tab-header">
          <span>管理需求的优先级选项，可拖拽排序，颜色可自定义。</span>
          <span style="display:flex;align-items:center;gap:8px">
            <span style="font-size:12px;color:#999">显示已停用</span>
            <el-switch v-model="showInactivePriority" size="small" @change="loadPriorityPools" />
            <el-button type="primary" @click="openAddDialog('priority')">
              <el-icon><Plus /></el-icon> 新增优先级
            </el-button>
          </span>
        </div>
        <div class="list">
          <div
            v-for="(p, i) in priorityPools"
            :key="p.id"
            class="list-item"
            :class="{'drag-over': priorityDragOver === i, inactive: !p.is_active}"
            :draggable="p.is_active ? 'true' : 'false'"
            @dragstart="p.is_active && (priorityDragIdx = i)"
            @dragover.prevent="p.is_active && (priorityDragOver = i)"
            @dragleave="priorityDragOver = -1"
            @drop="p.is_active && onPriorityDrop(i)"
            @dragend="priorityDragIdx = -1; priorityDragOver = -1"
          >
            <span class="drag-handle" :style="{opacity: p.is_active ? 1 : 0.3}"><el-icon><Rank /></el-icon></span>
            <div class="dot" :style="{background: p.color}"></div>
            <div class="item-name" :class="{'inactive-text': !p.is_active}">{{ p.name }}</div>
            <el-color-picker v-if="p.is_active" v-model="p.color" size="small" @change="onPriorityColorChange(p)" />
            <el-tag v-if="p.is_default" type="info" size="small">默认</el-tag>
            <el-tag v-if="!p.is_active" type="warning" size="small">已停用</el-tag>
            <div style="flex:1"></div>
            <el-button v-if="p.is_active" size="small" text @click="openEditDialog('priority', p)"><el-icon><Edit /></el-icon></el-button>
            <template v-if="!p.is_active">
              <el-button size="small" text type="primary" @click="restorePool('priority', p)"><el-icon><Refresh /></el-icon> 还原</el-button>
              <el-button size="small" text type="danger" @click="permanentDeletePool('priority', p)"><el-icon><Delete /></el-icon> 彻底删除</el-button>
            </template>
            <template v-else-if="!p.is_default">
              <el-button size="small" text type="warning" @click="removePool('priority', p)"><el-icon><Remove /></el-icon> 停用</el-button>
              <el-button size="small" text type="danger" @click="permanentDeletePool('priority', p)"><el-icon><Delete /></el-icon> 彻底删除</el-button>
            </template>
          </div>
          <el-empty v-if="!priorityPools.length" description="暂无优先级" :image-size="60" />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 新增/编辑字段弹窗 -->
    <el-dialog v-model="fieldDialogVisible" :title="editingField ? '编辑字段' : '新增字段'" width="450px" :close-on-click-modal="false">
      <el-form :model="fieldForm" label-width="80px">
        <el-form-item label="字段名称" required>
          <el-input v-model="fieldForm.field_name" placeholder="字段名称" />
        </el-form-item>
        <el-form-item label="字段类型" required>
          <el-select v-model="fieldForm.field_type" style="width:100%">
            <el-option label="文本" value="text" />
            <el-option label="下拉选项" value="dropdown" />
            <el-option label="日期" value="date" />
            <el-option label="数字" value="number" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="fieldForm.field_type === 'dropdown'" label="选项">
          <el-input v-model="fieldForm.field_options" type="textarea" :rows="3" placeholder="每行一个选项" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="fieldDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="fieldLoading" @click="submitField">确定</el-button>
      </template>
    </el-dialog>

    <!-- 新增/编辑状态/优先级弹窗 -->
    <el-dialog v-model="poolDialogVisible" :title="poolDialogTitle" width="380px" :close-on-click-modal="false">
      <el-form :model="poolForm" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="poolForm.name" :placeholder="poolDialogType === 'status' ? '如：待评估、开发中...' : '如：低、普通...'" />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker v-model="poolForm.color" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="poolForm.is_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="poolDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="poolLoading" @click="submitPool">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getReqCustomFields, createReqCustomField, updateReqCustomField, deleteReqCustomField,
  getReqStatusPools, createReqStatusPool, updateReqStatusPool, deleteReqStatusPool,
  getReqPriorityPools, createReqPriorityPool, updateReqPriorityPool, deleteReqPriorityPool,
} from '../api/index.js'

const route = useRoute()
const projectId = route.params.projectId
const fields = ref([])
const activeTab = ref('fields')
const showInactive = ref(false)
const showInactiveStatus = ref(false)
const showInactivePriority = ref(false)
const fieldLoading = ref(false)
const fieldDialogVisible = ref(false)
const editingField = ref(null)
const dragIdx = ref(-1)
const dragOver = ref(-1)

// ---- 状态池 ----
const statusPools = ref([])
const statusDragIdx = ref(-1)
const statusDragOver = ref(-1)

// ---- 优先级池 ----
const priorityPools = ref([])
const priorityDragIdx = ref(-1)
const priorityDragOver = ref(-1)

// ---- 状态/优先级弹窗 ----
const poolDialogVisible = ref(false)
const poolLoading = ref(false)
const poolDialogType = ref('status')
const editingPool = ref(null)
const poolForm = ref({ name: '', color: '#5F5E5A', is_default: false })

const poolDialogTitle = computed(() => {
  const prefix = editingPool.value ? '编辑' : '新增'
  const label = poolDialogType.value === 'status' ? '状态' : '优先级'
  return prefix + label
})

const COLOR_PALETTE = [
  '#E24B4A', '#E8833A', '#F1A43C', '#6B9F3A', '#1F9A8D',
  '#1F7EB7', '#534AB7', '#993C9D', '#D43D7A', '#854F0B',
]
const _randomColor = (pool) => {
  const used = new Set(pool.map(i => i.color))
  const avail = COLOR_PALETTE.filter(c => !used.has(c))
  return avail.length ? avail[Math.floor(Math.random() * avail.length)] : COLOR_PALETTE[Math.floor(Math.random() * COLOR_PALETTE.length)]
}

const fieldForm = ref({
  field_name: '',
  field_type: 'text',
  field_options: '',
})

const fieldTypeLabel = (t) => ({ text: '文本', dropdown: '下拉选项', date: '日期', number: '数字' }[t] || t)

// 基础字段定义
const builtInFields = [
  { id: '_title', field_name: '标题', field_type: 'text', field_options: '', is_active: true, builtin: true },
  { id: '_status', field_name: '状态', field_type: 'dropdown', field_options: '待处理\n进行中\n已完成\n已取消', is_active: true, builtin: true },
  { id: '_priority', field_name: '优先级', field_type: 'dropdown', field_options: '低\n普通\n高\n紧急', is_active: true, builtin: true },
]

// 合并显示：基础字段在前，自定义字段在后
const displayFields = computed(() => [
  ...builtInFields,
  ...fields.value,
])

function openAddField() {
  editingField.value = null
  fieldForm.value = { field_name: '', field_type: 'text', field_options: '' }
  fieldDialogVisible.value = true
}

function editField(f) {
  editingField.value = f
  fieldForm.value = { field_name: f.field_name, field_type: f.field_type, field_options: f.field_options }
  fieldDialogVisible.value = true
}

async function submitField() {
  if (!fieldForm.value.field_name.trim()) {
    ElMessage.warning('请输入字段名称')
    return
  }
  fieldLoading.value = true
  try {
    if (editingField.value) {
      await updateReqCustomField(projectId, editingField.value.id, fieldForm.value)
      ElMessage.success('字段已更新')
    } else {
      await createReqCustomField(projectId, fieldForm.value)
      ElMessage.success('字段已创建')
    }
    fieldDialogVisible.value = false
    await load()
  } finally {
    fieldLoading.value = false
  }
}

async function removeField(f) {
  try {
    await ElMessageBox.confirm(`确定停用字段「${f.field_name}」吗？\n已使用该字段的数据不受影响。`, '提示', { type: 'warning' })
    await deleteReqCustomField(projectId, f.id)
    ElMessage.success('字段已停用')
    await load()
  } catch {}
}

async function restoreField(f) {
  await createReqCustomField(projectId, { field_name: f.field_name, field_type: f.field_type, field_options: f.field_options, sort_order: f.sort_order })
  await load()
}

async function permanentDelete(f) {
  try {
    await ElMessageBox.confirm(`确定永久删除字段「${f.field_name}」？\n该字段下所有需求的值将被永久移除。`, '确认删除', { type: 'warning' })
    await deleteReqCustomField(projectId, f.id, { params: { force: true }, _silentError: true })
    ElMessage.success('字段已永久删除')
    await load()
  } catch {}
}

// 拖拽排序
const onDrop = async (i) => {
  dragOver.value = -1
  if (dragIdx.value < 0 || dragIdx.value === i) { dragIdx.value = -1; return }
  const offset = builtInFields.length
  const adjustedFrom = dragIdx.value - offset
  const adjustedTo = i - offset
  if (adjustedFrom < 0 || adjustedTo < 0) { dragIdx.value = -1; return }
  const arr = fields.value
  const [moved] = arr.splice(adjustedFrom, 1)
  arr.splice(adjustedTo, 0, moved)
  dragIdx.value = -1
  for (let idx = 0; idx < arr.length; idx++) {
    if (arr[idx].sort_order !== idx) {
      arr[idx].sort_order = idx
      try { await updateReqCustomField(projectId, arr[idx].id, { sort_order: idx }) } catch {}
    }
  }
  fields.value = [...arr]
}

onMounted(load)

// ---- load ----
async function load() {
  const params = showInactive.value ? { show_inactive: true } : undefined
  fields.value = await getReqCustomFields(projectId, params)
  await loadStatusPools()
  await loadPriorityPools()
}

async function loadStatusPools() {
  const params = showInactiveStatus.value ? { show_inactive: true } : undefined
  statusPools.value = await getReqStatusPools(projectId, params)
}

async function loadPriorityPools() {
  const params = showInactivePriority.value ? { show_inactive: true } : undefined
  priorityPools.value = await getReqPriorityPools(projectId, params)
}

// ---- 状态/优先级弹窗 CRUD ----
function openAddDialog(type) {
  poolDialogType.value = type
  editingPool.value = null
  const pool = type === 'status' ? statusPools.value : priorityPools.value
  poolForm.value = { name: '', color: _randomColor(pool), is_default: false }
  poolDialogVisible.value = true
}

function openEditDialog(type, item) {
  poolDialogType.value = type
  editingPool.value = item
  poolForm.value = { name: item.name, color: item.color, is_default: item.is_default }
  poolDialogVisible.value = true
}

async function submitPool() {
  if (!poolForm.value.name.trim()) { ElMessage.warning('名称不能为空'); return }
  poolLoading.value = true
  try {
    const isStatus = poolDialogType.value === 'status'
    if (editingPool.value) {
      if (isStatus) {
        await updateReqStatusPool(projectId, editingPool.value.id, poolForm.value)
      } else {
        await updateReqPriorityPool(projectId, editingPool.value.id, poolForm.value)
      }
    } else {
      if (isStatus) {
        await createReqStatusPool(projectId, poolForm.value)
      } else {
        await createReqPriorityPool(projectId, poolForm.value)
      }
    }
    poolDialogVisible.value = false
    isStatus ? await loadStatusPools() : await loadPriorityPools()
  } finally { poolLoading.value = false }
}

async function removePool(type, item) {
  const label = type === 'status' ? '状态' : '优先级'
  await ElMessageBox.confirm(`确定停用${label}「${item.name}」吗？`, '提示', { type: 'warning' })
  if (type === 'status') {
    await deleteReqStatusPool(projectId, item.id)
  } else {
    await deleteReqPriorityPool(projectId, item.id)
  }
  type === 'status' ? await loadStatusPools() : await loadPriorityPools()
}

async function restorePool(type, item) {
  const data = { name: item.name, color: item.color, sort_order: item.sort_order, is_default: item.is_default }
  if (type === 'status') {
    await createReqStatusPool(projectId, data)
    await loadStatusPools()
  } else {
    await createReqPriorityPool(projectId, data)
    await loadPriorityPools()
  }
}

async function permanentDeletePool(type, item) {
  const label = type === 'status' ? '状态' : '优先级'
  try {
    const deleteFn = type === 'status'
      ? () => deleteReqStatusPool(projectId, item.id, { params: { force: true }, _silentError: true })
      : () => deleteReqPriorityPool(projectId, item.id, { params: { force: true }, _silentError: true })
    const deleteConfirmed = type === 'status'
      ? () => deleteReqStatusPool(projectId, item.id, { params: { force: true, confirmed: true }, _silentError: true })
      : () => deleteReqPriorityPool(projectId, item.id, { params: { force: true, confirmed: true }, _silentError: true })

    const result = await deleteFn()
    const refs = result?.refs_cleaned
    if (refs && Object.keys(refs).length) {
      const text = Object.entries(refs).map(([k, v]) => `${k}: ${v}`).join('、')
      ElMessage.success(`已彻底删除「${item.name}」，清理了 ${text}`)
    } else {
      ElMessage.success(`已彻底删除「${item.name}」`)
    }
  } catch (err) {
    if (err.response?.status === 409) {
      const refs = err.response.data.detail.refs
      const refText = Object.entries(refs).map(([k, v]) => `${k}: ${v}个`).join('、')
      await ElMessageBox.confirm(
        `「${item.name}」被以下数据引用：\n${refText}\n\n彻底删除后，这些引用将被置为默认值。确认彻底删除？`,
        '确认彻底删除',
        { type: 'warning', confirmButtonText: '彻底删除' }
      )
      const deleteConfirmed = type === 'status'
        ? () => deleteReqStatusPool(projectId, item.id, { params: { force: true, confirmed: true }, _silentError: true })
        : () => deleteReqPriorityPool(projectId, item.id, { params: { force: true, confirmed: true }, _silentError: true })
      const result = await deleteConfirmed()
      const cleaned = result?.refs_cleaned
      if (cleaned && Object.keys(cleaned).length) {
        const text = Object.entries(cleaned).map(([k, v]) => `${k}: ${v}`).join('、')
        ElMessage.success(`已彻底删除「${item.name}」，清理了 ${text}`)
      } else {
        ElMessage.success(`已彻底删除「${item.name}」`)
      }
    } else {
      ElMessage.error(err.response?.data?.detail?.message || err.response?.data?.detail || '删除失败')
    }
  }
  type === 'status' ? await loadStatusPools() : await loadPriorityPools()
}

// ---- 颜色即时更新 ----
async function onStatusColorChange(s) { await updateReqStatusPool(projectId, s.id, { color: s.color }) }
async function onPriorityColorChange(p) { await updateReqPriorityPool(projectId, p.id, { color: p.color }) }

// ---- 拖拽 ----
async function onStatusDrop(i) {
  statusDragOver.value = -1
  if (statusDragIdx.value < 0 || statusDragIdx.value === i) { statusDragIdx.value = -1; return }
  const arr = statusPools.value
  const [moved] = arr.splice(statusDragIdx.value, 1)
  arr.splice(i, 0, moved)
  statusDragIdx.value = -1
  for (let idx = 0; idx < arr.length; idx++) {
    if (arr[idx].sort_order !== idx) {
      arr[idx].sort_order = idx
      try { await updateReqStatusPool(projectId, arr[idx].id, { sort_order: idx }) } catch {}
    }
  }
  statusPools.value = [...arr]
}

async function onPriorityDrop(i) {
  priorityDragOver.value = -1
  if (priorityDragIdx.value < 0 || priorityDragIdx.value === i) { priorityDragIdx.value = -1; return }
  const arr = priorityPools.value
  const [moved] = arr.splice(priorityDragIdx.value, 1)
  arr.splice(i, 0, moved)
  priorityDragIdx.value = -1
  for (let idx = 0; idx < arr.length; idx++) {
    if (arr[idx].sort_order !== idx) {
      arr[idx].sort_order = idx
      try { await updateReqPriorityPool(projectId, arr[idx].id, { sort_order: idx }) } catch {}
    }
  }
  priorityPools.value = [...arr]
}
</script>

<style scoped>
.tab-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; font-size: 13px; color: #888; }
.list { display: flex; flex-direction: column; gap: 8px; }
.list-item { background: #fff; border: 1px solid #e8e8e4; border-radius: 8px; padding: 12px 16px; display: flex; align-items: center; gap: 12px; transition: border-color .15s, box-shadow .15s; }
.list-item[draggable="true"] { cursor: grab; }
.list-item[draggable="true"]:active { cursor: grabbing; }
.list-item.drag-over { border-color: #534ab7; box-shadow: 0 0 0 2px rgba(83,74,183,.15); }
.list-item.inactive { background: #f5f5f5; opacity: 0.7; }
.builtin-item { background: #fafafa; cursor: default !important; opacity: 0.85; }
.inactive-text { color: #999; }
.drag-handle { color: #bbb; cursor: grab; display: flex; align-items: center; }
.drag-handle:active { cursor: grabbing; }
.dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
.item-name { font-size: 14px; font-weight: 500; min-width: 80px; }
</style>
