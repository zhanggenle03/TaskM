<template>
  <el-dialog v-model="visible" width="80%" top="5vh" destroy-on-close append-to-body
    :close-on-click-modal="false" :close-on-press-escape="false" :show-close="false">
    <template #header>
      <div class="apd-header">
        <span class="apd-title">{{ title }}</span>
        <span v-if="list.length > 1" class="apd-counter">{{ index + 1 }} / {{ list.length }}</span>
        <span class="apd-header-actions">
          <template v-if="!editSession">
            <!-- 编辑：复制出带原文件名的副本打开，编辑期间锁死原件 -->
            <el-button v-if="canOpenInApp" size="small" @click="startEdit">
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
          </template>
          <template v-else>
            <el-button size="small" @click="discardEdit">放弃修改</el-button>
            <el-button size="small" type="primary" @click="commitEdit">保存回系统</el-button>
          </template>
        </span>
      </div>
    </template>

    <template v-if="!editSession">
      <!-- 图片预览（滚轮缩放 + 拖拽） -->
      <div v-if="isImage" v-loading="loading" element-loading-text="加载中…" class="apd-img-wrap" @wheel.prevent="onImgWheel">
        <div class="apd-img-container">
          <img :src="src" class="apd-img" draggable="false"
            :style="{
              transform: `translate(${imgState.x}px, ${imgState.y}px) scale(${imgState.scale})`,
              transformOrigin: '0 0',
              cursor: isDragging ? 'grabbing' : imgState.scale !== 1 ? 'grab' : 'default'
            }"
            @load="onLoaded"
            @error="onLoaded"
            @mousedown="onImgMouseDown"
            @mousemove="onImgMouseMove"
            @mouseup="onImgMouseUp"
            @mouseleave="onImgMouseUp"
          />
        </div>
      </div>

      <!-- 非图片预览（iframe，Office 转换期间显示加载遮罩） -->
      <div v-else v-loading="loading" element-loading-text="加载中…" class="apd-other-wrap" @wheel.prevent="onOtherWheel">
        <iframe :src="src" class="apd-iframe"
          :style="{
            width: `${100 * imgState.scale}%`,
            height: `${70 * imgState.scale}vh`,
          }"
          @load="onLoaded"
        />
      </div>

      <!-- 工具栏：左右切换 + 重置 -->
      <div v-if="list.length > 1 || imgState.scale !== 1" class="apd-toolbar">
        <template v-if="list.length > 1">
          <el-button size="small" :disabled="index <= 0" @click="prev"><el-icon><ArrowLeft /></el-icon></el-button>
          <span class="apd-counter">{{ index + 1 }} / {{ list.length }}</span>
          <el-button size="small" :disabled="index >= list.length - 1" @click="next"><el-icon><ArrowRight /></el-icon></el-button>
        </template>
        <span v-if="list.length > 1 && imgState.scale !== 1" class="apd-sep"></span>
        <el-button v-if="imgState.scale !== 1" size="small" text @click="resetZoom">重置</el-button>
      </div>
    </template>

    <!-- 编辑会话视图：副本已打开，原件锁定，等待用户保存/放弃 -->
    <div v-else class="apd-edit-panel">
      <el-icon :size="40"><Edit /></el-icon>
      <p class="apd-edit-title">已用系统程序打开副本：<b>{{ editSession.displayName }}</b></p>
      <p class="apd-hint">原件已锁定，编辑期间不可被删除或移动。改完后点「保存回系统」覆盖原件，或「放弃修改」。</p>
    </div>

    <template #footer>
      <el-button @click="requestClose">关闭</el-button>
      <el-button @click="openInNewTab">新窗口打开</el-button>
      <el-button type="primary" @click="download">下载</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, ArrowRight, Edit } from '@element-plus/icons-vue'
import { openUploadFile } from '../api'
import http from '../api'

const IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg', '.ico']

const visible = ref(false)
const list = ref([])
const index = ref(0)
const src = ref('')
const title = ref('')
const attId = ref(null)
const isImage = ref(false)
const loading = ref(false)
// 编辑会话：{ copyPath, displayName } 或 null。非空表示副本已打开、原件锁定
const editSession = ref(null)

const imgState = ref({ x: 0, y: 0, scale: 1 })
const isDragging = ref(false)
const dragStart = { x: 0, y: 0 }
const dragImgState = { x: 0, y: 0 }

// item.id 的 API 基址：需求正文文件带 item.apiBase（/projects/.../requirements/.../files），
// 任务附件缺省走 /attachments —— 预览/下载/本地打开与任务附件共用同一套端点行为。
// 注意两条通道对前缀要求不同，不可混用：
//   apiPath —— 供 axios（baseURL 已是 /api），如 startEdit 的 POST
//   apiUrl  —— 供 iframe/window.open 直开的完整地址（/api + apiPath）
// 曾踩坑：apiUrl 漏 /api 时请求被 SPA fallback 接管渲染出整个系统页面；
//         startEdit 误用 apiUrl 时 axios 又叠加 baseURL 造成 /api/api 双前缀 404。
const apiPath = (item, suffix) => `${item.apiBase || '/attachments'}/${item.id}/${suffix}`
const apiUrl = (item, suffix) => `/api${apiPath(item, suffix)}`

// 预览项统一结构：{ id?, src, title, downloadUrl?, downloadName?, type?, _isComImage? }
// - 有 id：附件（走附件预览/下载接口）
// - 无 id + type:'image'/_isComImage：直接用 src 当图片
// - 无 id + 其他（需求页超链接文件）：src 即预览 URL，下载走 downloadUrl
const applyPreview = (item) => {
  attId.value = item.id ?? null
  title.value = item.title || item.original_filename || ''
  loading.value = true
  if (item.id) {
    // 加 t 时间戳：回写后重挂预览可强制浏览器/Office 缓存刷新
    src.value = apiUrl(item, 'preview') + '?t=' + Date.now()
    const ext = (item.original_filename || item.title || '').split('.').pop() || ''
    isImage.value = IMAGE_EXTS.includes('.' + ext.toLowerCase())
  } else {
    src.value = item.src
    isImage.value = !!item._isComImage || item.type === 'image'
  }
  imgState.value = { x: 0, y: 0, scale: 1 }
}

// open(items, startIndex)：items 为可翻页的附件列表，startIndex 为初始项下标
const open = (items, startIndex) => {
  list.value = items || []
  index.value = Math.max(0, startIndex ?? 0)
  if (!list.value.length) return
  if (index.value >= list.value.length) index.value = list.value.length - 1
  editSession.value = null
  applyPreview(list.value[index.value])
  visible.value = true
}
const close = () => { visible.value = false }

const prev = () => {
  if (index.value <= 0) return
  index.value--
  applyPreview(list.value[index.value])
}

const next = () => {
  if (index.value >= list.value.length - 1) return
  index.value++
  applyPreview(list.value[index.value])
}

const onLoaded = () => { loading.value = false }

const download = async () => {
  const item = list.value[index.value]
  if (!item) return
  // 自定义下载名（需求页保留 {需求ID}_{文件名} 习惯）：fetch blob + a.download
  if (item.downloadName) {
    const url = item.downloadUrl || item.src
    try {
      const res = await fetch(url)
      const blob = await res.blob()
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = item.downloadName
      a.click()
      URL.revokeObjectURL(a.href)
    } catch {
      window.open(url, '_blank')
    }
    return
  }
  if (item.id) window.open(apiUrl(item, 'download'), '_blank')
  else if (item.downloadUrl) window.open(item.downloadUrl, '_blank')
  else if (src.value) window.open(src.value, '_blank')
}

// 新窗口打开预览：
// 1) 附件（有 id）→ 后端 as_page HTML 包装页（浏览器标签标题=文件名）
// 2) 无 id 但 src 是预览接口（如需求文件 /preview）→ 同样走后端 as_page 包装页
// 3) 其余（沟通内联图片 / 需求正文图片）→ 前端注入 title 包装兜底
const openInNewTab = () => {
  if (!src.value) return
  const item = list.value[index.value]
  if (item.id) {
    // 需求文件包装页标题沿用链接文字（后端优先 original_filename），否则后端自带文件名
    const titleParam = item.apiBase && title.value ? `&title=${encodeURIComponent(title.value)}` : ''
    window.open(`${apiUrl(item, 'preview')}?as_page=1${titleParam}`, '_blank', 'noopener')
    return
  }
  if (!isImage.value && /\/preview(\?|$)/.test(src.value)) {
    const sep = src.value.includes('?') ? '&' : '?'
    // title 传给后端作包装页标题：需求文件物理名为 uuid 乱码，需用前端显示名
    window.open(`${src.value}${sep}as_page=1&title=${encodeURIComponent(title.value || '')}`, '_blank', 'noopener')
    return
  }
  const w = window.open('', '_blank')
  if (!w) { window.open(src.value, '_blank', 'noopener'); return }
  const esc = (s) => (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
  const body = isImage.value
    ? `<div style="height:100vh;display:flex;align-items:center;justify-content:center;background:#f5f5f5"><img src="${esc(src.value)}" style="max-width:100%;max-height:100vh;object-fit:contain"></div>`
    : `<iframe src="${esc(src.value)}" style="width:100%;height:100vh;border:0;display:block"></iframe>`
  w.document.write(
    `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${esc(title.value)}</title>` +
    `<style>*{margin:0;padding:0;box-sizing:border-box}body{background:#f5f5f5}</style></head>` +
    `<body>${body}</body></html>`
  )
  w.document.close()
}

// 当前项是否可用系统程序打开：
// - 附件（有 id）→ 直接定位磁盘文件
// - 无 id 但源是 /uploads/ 上传目录文件（沟通内联图 / 需求正文图片与文件）→ 按 URL 解析磁盘路径
const canOpenInApp = computed(() => {
  if (attId.value) return true
  const item = list.value[index.value]
  const url = item?.downloadUrl || (item?.src?.startsWith('/uploads/') ? item.src : '')
  return !!(url && url.startsWith('/uploads/'))
})

// 开始副本编辑：复制出带原文件名的副本并打开，原件加逻辑锁（编辑期间不可删/移/再编辑）
const startEdit = async () => {
  const item = list.value[index.value]
  if (!item) return
  if (!item.id) {
    // 无 id 项（沟通/需求正文内联图片等）：直接打开原件
    const url = item.downloadUrl || (item.src?.startsWith('/uploads/') ? item.src : '')
    if (url && url.startsWith('/uploads/')) {
      try { await openUploadFile(url); ElMessage.success('已用系统默认程序打开') }
      catch (e) { ElMessage.error(e.response?.data?.detail || '打开失败') }
    } else {
      ElMessage.warning('该文件不支持用系统程序打开')
    }
    return
  }
  try {
    const displayName = item.title || item.original_filename || ''
    const res = await http.post(apiPath(item, 'open-copy'), { display_name: displayName })
    editSession.value = { copyPath: res.copy_path, displayName: res.display_name }
    if (res.warn) ElMessage.warning(res.warn)
  } catch (e) {
    const status = e.response?.status
    const detail = e.response?.data?.detail || '打开编辑失败'
    if (status === 423) ElMessage.warning(detail)
    else ElMessage.error(detail)
  }
}

// 保存回系统：副本内容原子覆盖原件，刷新预览（cache-bust）
const commitEdit = async () => {
  const item = list.value[index.value]
  if (!item || !editSession.value) return
  try {
    await http.post(apiPath(item, 'commit-edit'), { copy_path: editSession.value.copyPath })
  } catch (e) {
    const status = e.response?.status
    const detail = e.response?.data?.detail || '保存失败'
    if (status === 409) {
      // 原件被外部修改 / 会话失效：二次确认后强制覆盖
      try {
        await ElMessageBox.confirm(detail + ' 仍要覆盖保存吗？', '原件已被外部修改', { type: 'warning' })
        await http.post(apiPath(item, 'commit-edit'), { copy_path: editSession.value.copyPath, force: true })
      } catch (ce) {
        if (ce !== 'cancel' && ce?.message !== 'cancel') ElMessage.error('保存失败')
        return
      }
    } else {
      ElMessage.error(detail)
      return
    }
  }
  editSession.value = null
  applyPreview(item)
  ElMessage.success('已保存回系统')
}

// 放弃修改：删除副本、清锁、恢复预览
const discardEdit = async () => {
  const item = list.value[index.value]
  if (!item || !editSession.value) return
  await doDiscard(item)
  applyPreview(item)
  ElMessage.info('已放弃修改')
}

// 静默放弃（关闭对话框时调用，不提示）
const doDiscard = async (item) => {
  if (item && editSession.value) {
    try { await http.post(apiPath(item, 'discard-edit'), { copy_path: editSession.value.copyPath }) } catch { /* 忽略 */ }
  }
  editSession.value = null
}

// 关闭对话框：编辑会话未结束则先确认放弃，避免锁残留
const requestClose = () => {
  if (editSession.value) {
    ElMessageBox.confirm('有未保存的编辑，关闭将放弃修改。确定关闭？', '提示', { type: 'warning' })
      .then(async () => { await doDiscard(list.value[index.value]); visible.value = false })
      .catch(() => {})
  } else {
    visible.value = false
  }
}

// ---- 图片滚轮缩放 ----
const onImgWheel = (e) => {
  const step = e.deltaY > 0 ? -0.05 : 0.05
  const newScale = Math.round((imgState.value.scale + step) * 100) / 100
  if (newScale < 0.01) { imgState.value = { x: 0, y: 0, scale: 0.01 }; return }
  // 居中状态（未拖拽过）只调大小不移动位置，保证第一次缩放无跳动
  if (imgState.value.x === 0 && imgState.value.y === 0) {
    imgState.value = { x: 0, y: 0, scale: newScale }
    return
  }
  const wrap = e.currentTarget
  const rect = wrap.getBoundingClientRect()
  const mx = rect.width / 2
  const my = rect.height / 2
  const ratio = newScale / imgState.value.scale
  imgState.value = {
    x: Math.round((imgState.value.x + mx * (1 - ratio)) * 10) / 10,
    y: Math.round((imgState.value.y + my * (1 - ratio)) * 10) / 10,
    scale: newScale,
  }
}

const onImgMouseDown = (e) => {
  if (e.button !== 0 || imgState.value.scale === 1) return
  isDragging.value = true
  dragStart.x = e.clientX
  dragStart.y = e.clientY
  dragImgState.x = imgState.value.x
  dragImgState.y = imgState.value.y
  e.preventDefault()
}

const onImgMouseMove = (e) => {
  if (!isDragging.value) return
  imgState.value = {
    ...imgState.value,
    x: +(dragImgState.x + e.clientX - dragStart.x).toFixed(1),
    y: +(dragImgState.y + e.clientY - dragStart.y).toFixed(1),
  }
}

const onImgMouseUp = () => {
  isDragging.value = false
}

const onOtherWheel = (e) => {
  const step = e.deltaY > 0 ? -0.05 : 0.05
  const newScale = Math.round((imgState.value.scale + step) * 100) / 100
  if (newScale < 0.01) { imgState.value = { x: 0, y: 0, scale: 0.01 }; return }
  imgState.value = { x: 0, y: 0, scale: newScale }
}

const resetZoom = () => {
  imgState.value = { x: 0, y: 0, scale: 1 }
}

defineExpose({ open, close })
</script>

<style scoped>
.apd-header { display: flex; align-items: center; gap: 10px; }
.apd-title { font-size: 15px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.apd-counter { font-size: 12px; color: #999; flex-shrink: 0; }
.apd-header-actions { margin-left: auto; flex-shrink: 0; }
.apd-img-wrap { overflow: auto; height: 70vh; background: #f5f5f5; border-radius: 4px; position: relative; user-select: none; }
.apd-img-container { min-height: 100%; text-align: center; padding: 16px; }
.apd-img { max-width: 100%; max-height: calc(70vh - 80px); display: inline-block; vertical-align: top; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.apd-other-wrap { overflow: auto; height: 70vh; background: #f5f5f5; border-radius: 4px; }
.apd-iframe { border: none; border-radius: 4px; background: #fff; transform-origin: top left; display: block; }
.apd-toolbar { display: flex; align-items: center; justify-content: center; gap: 6px; margin-top: 10px; }
.apd-toolbar .apd-sep { display: inline-block; width: 1px; height: 18px; background: #e0e0e0; flex-shrink: 0; }
.apd-edit-panel { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; height: 50vh; color: #409eff; background: #f5f9ff; border-radius: 6px; }
.apd-edit-title { font-size: 15px; color: #333; }
.apd-edit-title b { color: #409eff; }
.apd-hint { font-size: 13px; color: #888; max-width: 80%; text-align: center; line-height: 1.6; }
</style>
