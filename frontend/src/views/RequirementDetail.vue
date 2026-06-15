<template>
  <div>
    <!-- 面包屑 -->
    <el-breadcrumb separator="/" style="margin-bottom:20px">
      <el-breadcrumb-item :to="{ path: '/projects' }">项目列表</el-breadcrumb-item>
      <el-breadcrumb-item :to="{ path: `/projects/${projectId}/requirements` }">需求列表</el-breadcrumb-item>
      <el-breadcrumb-item>{{ req?.title || '需求详情' }}</el-breadcrumb-item>
    </el-breadcrumb>

    <!-- 加载状态 -->
    <div v-if="loading" style="display:flex;justify-content:center;padding:100px 0">
      <div class="loading-spinner" />
    </div>

    <!-- 错误状态 -->
    <div v-if="!loading && !req" style="display:flex;justify-content:center;padding:80px 0">
      <el-empty description="需求加载失败或不存在">
        <el-button type="primary" @click="load(Number(route.params.requirementId))">重新加载</el-button>
      </el-empty>
    </div>

    <!-- 内容 -->
    <div v-if="req" class="page-body">
      <!-- 左侧主内容 -->
      <div class="body-main">
        <!-- 标题行 -->
        <div class="title-row">
          <div class="title-left">
            <el-button @click="router.back()" class="back-btn">
              <el-icon><ArrowLeft /></el-icon> 返回
            </el-button>
            <h1 class="page-title">{{ req.title }}</h1>
            <el-button size="small" text @click="startEditTitle" class="title-edit-btn">
              <el-icon><Edit /></el-icon>
            </el-button>
          </div>
          <div style="display:flex;gap:6px">
            <span v-if="saveStatus" class="save-indicator" :class="'save--' + saveStatus">
              {{ saveStatus === 'saving' ? '保存中…' : saveStatus === 'saved' ? '已保存' : '保存失败' }}
            </span>
            <el-button
              v-if="isEditing"
              size="small" type="warning" plain
              @click="exitEdit"
            >
              <el-icon><Close /></el-icon> 退出编辑
            </el-button>
            <el-button
              v-else
              size="small" type="primary" plain
              @click="enterEdit"
            >
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
            <el-button size="small" type="primary" @click="doSaveDesc" :loading="saveStatus === 'saving'">
              <el-icon><Check /></el-icon> 保存描述
            </el-button>
          </div>
        </div>

        <!-- 显示ID -->
        <p v-if="req.display_id" class="req-display-id">{{ req.display_id }}</p>

        <!-- 富文本编辑器 -->
        <div class="section-title">
          <el-icon><EditPen /></el-icon> 详细描述
          <span style="flex:1" />
          <template v-if="isEditing">
            <span style="font-size:12px;color:#999;margin-right:4px">引用块</span>
            <span
              v-for="c in bqPresets"
              :key="c"
              class="bq-color-dot"
              :class="{ active: bqColor === c }"
              :style="{ background: c }"
              @click="setBqColor(c)"
            />
          </template>
        </div>
        <div class="editor-wrapper" :class="{ 'editor-readonly': !isEditing }">
          <Toolbar
            v-show="isEditing"
            :editor="editorRef"
            :defaultConfig="toolbarConfig"
            mode="simple"
            class="editor-toolbar"
          />
          <Editor
            v-model="descDraft"
            :defaultConfig="editorConfig"
            mode="default"
            class="editor-body"
            @onCreated="onEditorCreated"
            @onChange="onEditorChange"
          />
        </div>
      </div>

      <!-- 右侧信息栏 -->
      <div class="detail-side">
        <div class="side-card side-card-fields">
          <!-- 状态 -->
          <div class="side-field">
            <span class="side-field-label">状态</span>
            <el-select v-model="req.status" placeholder="设置状态" size="small" style="flex:1" @change="quickUpdateStatus">
              <el-option
                v-for="s in statusPools"
                :key="s.name"
                :label="s.name"
                :value="s.name"
              >
                <span :style="{ color: s.color, marginRight: '6px' }">●</span>{{ s.name }}
              </el-option>
            </el-select>
          </div>

          <!-- 优先级 -->
          <div class="side-field">
            <span class="side-field-label">优先级</span>
            <el-select v-model="req.priority" placeholder="选择优先级" size="small" style="flex:1" @change="quickUpdatePriority">
              <el-option
                v-for="p in priorityPools"
                :key="p.name"
                :label="p.name"
                :value="p.name"
              >
                <span :style="{ color: p.color, marginRight: '6px' }">●</span>{{ p.name }}
              </el-option>
            </el-select>
          </div>

          <!-- 自定义字段 -->
          <div v-if="customFields.length" class="side-field-section">
            <div class="side-field-section-title">自定义字段</div>
            <div v-for="f in customFields" :key="f.id" class="side-field">
              <span class="side-field-label" :title="f.field_name">{{ f.field_name }}</span>
              <span class="side-field-value">{{ getFieldValue(f.id) || '—' }}</span>
            </div>
          </div>
        </div>

        <!-- 时间信息 -->
        <div class="side-card">
          <div class="side-info-row">
            <span class="side-info-label">创建时间</span>
            <span class="side-info-value">{{ formatTime(req.created_at) }}</span>
          </div>
          <div class="side-info-row">
            <span class="side-info-label">更新时间</span>
            <span class="side-info-value">{{ formatTime(req.updated_at) }}</span>
          </div>
        </div>

        <!-- 操作 -->
        <div class="side-card">
          <el-button type="danger" size="small" style="width:100%" @click="removeReq">
            <el-icon><Delete /></el-icon> 删除需求
          </el-button>
        </div>
      </div>
    </div>

    <!-- 标题编辑对话框 -->
    <el-dialog v-model="editTitleDialog" title="编辑标题" width="500px" :close-on-click-modal="false">
      <el-input v-model="editTitleVal" autofocus @keyup.enter="doSaveTitle" />
      <template #footer>
        <el-button @click="editTitleDialog = false">取消</el-button>
        <el-button type="primary" @click="doSaveTitle">保存</el-button>
      </template>
    </el-dialog>

    <!-- 退出编辑确认对话框 -->
    <el-dialog v-model="exitConfirmVisible" title="未保存的改动" width="420px" :close-on-click-modal="false" :show-close="false">
      <p style="margin:0;color:#555">当前修改未保存，是否保存？</p>
      <template #footer>
        <el-button @click="onExitChoice('continue')">继续编辑</el-button>
        <el-button @click="onExitChoice('discard')" type="danger" plain>不保存退出</el-button>
        <el-button @click="onExitChoice('save')" type="primary">保存退出</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, shallowRef, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import '@wangeditor/editor/dist/css/style.css'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import {
  getRequirement, updateRequirement, deleteRequirement, deleteRequirementImage,
  getReqCustomFields, getReqStatusPools, getReqPriorityPools,
} from '../api/index.js'

const route = useRoute()
const router = useRouter()
const projectId = route.params.projectId

const loading = ref(true)
const req = ref(null)
const customFields = ref([])
const statusPools = ref([])
const priorityPools = ref([])
const descDraft = ref('')
const origImgFilenames = new Set()  // 原始描述中的图片文件名
const saveStatus = ref('')  // '' | 'saving' | 'saved' | 'error'

const editTitleDialog = ref(false)
const editTitleVal = ref('')
const exitConfirmVisible = ref(false)
let exitResolve = null  // 退出编辑的 Promise resolve

// ── 富文本编辑器 ──
const editorRef = shallowRef()
const isEditing = ref(false)
const hasUnsaved = ref(false)
const bqPresets = ['#f8f8f8', '#e8f4fd', '#e8f8e8', '#fef9e7', '#fde8e8']
const bqColor = ref('#f8f8f8')

const toolbarConfig = {
  toolbarKeys: [
    'undo', 'redo',
    '|',
    'bold', 'italic', 'underline', 'through', 'code',
    '|',
    'color', 'bgColor',
    '|',
    'bulletedList', 'numberedList', 'blockquote',
    '|',
    'divider',
    '|',
    'clearStyle',
    '|',
    'uploadImage', 'insertLink',
  ],
}

const onEditorCreated = (editor) => {
  editorRef.value = editor
  // 非编辑状态禁止聚焦
  editor.on('focus', () => {
    if (!isEditing.value) editor.blur()
  })
  editor.blur()
  // 初始化引用块颜色
  nextTick(() => setBqColor(bqColor.value))
}

const onEditorChange = () => {
  if (isEditing.value) hasUnsaved.value = true
}

const editorConfig = {
  placeholder: '开始编写需求文档…',
  hoverbarKeys: {
    text: { menuKeys: [] },
    link: { menuKeys: [] },
    image: { menuKeys: [] },
    pre: { menuKeys: [] },
    table: { menuKeys: [] },
    divider: { menuKeys: [] },
  },
  MENU_CONF: {
    uploadImage: {
      async customUpload(file, insertFn) {
        if (!file) return
        const fd = new FormData()
        fd.append('file', file)
        try {
          const r = await (await fetch(`/api/projects/${projectId}/requirements/${req.value.id}/images`, { method: 'POST', body: fd })).json()
          if (r.url) insertFn(r.url)
        } catch { ElMessage.error('图片上传失败') }
      },
    },
  },
}

const enterEdit = () => {
  hasUnsaved.value = false
  isEditing.value = true
}

const exitEdit = async () => {
  if (hasUnsaved.value) {
    const choice = await new Promise((resolve) => {
      exitResolve = resolve
      exitConfirmVisible.value = true
    })
    if (choice === 'continue') return
    if (choice === 'save') {
      await doSaveDesc()
    } else {
      // 不保存：重置内容为上次保存的版本
      descDraft.value = req.value.description || ''
      hasUnsaved.value = false
    }
  }
  doExitEdit()
}

const onExitChoice = (choice) => {
  exitConfirmVisible.value = false
  exitResolve?.(choice)
}

const setBqColor = (color) => {
  bqColor.value = color
  const wrapper = document.querySelector('.editor-wrapper')
  if (wrapper) {
    wrapper.style.setProperty('--bq-bg', color)
    wrapper.style.setProperty('--bq-border', darken(color, 0.15))
    wrapper.style.setProperty('--bq-text', isLight(color) ? '#555' : '#eee')
  }
}

// 简易颜色工具
const isLight = (hex) => {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return (r * 299 + g * 587 + b * 114) / 1000 > 160
}
const darken = (hex, amount) => {
  const clamp = (v) => Math.max(0, Math.min(255, v))
  const r = clamp(parseInt(hex.slice(1, 3), 16) * (1 - amount))
  const g = clamp(parseInt(hex.slice(3, 5), 16) * (1 - amount))
  const b = clamp(parseInt(hex.slice(5, 7), 16) * (1 - amount))
  return `#${Math.round(r).toString(16).padStart(2, '0')}${Math.round(g).toString(16).padStart(2, '0')}${Math.round(b).toString(16).padStart(2, '0')}`
}

const doExitEdit = () => {
  isEditing.value = false
  editorRef.value?.blur()
}

onBeforeUnmount(() => {
  if (editorRef.value) editorRef.value.destroy()
})

// ── 数据加载 ──
const load = async (id) => {
  if (!id) id = Number(route.params.requirementId)
  loading.value = true
  req.value = null
  try {
    const [reqRes, cfs, sp, pp] = await Promise.all([
      getRequirement(projectId, id),
      getReqCustomFields(projectId, { show_inactive: false }),
      getReqStatusPools(projectId, { show_inactive: true }),
      getReqPriorityPools(projectId, { show_inactive: true }),
    ])
    req.value = reqRes
    customFields.value = cfs || []
    statusPools.value = sp || []
    priorityPools.value = pp || []
    descDraft.value = reqRes.description || ''
    // 记录原始图片文件名
    origImgFilenames.clear()
    for (const fn of extractImgFilenames(reqRes.description)) {
      origImgFilenames.add(fn)
    }
  } catch {
    ElMessage.error('加载需求失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  const id = Number(route.params.requirementId)
  if (id) load(id)
})

// ── 标题编辑 ──
const startEditTitle = () => {
  editTitleVal.value = req.value.title
  editTitleDialog.value = true
}
const doSaveTitle = async () => {
  const t = editTitleVal.value?.trim()
  if (!t) return
  try {
    await updateRequirement(projectId, req.value.id, { title: t })
    req.value.title = t
    editTitleDialog.value = false
    ElMessage.success('标题已更新')
  } catch {
    ElMessage.error('标题更新失败')
  }
}

// ── 描述保存 ──
const doSaveDesc = async () => {
  if (!req.value) return
  saveStatus.value = 'saving'
  try {
    await updateRequirement(projectId, req.value.id, { description: descDraft.value })
    req.value.description = descDraft.value
    hasUnsaved.value = false

    // 清理已删除的图片文件
    const newFilenames = new Set(extractImgFilenames(descDraft.value))
    for (const fn of origImgFilenames) {
      if (!newFilenames.has(fn)) {
        deleteRequirementImage(projectId, req.value.id, fn).catch(() => {})
      }
    }
    origImgFilenames.clear()
    for (const fn of newFilenames) origImgFilenames.add(fn)

    saveStatus.value = 'saved'
    setTimeout(() => { if (saveStatus.value === 'saved') saveStatus.value = '' }, 1500)
  } catch {
    saveStatus.value = 'error'
    setTimeout(() => { saveStatus.value = '' }, 3000)
  }
}

// ── 右侧栏快速编辑 ──
const quickUpdateStatus = async (val) => {
  try {
    await updateRequirement(projectId, req.value.id, { status: val })
    ElMessage.success('状态已更新')
  } catch {
    ElMessage.error('状态更新失败')
  }
}

const quickUpdatePriority = async (val) => {
  try {
    await updateRequirement(projectId, req.value.id, { priority: val })
    ElMessage.success('优先级已更新')
  } catch {
    ElMessage.error('优先级更新失败')
  }
}

// ── 自定义字段 ──
const getFieldValue = (fid) => {
  return req.value?.custom_values?.find(v => v.field_id === fid)?.value || ''
}

// ── 删除 ──
const removeReq = async () => {
  await ElMessageBox.confirm(
    `确定删除需求「${req.value.title}」吗？此操作不可恢复！`,
    '警告',
    { type: 'warning' }
  )
  await deleteRequirement(projectId, req.value.id)
  ElMessage.success('已删除')
  router.push(`/projects/${projectId}/requirements`)
}

// ── 工具函数 ──
const formatTime = (t) => t ? dayjs(t).format('YYYY-MM-DD HH:mm') : '—'

/** 从 HTML 描述中提取已上传图片的文件名 */
const extractImgFilenames = (html) => {
  if (!html) return []
  const names = []
  const re = /\/uploads\/[^\/]+\/requirements\/[^\/]+\/images\/([^"\s)]+)/
  let m
  const g = html.matchAll(new RegExp(re.source, 'g'))
  for (m of g) names.push(m[1])
  return names
}
</script>

<style scoped>
/* ── 加载 ── */
.loading-spinner {
  width: 32px; height: 32px;
  border: 3px solid #e0e0e0; border-top-color: #534ab7;
  border-radius: 50%; animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── 页面布局 ── */
.page-body { display: flex; gap: 24px; align-items: flex-start; }
.body-main { flex: 1; min-width: 0; }
.detail-side { width: 260px; flex-shrink: 0; display: flex; flex-direction: column; gap: 12px; }

/* ── 标题行 ── */
.title-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.title-left { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
.title-left .back-btn { flex-shrink: 0; }
.title-left .back-btn:hover { color: #534ab7; border-color: #d0cff0; background: #f5f4ff; }
.page-title { font-size: 22px; font-weight: 600; color: #222; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.title-edit-btn { flex-shrink: 0; color: #999; }
.title-edit-btn:hover { color: #409eff; }
.req-display-id { font-size: 12px; color: #aaa; margin: 0 0 16px 0; }

/* ── 描述编辑区 ── */
.section-title {
  font-size: 14px; font-weight: 500;
  display: flex; align-items: center; gap: 6px;
  margin-bottom: 10px; margin-top: 20px; color: #444;
}
.bq-color-dot {
  width: 18px; height: 18px; border-radius: 50%;
  border: 2px solid transparent; cursor: pointer;
  box-shadow: 0 1px 3px rgba(0,0,0,0.12);
  transition: border-color 0.15s, transform 0.15s;
}
.bq-color-dot:hover { transform: scale(1.15); }
.bq-color-dot.active { border-color: #534ab7; }

/* 富文本编辑器外层 */
.editor-wrapper {
  border: 1px solid #d0cff0; border-radius: 8px; overflow: hidden;
  box-shadow: 0 2px 16px rgba(83,74,183,0.08);
  background: #fff;
}
.editor-readonly :deep(.w-e-text-container) { pointer-events: none; user-select: none; }
.editor-toolbar {
  border-bottom: 1px solid #e8e8e8;
  background: #fafafa;
}
.editor-body {
  min-height: 420px;
}
.editor-body :deep(.w-e-text-container) {
  min-height: 420px !important; padding: 20px 32px !important;
}
.editor-body :deep(.w-e-text-placeholder) { left: 32px; top: 20px; }
/* 正文：单倍行距，段前段后0，统一字号14px */
.editor-body :deep(.w-e-text-container [data-slate-editor]) { padding: 0 !important; font-size: 14px; }
.editor-body :deep(.w-e-text-container [data-slate-editor] p) { line-height: 1.6; margin: 0; }
/* 引用块样式（背景/边框可通过颜色选择器修改） */
.editor-body :deep(.w-e-text-container [data-slate-editor] blockquote) {
  line-height: 1.6;
  margin: 0;
  padding: 8px 16px;
  border-left: 3px solid var(--bq-border, #ccc);
  background: var(--bq-bg, #f8f8f8);
  color: var(--bq-text, #555);
}
/* 注释/行内代码样式 */
.editor-body :deep(.w-e-text-container [data-slate-editor] code) {
  font-size: 13px;
  color: #888;
  background: #f5f5f5;
  border-radius: 3px;
  padding: 2px 6px;
  font-family: inherit;
}

/* ── 保存状态 ── */
.save-indicator { font-size: 12px; padding: 1px 10px; border-radius: 10px; line-height: 22px; }
.save--saving { color: #999; }
.save--saved { color: #519839; background: #edf7e6; }
.save--error { color: #d32f2f; background: #fdebea; }

/* ── 右侧栏 ── */
.side-card { background: #fff; border-radius: 8px; border: 1px solid #e8e8e4; padding: 14px 16px; }
.side-card-fields { padding: 8px 14px; }
.side-field { display: flex; align-items: center; gap: 8px; padding: 7px 0; }
.side-field + .side-field { border-top: 1px solid #f0f0ee; }
.side-field-label {
  font-size: 13px; color: #555; width: 56px; flex-shrink: 0;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.side-field-value { font-size: 13px; color: #333; flex: 1; min-width: 0; word-break: break-all; }
.side-field-section { margin-top: 4px; }
.side-field-section-title {
  font-size: 12px; font-weight: 500; color: #aaa;
  padding: 6px 0 2px 0; border-top: 1px solid #f0f0ee;
}

.side-info-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; }
.side-info-row + .side-info-row { border-top: 1px solid #f0f0ee; }
.side-info-label { font-size: 13px; color: #888; }
.side-info-value { font-size: 13px; color: #555; }
</style>
