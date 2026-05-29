<template>
  <div>
    <el-breadcrumb separator="/" style="margin-bottom:20px">
      <el-breadcrumb-item :to="{ path: '/projects' }">项目列表</el-breadcrumb-item>
      <el-breadcrumb-item :to="{ path: `/projects/${projectId}` }">返回任务</el-breadcrumb-item>
      <el-breadcrumb-item>设置</el-breadcrumb-item>
    </el-breadcrumb>

    <!-- 项目信息 -->
    <div class="proj-info-bar" v-if="project">
      <span><strong>{{ project.name }}</strong></span>
      <el-tag v-if="project.display_id" size="small" type="info" effect="plain" style="margin-left:8px">{{ project.display_id }}</el-tag>
      <span style="margin-left:12px;color:#999;font-size:13px">前缀：{{ project.custom_prefix || '未设置' }}（创建后不可更改）</span>
    </div>

    <el-tabs v-model="activeTab" tab-position="left" style="min-height:400px">
      <!-- ===== 状态池 ===== -->
      <el-tab-pane label="状态池" name="status">
        <div class="tab-header">
          <span>自定义任务状态，拖拽排序，颜色随意设置。</span>
          <el-button type="primary" @click="openAddDialog('status')">
            <el-icon><Plus /></el-icon> 新增状态
          </el-button>
        </div>

        <div class="list">
          <div
            v-for="(s, i) in statuses"
            :key="s.id"
            class="list-item"
            :class="{ 'drag-over': statusDragOver === i }"
            draggable="true"
            @dragstart="onStatusDragStart(i)"
            @dragover.prevent="statusDragOver = i"
            @dragleave="statusDragOver = -1"
            @drop="onStatusDrop(i)"
            @dragend="statusDragIdx = -1; statusDragOver = -1"
          >
            <span class="drag-handle"><el-icon><Rank /></el-icon></span>
            <div class="dot" :style="{ background: s.color }"></div>
            <div class="item-name">{{ s.name }}</div>
            <el-color-picker v-model="s.color" size="small" @change="updateItem('status', s.id, { color: s.color })" />
            <el-tag v-if="s.is_default" type="info" size="small">默认</el-tag>
            <div style="flex:1"></div>
            <el-button size="small" text @click="openEditDialog('status', s)"><el-icon><Edit /></el-icon></el-button>
            <el-button size="small" text type="danger" @click="removeItem('status', s)"><el-icon><Delete /></el-icon></el-button>
          </div>
          <el-empty v-if="!statuses.length" description="暂无状态" :image-size="60" />
        </div>
      </el-tab-pane>

      <!-- ===== 对接人库 ===== -->
      <el-tab-pane label="对接人库" name="contact">
        <div class="tab-header">
          <span>项目常用对接人库，按首字母排序。</span>
          <el-button type="primary" @click="openAddPC">
            <el-icon><Plus /></el-icon> 新增对接人
          </el-button>
        </div>

        <el-input v-model="pcSearch" placeholder="搜索对接人..." clearable style="width:300px;margin-bottom:12px">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>

        <div class="list">
          <div
            v-for="pc in filteredProjectContacts"
            :key="pc.id"
            class="list-item"
            style="cursor:default"
          >
            <div class="avatar">{{ pc.name[0] }}</div>
            <div style="flex:1;min-width:0">
              <div class="item-name">{{ pc.name }}</div>
              <div style="font-size:12px;color:#888">{{ pc.role }} · {{ pc.contact_info }}</div>
            </div>
            <el-button size="small" text @click="openEditPC(pc)"><el-icon><Edit /></el-icon></el-button>
            <el-button size="small" text type="danger" @click="removePC(pc)"><el-icon><Delete /></el-icon></el-button>
          </div>
          <el-empty v-if="!filteredProjectContacts.length" description="暂无对接人" :image-size="60" />
        </div>
      </el-tab-pane>

      <!-- ===== 沟通类型池 ===== -->
      <el-tab-pane label="沟通类型" name="commType">
        <div class="tab-header">
          <span>自定义沟通类型（备注/会议/邮件/电话等），拖拽排序。</span>
          <el-button type="primary" @click="openAddDialog('commType')">
            <el-icon><Plus /></el-icon> 新增类型
          </el-button>
        </div>

        <div class="list">
          <div
            v-for="(t, i) in commTypes"
            :key="t.id"
            class="list-item"
            :class="{ 'drag-over': ctDragOver === i }"
            draggable="true"
            @dragstart="ctDragIdx = i"
            @dragover.prevent="ctDragOver = i"
            @dragleave="ctDragOver = -1"
            @drop="onCommTypeDrop(i)"
            @dragend="ctDragIdx = -1; ctDragOver = -1"
          >
            <span class="drag-handle"><el-icon><Rank /></el-icon></span>
            <div class="dot" :style="{ background: t.color }"></div>
            <div class="item-name">{{ t.name }}</div>
            <el-color-picker v-model="t.color" size="small" @change="updateItem('commType', t.id, { color: t.color })" />
            <el-tag v-if="t.is_default" type="info" size="small">默认</el-tag>
            <div style="flex:1"></div>
            <el-button size="small" text @click="openEditDialog('commType', t)"><el-icon><Edit /></el-icon></el-button>
            <el-button size="small" text type="danger" @click="removeItem('commType', t)"><el-icon><Delete /></el-icon></el-button>
          </div>
          <el-empty v-if="!commTypes.length" description="暂无沟通类型" :image-size="60" />
        </div>
      </el-tab-pane>

      <!-- ===== 标签池 ===== -->
      <el-tab-pane label="标签池" name="tag">
        <div class="tab-header">
          <span>自定义任务标签，拖拽排序，颜色随意设置。</span>
          <el-button type="primary" @click="openTagDialog">
            <el-icon><Plus /></el-icon> 新增标签
          </el-button>
        </div>

        <div class="list">
          <div
            v-for="(t, i) in tags"
            :key="t.id"
            class="list-item"
            :class="{ 'drag-over': tagDragOver === i }"
            draggable="true"
            @dragstart="tagDragIdx = i"
            @dragover.prevent="tagDragOver = i"
            @dragleave="tagDragOver = -1"
            @drop="onTagDrop(i)"
            @dragend="tagDragIdx = -1; tagDragOver = -1"
          >
            <span class="drag-handle"><el-icon><Rank /></el-icon></span>
            <div class="dot" :style="{ background: t.color }"></div>
            <div class="item-name">{{ t.name }}</div>
            <el-color-picker v-model="t.color" size="small" @change="updateTagItem(t.id, { color: t.color })" />
            <div style="flex:1"></div>
            <el-button size="small" text @click="openEditTagDialog(t)"><el-icon><Edit /></el-icon></el-button>
            <el-button size="small" text type="danger" @click="removeTag(t)"><el-icon><Delete /></el-icon></el-button>
          </div>
          <el-empty v-if="!tags.length" description="暂无标签" :image-size="60" />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 新增/编辑弹窗（状态池 + 沟通类型共用） -->
    <el-dialog v-model="showDialog" :title="dialogTitle" width="380px" @close="resetForm">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" :placeholder="dialogType === 'status' ? '如：待评估、开发中...' : '如：微信、面谈...'" />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker v-model="form.color" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="form.is_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="submit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 标签池弹窗 -->
    <el-dialog v-model="showTagDialog" :title="editTagRef ? '编辑标签' : '新增标签'" width="380px" @close="resetTagForm">
      <el-form :model="tagForm" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="tagForm.name" placeholder="如：Bug、功能、优化..." />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker v-model="tagForm.color" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTagDialog = false">取消</el-button>
        <el-button type="primary" :loading="tagLoading" @click="submitTag">确定</el-button>
      </template>
    </el-dialog>

    <!-- 对接人库弹窗 -->
    <el-dialog v-model="showPCDialog" :title="editPCRef ? '编辑对接人' : '新增对接人'" width="380px" @close="resetPCForm">
      <el-form :model="pcForm" label-width="80px">
        <el-form-item label="姓名" required>
          <el-input v-model="pcForm.name" placeholder="对接人姓名" />
        </el-form-item>
        <el-form-item label="角色">
          <el-input v-model="pcForm.role" placeholder="如：项目经理、开发负责人" />
        </el-form-item>
        <el-form-item label="联系方式">
          <el-input v-model="pcForm.contact_info" placeholder="手机/邮件/微信" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPCDialog = false">取消</el-button>
        <el-button type="primary" :loading="pcLoading" @click="submitPC">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getStatuses, createStatus, updateStatus, deleteStatus,
  getCommTypes, createCommType, updateCommType, deleteCommType,
  getProjectContacts, addProjectContact, updateProjectContact, deleteProjectContact,
  getTags, createTag, updateTag, deleteTag,
  getProjects,
} from '../api'

const route = useRoute()
const projectId = route.params.projectId
const project = ref(null)
const activeTab = ref('status')

const statuses = ref([])
const commTypes = ref([])
const tags = ref([])
const tagDragIdx = ref(-1)
const tagDragOver = ref(-1)
const showTagDialog = ref(false)
const tagLoading = ref(false)
const editTagRef = ref(null)
const tagForm = ref({ name: '', color: '#5F5E5A' })

// 对接人库
const projectContacts = ref([])
const pcSearch = ref('')
const showPCDialog = ref(false)
const pcLoading = ref(false)
const editPCRef = ref(null)
const pcForm = ref({ name: '', role: '', contact_info: '' })

const filteredProjectContacts = computed(() => {
  let list = projectContacts.value || []
  if (pcSearch.value) {
    const kw = pcSearch.value.toLowerCase()
    list = list.filter(pc =>
      pc.name.toLowerCase().includes(kw) ||
      pc.role.toLowerCase().includes(kw) ||
      pc.contact_info.toLowerCase().includes(kw)
    )
  }
  return [...list].sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
})

// 对接人库 CRUD
const openAddPC = () => {
  editPCRef.value = null
  pcForm.value = { name: '', role: '', contact_info: '' }
  showPCDialog.value = true
}
const openEditPC = (pc) => {
  editPCRef.value = pc
  pcForm.value = { name: pc.name, role: pc.role, contact_info: pc.contact_info }
  showPCDialog.value = true
}
const resetPCForm = () => {
  pcForm.value = { name: '', role: '', contact_info: '' }
  editPCRef.value = null
}
const submitPC = async () => {
  if (!pcForm.value.name.trim()) { ElMessage.warning('姓名不能为空'); return }
  pcLoading.value = true
  try {
    if (editPCRef.value) {
      await updateProjectContact(projectId, editPCRef.value.id, pcForm.value)
    } else {
      await addProjectContact(projectId, pcForm.value)
    }
    showPCDialog.value = false
    projectContacts.value = await getProjectContacts(projectId, {})
    resetPCForm()
  } finally { pcLoading.value = false }
}
const removePC = async (pc) => {
  await ElMessageBox.confirm('确定从对接人库中删除？', '提示', { type: 'warning' })
  await deleteProjectContact(projectId, pc.id)
  projectContacts.value = await getProjectContacts(projectId, {})
}

const load = async () => {
  const [projRes, s, ct, pcs, tg] = await Promise.all([
    getProjects(),
    getStatuses(projectId),
    getCommTypes(projectId),
    getProjectContacts(projectId, {}),
    getTags(projectId),
  ])
  project.value = projRes.find(p => p.display_id === projectId) || null
  statuses.value = s
  commTypes.value = ct
  projectContacts.value = pcs
  tags.value = tg
}

// 状态池拖拽
const statusDragIdx = ref(-1)
const statusDragOver = ref(-1)
// 沟通类型池拖拽
const ctDragIdx = ref(-1)
const ctDragOver = ref(-1)

// 弹窗
const showDialog = ref(false)
const loading = ref(false)
const dialogType = ref('status') // 'status' | 'commType'
const editTarget = ref(null)
const form = ref({ name: '', color: '#5F5E5A', is_default: false })

const dialogTitle = computed(() => {
  const prefix = editTarget.value ? '编辑' : '新增'
  const label = dialogType.value === 'status' ? '状态' : '沟通类型'
  return prefix + label
})
onMounted(load)

// ---- 弹窗 ----
const COLOR_PALETTE = [
  '#E24B4A', '#E8833A', '#F1A43C', '#6B9F3A', '#1F9A8D',
  '#1F7EB7', '#534AB7', '#993C9D', '#D43D7A', '#854F0B',
  '#366092', '#4A8C6F', '#B87C3A', '#8B5CF6', '#EC4899',
  '#14B8A6', '#0EA5E9', '#F97316', '#84CC16', '#6366F1',
]
const _randomUnusedColor = (existingColors) => {
  const used = new Set(existingColors)
  const pool = COLOR_PALETTE.filter(c => !used.has(c))
  return pool.length ? pool[Math.floor(Math.random() * pool.length)] : COLOR_PALETTE[Math.floor(Math.random() * COLOR_PALETTE.length)]
}

const resetForm = () => {
  form.value = { name: '', color: '#5F5E5A', is_default: false }
  editTarget.value = null
}
const resetTagForm = () => {
  tagForm.value = { name: '', color: '#5F5E5A' }
  editTagRef.value = null
}
const openAddDialog = (type) => {
  dialogType.value = type
  editTarget.value = null
  const pool = type === 'status' ? statuses.value : commTypes.value
  form.value = { name: '', color: _randomUnusedColor(pool.map(i => i.color)), is_default: false }
  showDialog.value = true
}
const openEditDialog = (type, item) => {
  dialogType.value = type
  editTarget.value = item
  form.value = { name: item.name, color: item.color, is_default: item.is_default }
  showDialog.value = true
}
const submit = async () => {
  if (!form.value.name.trim()) { ElMessage.warning('名称不能为空'); return }
  loading.value = true
  try {
    const api = dialogType.value === 'status'
      ? (editTarget.value ? updateStatus(projectId, editTarget.value.id, form.value) : createStatus(projectId, form.value))
      : (editTarget.value ? updateCommType(projectId, editTarget.value.id, form.value) : createCommType(projectId, form.value))
    await api
    showDialog.value = false
    await load()
  } finally { loading.value = false }
}

// ---- CRUD 辅助 ----
const updateItem = async (type, id, data) => {
  const fn = type === 'status' ? updateStatus : updateCommType
  await fn(projectId, id, data)
}
const removeItem = async (type, item) => {
  const label = type === 'status' ? '状态' : '沟通类型'
  await ElMessageBox.confirm(`确定删除${label}「${item.name}」吗？`, '提示', { type: 'warning' })
  const fn = type === 'status' ? deleteStatus : deleteCommType
  await fn(projectId, item.id)
  await load()
}

// ---- 拖拽（状态池） ----
const onStatusDragStart = (i) => { statusDragIdx.value = i }
const onStatusDrop = async (i) => {
  statusDragOver.value = -1
  if (statusDragIdx.value < 0 || statusDragIdx.value === i) { statusDragIdx.value = -1; return }
  const arr = statuses.value
  const [moved] = arr.splice(statusDragIdx.value, 1)
  arr.splice(i, 0, moved)
  statusDragIdx.value = -1
  for (let idx = 0; idx < arr.length; idx++) {
    if (arr[idx].sort_order !== idx) {
      arr[idx].sort_order = idx
      try { await updateStatus(projectId, arr[idx].id, { sort_order: idx }) } catch {}
    }
  }
  statuses.value = [...arr]
}

// ---- 拖拽（沟通类型池） ----
const onCommTypeDrop = async (i) => {
  ctDragOver.value = -1
  if (ctDragIdx.value < 0 || ctDragIdx.value === i) { ctDragIdx.value = -1; return }
  const arr = commTypes.value
  const [moved] = arr.splice(ctDragIdx.value, 1)
  arr.splice(i, 0, moved)
  ctDragIdx.value = -1
  for (let idx = 0; idx < arr.length; idx++) {
    if (arr[idx].sort_order !== idx) {
      arr[idx].sort_order = idx
      try { await updateCommType(projectId, arr[idx].id, { sort_order: idx }) } catch {}
    }
  }
  commTypes.value = [...arr]
}

// ---- 标签池 CRUD ----
const openTagDialog = () => {
  editTagRef.value = null
  tagForm.value = { name: '', color: _randomUnusedColor(tags.value.map(i => i.color)) }
  showTagDialog.value = true
}
const openEditTagDialog = (t) => {
  editTagRef.value = t
  tagForm.value = { name: t.name, color: t.color }
  showTagDialog.value = true
}
const submitTag = async () => {
  if (!tagForm.value.name.trim()) { ElMessage.warning('名称不能为空'); return }
  tagLoading.value = true
  try {
    if (editTagRef.value) {
      await updateTag(projectId, editTagRef.value.id, tagForm.value)
    } else {
      await createTag(projectId, tagForm.value)
    }
    showTagDialog.value = false
    tags.value = await getTags(projectId)
  } finally { tagLoading.value = false }
}
const updateTagItem = async (id, data) => {
  await updateTag(projectId, id, data)
}
const removeTag = async (t) => {
  await ElMessageBox.confirm(`确定删除标签「${t.name}」吗？同时会移除所有任务上的该标签。`, '提示', { type: 'warning' })
  await deleteTag(projectId, t.id)
  tags.value = await getTags(projectId)
}

// ---- 拖拽（标签池） ----
const onTagDragStart = (i) => { tagDragIdx.value = i }
const onTagDrop = async (i) => {
  tagDragOver.value = -1
  if (tagDragIdx.value < 0 || tagDragIdx.value === i) { tagDragIdx.value = -1; return }
  const arr = tags.value
  const [moved] = arr.splice(tagDragIdx.value, 1)
  arr.splice(i, 0, moved)
  tagDragIdx.value = -1
  for (let idx = 0; idx < arr.length; idx++) {
    if (arr[idx].sort_order !== idx) {
      arr[idx].sort_order = idx
      try { await updateTag(projectId, arr[idx].id, { sort_order: idx }) } catch {}
    }
  }
  tags.value = [...arr]
}
</script>

<style scoped>
.tab-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; font-size: 13px; color: #888; }
.list { display: flex; flex-direction: column; gap: 8px; }
.list-item { background: #fff; border: 1px solid #e8e8e4; border-radius: 8px; padding: 12px 16px; display: flex; align-items: center; gap: 12px; transition: border-color .15s, box-shadow .15s; }
.list-item[draggable="true"] { cursor: grab; }
.list-item[draggable="true"]:active { cursor: grabbing; }
.list-item.drag-over { border-color: #534ab7; box-shadow: 0 0 0 2px rgba(83,74,183,.15); }
.dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
.item-name { font-size: 14px; font-weight: 500; min-width: 80px; }
.drag-handle { color: #bbb; cursor: grab; display: flex; align-items: center; }
.drag-handle:active { cursor: grabbing; }
.avatar { width: 32px; height: 32px; border-radius: 50%; background: #eeedfe; color: #534ab7; display: flex; align-items: center; justify-content: center; font-weight: 500; font-size: 13px; flex-shrink: 0; }
.proj-info-bar { padding: 10px 14px; background: #f9f9f8; border-radius: 8px; border: 1px solid #e8e8e4; margin-bottom: 20px; display: flex; align-items: center; }
</style>
