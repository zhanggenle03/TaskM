<template>
  <el-dialog v-model="visible" width="80%" top="5vh" destroy-on-close append-to-body :show-close="false">
    <template #header>
      <div class="apd-header">
        <span class="apd-title">{{ title }}</span>
        <span v-if="list.length > 1" class="apd-counter">{{ index + 1 }} / {{ list.length }}</span>
        <span class="apd-header-actions">
          <!-- 编辑：用系统默认程序打开原始文件（附件 / 上传目录文件均可） -->
          <el-button v-if="canOpenInApp" size="small" @click="openInApp">
            <el-icon><Edit /></el-icon> 编辑
          </el-button>
        </span>
      </div>
    </template>

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

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button @click="openInNewTab">新窗口打开</el-button>
      <el-button type="primary" @click="download">下载</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft, ArrowRight, Edit } from '@element-plus/icons-vue'
import { openAttachment, openUploadFile } from '../api'

const IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg', '.ico']

const visible = ref(false)
const list = ref([])
const index = ref(0)
const src = ref('')
const title = ref('')
const attId = ref(null)
const isImage = ref(false)
const loading = ref(false)

const imgState = ref({ x: 0, y: 0, scale: 1 })
const isDragging = ref(false)
const dragStart = { x: 0, y: 0 }
const dragImgState = { x: 0, y: 0 }

const previewUrl = (id) => `/api/attachments/${id}/preview`
const downloadUrl = (id) => `/api/attachments/${id}/download`

// 预览项统一结构：{ id?, src, title, downloadUrl?, downloadName?, type?, _isComImage? }
// - 有 id：附件（走附件预览/下载接口）
// - 无 id + type:'image'/_isComImage：直接用 src 当图片
// - 无 id + 其他（需求页超链接文件）：src 即预览 URL，下载走 downloadUrl
const applyPreview = (item) => {
  attId.value = item.id ?? null
  title.value = item.title || item.original_filename || ''
  loading.value = true
  if (item.id) {
    src.value = previewUrl(item.id)
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
  if (attId.value) window.open(downloadUrl(attId.value), '_blank')
  else if (item.downloadUrl) window.open(item.downloadUrl, '_blank')
  else if (src.value) window.open(src.value, '_blank')
}

// 新窗口打开预览：
// 1) 附件（有 id）→ 后端 as_page HTML 包装页（浏览器标签标题=文件名）
// 2) 无 id 但 src 是预览接口（如需求文件 /preview）→ 同样走后端 as_page 包装页
// 3) 其余（沟通内联图片 / 需求正文图片）→ 前端注入 title 包装兜底
const openInNewTab = () => {
  if (!src.value) return
  if (attId.value) {
    window.open(`${previewUrl(attId.value)}?as_page=1`, '_blank', 'noopener')
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

// 用系统默认程序打开原始文件（等价于双击文件，触发 Word/Excel 等本地应用）
const openInApp = async () => {
  const item = list.value[index.value]
  const url = item?.downloadUrl || (item?.src?.startsWith('/uploads/') ? item.src : '')
  try {
    if (attId.value) {
      await openAttachment(attId.value)
    } else if (url && url.startsWith('/uploads/')) {
      await openUploadFile(url)
    } else {
      ElMessage.warning('该文件不支持用系统程序打开')
      return
    }
    ElMessage.success('已用系统默认程序打开')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '打开失败')
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
</style>
