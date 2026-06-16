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
import { ref, shallowRef, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import '@wangeditor/editor/dist/css/style.css'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import { Boot } from '@wangeditor/editor'
import {
  getRequirement, updateRequirement, deleteRequirement, deleteRequirementImage,
  getReqCustomFields, getReqStatusPools, getReqPriorityPools,
} from '../api/index.js'

// ── 引用块颜色选择器 ──
const BQ_PRESETS = [
  { value: '#f8f8f8', label: '灰', border: '#ccc' },
  { value: '#e8f4fd', label: '蓝', border: '#9fc5e8' },
  { value: '#e8f8e8', label: '绿', border: '#9fc89f' },
  { value: '#fef9e7', label: '黄', border: '#e6d88a' },
  { value: '#fde8e8', label: '红', border: '#e89f9f' },
]

/** 从 DOM 节点向上查找最近的 blockquote */
const findParentBlockquote = (startEl) => {
  let el = startEl
  while (el) {
    if (el.nodeName === 'BLOCKQUOTE') return el
    el = el.parentElement
  }
  return null
}

/**
 * 在编辑器内查找当前光标所在的 blockquote DOM（多路径 fallback）
 */
const findCurrentBlockquote = () => {
  try {
    const sel = window.getSelection()
    if (sel && sel.rangeCount > 0 && sel.anchorNode) {
      const bq = findParentBlockquote(sel.anchorNode)
      if (bq) return bq
    }
  } catch {}
  if (editorRef.value) {
    try {
      const container =
        editorRef.value.getEditableContainer?.() ||
        document.querySelector('.w-e-text-container [data-slate-editor]') ||
        document.querySelector('.w-e-text-container')
      if (container) {
        const allBq = container.querySelectorAll('blockquote')
        if (allBq.length === 1) return allBq[0]
        for (let i = allBq.length - 1; i >= 0; i--) {
          if (allBq[i].getAttribute('data-bq-active') === 'true') return allBq[i]
        }
      }
    } catch {}
  }
  return null
}

/** 最后一次鼠标点击落入的 blockquote DOM */
let lastTouchedBlockquote = null

// ── 引用颜色选择器菜单 ──

class BqColorMenu {
  constructor() {
    this.title = '引用颜色'
    this.iconSvg = '<svg viewBox="0 0 1024 1024"><path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z"/></svg>'
    this.tag = 'select'
    this.width = 48
  }
  getOptions() { return BQ_PRESETS.map(c => ({ value: c.value, text: c.label })) }
  getValue() { return '' }
  isActive() { return false }
  isDisabled() { return false }
  exec(editor, color) {
    // 定位目标 blockquote DOM 元素
    let bqEl = findCurrentBlockquote()
    if (!bqEl) bqEl = lastTouchedBlockquote
    if (!bqEl || bqEl.nodeName !== 'BLOCKQUOTE') {
      console.warn('[BqColor] 未找到目标引用块，请先将光标放入引用块内再选择颜色')
      return
    }

    // 只设置 data-bq-color 属性；视觉颜色由 CSS 属性选择器驱动
    bqEl.setAttribute('data-bq-color', color)

    hasUnsaved.value = true
  }
}

// 用 try/catch 保护 registerMenu：首次注册成功，后续组件复用时不因
// "Duplicated key" 异常导致整个 setup() 崩溃（watch/ref 等全部无法初始化）
try {
  Boot.registerMenu({
    key: 'bqColorSelect',
    factory() { return new BqColorMenu() }
  })
} catch (e) {
  // 预期：第二次注册时抛 "Duplicated key" — 忽略即可，无需重新注册
  if (e.message && !e.message.includes('Duplicated key')) throw e
}

const route = useRoute()
const router = useRouter()
// 响应式 projectId，确保路由切换时正确更新（修复第二次进入详情页时内容不加载的问题）
const projectId = computed(() => route.params.projectId)

const loading = ref(false)
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

const toolbarConfig = {
  toolbarKeys: [
    'undo', 'redo',
    '|',
    'bold', 'italic', 'underline', 'through', 'code',
    '|',
    'color', 'bgColor',
    '|',
    'bulletedList', 'numberedList', 'blockquote', 'bqColorSelect',
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

  // 延迟绑定 DOM 事件，追踪当前交互的 blockquote
  setTimeout(() => {
    try {
      const container = editor.getEditableContainer?.() ||
        document.querySelector('.w-e-text-container [data-slate-editor]') ||
        document.querySelector('.w-e-text-container')
      if (container) {
        // mousedown：用户点击编辑区时立即记录目标 blockquote（此时选区还在）
        container.addEventListener('mousedown', handleEditorMouseDown)
        // selectionchange：光标移动后更新
        document.addEventListener('selectionchange', handleSelectionChange)
      }
    } catch {}
  }, 300)
  // 恢复引用块颜色：立刻执行，无需等 300ms（Editor DOM 已就绪），避免先闪灰色再变色的延迟感
  restoreBqColors()
}

/** mousedown 时记录点击位置所在的 blockquote */
const handleEditorMouseDown = (e) => {
  const bq = findParentBlockquote(e.target)
  if (bq) {
    lastTouchedBlockquote = bq
    bq.setAttribute('data-bq-active', 'true')
    // 清除其他 blockquote 的 active 标记
    const allBq = bq.parentElement?.querySelectorAll('blockquote')
    if (allBq) { for (const el of allBq) { if (el !== bq) el.removeAttribute('data-bq-active') } }
  } else {
    lastTouchedBlockquote = null
  }
}

/** selectionchange 时同步更新 lastTouchedBlockquote */
const handleSelectionChange = () => {
  try {
    const sel = window.getSelection()
    if (!sel || !sel.anchorNode) return
    const bq = findParentBlockquote(sel.anchorNode)
    if (bq) {
      lastTouchedBlockquote = bq
      bq.setAttribute('data-bq-active', 'true')
      const allBq = bq.parentElement?.querySelectorAll('blockquote')
      if (allBq) { for (const el of allBq) { if (el !== bq) el.removeAttribute('data-bq-active') } }
    }
  } catch {}
}

const onEditorChange = (editor) => {
  if (isEditing.value) {
    hasUnsaved.value = true
  }
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
          const r = await (await fetch(`/api/projects/${projectId.value}/requirements/${req.value.id}/images`, { method: 'POST', body: fd })).json()
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
      // 恢复引用块颜色（重设 HTML 触发 Slate 反序列化会剥离内联样式）
      setTimeout(() => restoreBqColors(), 400)
    }
  }
  doExitEdit()
}

const onExitChoice = (choice) => {
  exitConfirmVisible.value = false
  exitResolve?.(choice)
}

const doExitEdit = () => {
  isEditing.value = false
  editorRef.value?.blur()
}

onBeforeUnmount(() => {
  if (editorRef.value) {
    // 清理事件监听器
    try {
      const container = editorRef.value.getEditableContainer?.() ||
        document.querySelector('.w-e-text-container [data-slate-editor]') ||
        document.querySelector('.w-e-text-container')
      if (container) container.removeEventListener('mousedown', handleEditorMouseDown)
    } catch {}
    document.removeEventListener('selectionchange', handleSelectionChange)
    editorRef.value.destroy()
  }
  lastTouchedBlockquote = null
})

// ── 数据加载 ──
const load = async (id) => {
  loading.value = true
  req.value = null
  try {
    const rId = id || Number(route.params.requirementId)
    const [reqRes, cfs, sp, pp] = await Promise.all([
      getRequirement(projectId.value, rId),
      getReqCustomFields(projectId.value, { show_inactive: false }),
      getReqStatusPools(projectId.value, { show_inactive: true }),
      getReqPriorityPools(projectId.value, { show_inactive: true }),
    ])
    customFields.value = cfs || []
    statusPools.value = sp || []
    priorityPools.value = pp || []
    const desc = reqRes.description || ''
    // 先设 descDraft，再设 req，确保编辑器创建时 v-model 已是目标内容
    descDraft.value = desc
    req.value = reqRes
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

// 唯一入口：监听路由参数，immediate 覆盖首次加载 + 后续同组件跳转
watch(() => route.params.requirementId, (newId) => {
  if (newId) load(Number(newId))
}, { immediate: true })

// 防御性兜底：如果 watcher immediate 未触发（第二次进入同路由时可能发生），
// 在 onMounted 中补加载。通过 req/loading 状态避免重复请求。
onMounted(() => {
  const rId = Number(route.params.requirementId)
  if (rId && !req.value && !loading.value) {
    load(rId)
  }
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
    await updateRequirement(projectId.value, req.value.id, { title: t })
    req.value.title = t
    editTitleDialog.value = false
    ElMessage.success('标题已更新')
  } catch {
    ElMessage.error('标题更新失败')
  }
}

// ── 描述保存 ──

/**
 * 保存前注入引用块颜色（data-bq-color 属性 → CSS 属性选择器驱动颜色）。
 *
 * 从编辑器 DOM 读取 data-bq-color，按文本锚点匹配写入待保存 HTML 的对应 blockquote。
 */
const injectBqColorsToHtml = (html) => {
  if (!editorRef.value) return html

  // 1. 获取实时编辑器容器中的所有 blockquote
  let liveContainer
  try {
    liveContainer =
      editorRef.value.getEditableContainer?.() ||
      document.querySelector('.w-e-text-container [data-slate-editor]') ||
      document.querySelector('.w-e-text-container')
  } catch { return html }
  if (!liveContainer) return html

  const allLiveBqs = Array.from(liveContainer.querySelectorAll('blockquote'))
  if (!allLiveBqs.length) return html

  // 2. 收集有色 blockquote：{ text, color }
  const coloredItems = []
  for (const bq of allLiveBqs) {
    const color = bq.getAttribute('data-bq-color')
    if (!color) continue
    const text = (bq.textContent || '').replace(/\s+/g, ' ').trim()
    coloredItems.push({ text, color })
  }
  if (!coloredItems.length) return html

  // 3. 将待保存 HTML 解析为临时 DOM
  const tmpDiv = document.createElement('div')
  tmpDiv.innerHTML = html
  const parsedBqs = Array.from(tmpDiv.querySelectorAll('blockquote'))
  if (!parsedBqs.length) return html

  // 4. 按文本内容锚点匹配，写入 data-bq-color
  for (const item of coloredItems) {
    let target = null
    for (const bq of parsedBqs) {
      if (bq.hasAttribute('data-bq-matched')) continue
      const bqText = (bq.textContent || '').replace(/\s+/g, ' ').trim()
      if (bqText === item.text) { target = bq; break }
    }
    if (!target) {
      for (const bq of parsedBqs) {
        if (bq.hasAttribute('data-bq-matched')) continue
        const bqText = (bq.textContent || '').replace(/\s+/g, ' ').trim()
        if (item.text && bqText && (bqText.includes(item.text) || item.text.includes(bqText))) {
          target = bq; break
        }
      }
    }
    if (target) {
      target.setAttribute('data-bq-matched', '1')
      target.setAttribute('data-bq-color', item.color)
    }
  }

  // 5. 清理临时标记
  for (const bq of parsedBqs) bq.removeAttribute('data-bq-matched')

  return tmpDiv.innerHTML
}

/**
 * 从已保存 HTML 中提取 data-bq-color 并恢复到编辑器 DOM。
 * 页面加载/内容重置后调用。CSS 属性选择器会处理视觉渲染。
 */
const restoreBqColors = () => {
  if (!editorRef.value || !req.value?.description) return

  // 1. 解析已保存 HTML，提取 data-bq-color
  const tmpDiv = document.createElement('div')
  tmpDiv.innerHTML = req.value.description
  const rawBqs = Array.from(tmpDiv.querySelectorAll('blockquote'))
  const colorMap = []
  for (const bq of rawBqs) {
    const color = bq.getAttribute('data-bq-color')
    if (!color) continue
    const text = (bq.textContent || '').replace(/\s+/g, ' ').trim()
    colorMap.push({ text, color })
  }
  if (!colorMap.length) return

  // 2. 在编辑器 DOM 中查找匹配的 blockquote，设置 data-bq-color
  const container =
    editorRef.value.getEditableContainer?.() ||
    document.querySelector('.w-e-text-container [data-slate-editor]') ||
    document.querySelector('.w-e-text-container')
  if (!container) return

  const editorBqs = container.querySelectorAll('blockquote')
  const used = new Set()

  for (const item of colorMap) {
    for (const bq of editorBqs) {
      if (used.has(bq)) continue
      const bqText = (bq.textContent || '').replace(/\s+/g, ' ').trim()
      if (bqText === item.text ||
          (item.text && bqText && (bqText.includes(item.text) || item.text.includes(bqText)))) {
        bq.setAttribute('data-bq-color', item.color)
        used.add(bq)
        break
      }
    }
  }
}

const doSaveDesc = async () => {
  if (!req.value) return
  saveStatus.value = 'saving'
  try {
    // 将 DOM 中的引用块颜色注入到 HTML 字符串中再保存
    const finalHtml = injectBqColorsToHtml(descDraft.value)
    await updateRequirement(projectId.value, req.value.id, { description: finalHtml })
    req.value.description = finalHtml
    // 不再更新 descDraft，避免触发 WangEditor 重新渲染导致
    // 内联样式（引用块颜色）被 Slate 反序列化时剥离
    hasUnsaved.value = false

    // 清理已删除的图片文件
    const newFilenames = new Set(extractImgFilenames(descDraft.value))
    for (const fn of origImgFilenames) {
      if (!newFilenames.has(fn)) {
        deleteRequirementImage(projectId.value, req.value.id, fn).catch(() => {})
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
    await updateRequirement(projectId.value, req.value.id, { status: val })
    ElMessage.success('状态已更新')
  } catch {
    ElMessage.error('状态更新失败')
  }
}

const quickUpdatePriority = async (val) => {
  try {
    await updateRequirement(projectId.value, req.value.id, { priority: val })
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
  await deleteRequirement(projectId.value, req.value.id)
  ElMessage.success('已删除')
  router.push(`/projects/${projectId.value}/requirements`)
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
/* 引用块基础样式 + 按 data-bq-color 属性分色（CSS 属性选择器驱动，无 JS 操作内联样式） */
.editor-body :deep(.w-e-text-container [data-slate-editor] blockquote) {
  line-height: 1.6;
  margin: 0;
  padding: 8px 16px;
  border-left: 3px solid #ccc;
  background: #f8f8f8;
  color: #555;
}
.editor-body :deep(.w-e-text-container [data-slate-editor] blockquote[data-bq-color="#e8f4fd"]) {
  background: #e8f4fd;
  border-left-color: #9fc5e8;
  color: #555;
}
.editor-body :deep(.w-e-text-container [data-slate-editor] blockquote[data-bq-color="#e8f8e8"]) {
  background: #e8f8e8;
  border-left-color: #9fc89f;
  color: #555;
}
.editor-body :deep(.w-e-text-container [data-slate-editor] blockquote[data-bq-color="#fef9e7"]) {
  background: #fef9e7;
  border-left-color: #e6d88a;
  color: #555;
}
.editor-body :deep(.w-e-text-container [data-slate-editor] blockquote[data-bq-color="#fde8e8"]) {
  background: #fde8e8;
  border-left-color: #e89f9f;
  color: #555;
}
/* 灰色引用 = 默认值，无需额外规则 */
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
